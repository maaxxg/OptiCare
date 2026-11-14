"""Opt-in intake API tests on real PostGIS (E2-T2): patients, visit requests, candidate slots."""

from __future__ import annotations

import json
import os
from collections.abc import Generator
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.main import app
from app.models import Department, Facility, Slot, make_point_wkt

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="DB tests are opt-in: set RUN_DB_TESTS=1 and start the db service",
)

ZAGREB_TZ = ZoneInfo("Europe/Zagreb")


@pytest.fixture
def db(migrated: None) -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client(migrated: None) -> Generator[TestClient, None, None]:
    """Real get_db against the freshly migrated PostGIS database."""
    yield TestClient(app)


def test_post_patients_deduplicates_by_mbo_and_auto_geocodes(client: TestClient) -> None:
    payload = {
        "first_name": "Katica",
        "last_name": "Starčević",
        "birth_year": 1949,
        "mbo": "000000006",
        "phone": "+385 00 000 0006",
        "phone_type": "basic_mobile",
        "address": "Donji Kosinj 14",
        "settlement": "Donji Kosinj",
        "municipality": "Perušić",
        "county": "Ličko-senjska",
        "mobility_class": "walks",
        "lives_alone": True,
    }
    first = client.post("/patients", json=payload)
    assert first.status_code == 201
    p1 = first.json()
    assert p1["mbo_masked"] == "*****0006"
    assert "000000006" not in json.dumps(p1)
    assert p1["location"]["lat"] == pytest.approx(44.75986, abs=1e-4)
    assert p1["municipality"] == "Perušić"

    # Re-submitting with the same MBO updates the existing patient record
    updated_payload = {
        **payload,
        "phone": "+385 00 999 0006",
        "mobility_class": "cane",
    }
    second = client.post("/patients", json=updated_payload)
    assert second.status_code == 200
    p2 = second.json()
    assert p2["id"] == p1["id"]
    assert p2["phone"] == "+385 00 999 0006"
    assert p2["mobility_class"] == "cane"

    by_mbo = client.post("/patients/lookup", json={"mbo": "000000006"})
    assert by_mbo.status_code == 200
    assert len(by_mbo.json()) == 1
    assert by_mbo.json()[0]["id"] == p1["id"]
    assert by_mbo.json()[0]["mbo_masked"] == "*****0006"
    assert "000000006" not in by_mbo.text
    assert client.post("/patients/lookup", json={"mbo": "000000007"}).json() == []


_REQUIRED = {
    "first_name": "Katica",
    "last_name": "Starčević",
    "mbo": "000000016",
    "phone": "+385 00 000 0016",
    "settlement": "Donji Kosinj",
    "municipality": "Perušić",
    "county": "Ličko-senjska",
}


def _lookup(client: TestClient, mbo: str) -> dict:
    found = client.post("/patients/lookup", json={"mbo": mbo})
    assert found.status_code == 200
    return found.json()[0]


def test_post_patients_update_changes_only_sent_fields(client: TestClient) -> None:
    created = client.post(
        "/patients",
        json={
            **_REQUIRED,
            "transport_entitlement": "sanitetski",
            "missed_visits_last_year": 2,
            "own_car": True,
            "lives_alone": True,
        },
    )
    assert created.status_code == 201
    p1 = created.json()

    # Only required fields plus a new phone: everything else must survive.
    again = client.post("/patients", json={**_REQUIRED, "phone": "+385 00 111 0016"})
    assert again.status_code == 200
    p2 = again.json()
    assert p2["id"] == p1["id"]
    assert p2["phone"] == "+385 00 111 0016"
    assert p2["transport_entitlement"] == "sanitetski"
    assert p2["missed_visits_last_year"] == 2
    assert p2["own_car"] is True
    assert p2["lives_alone"] is True

    # Explicit values do overwrite.
    explicit = client.post("/patients", json={**_REQUIRED, "lives_alone": False})
    assert explicit.status_code == 200
    assert explicit.json()["lives_alone"] is False
    assert explicit.json()["transport_entitlement"] == "sanitetski"


def test_post_patients_update_keeps_location_when_geocoding_fails(client: TestClient) -> None:
    first = client.post("/patients", json=_REQUIRED)
    assert first.status_code == 201
    location = first.json()["location"]
    assert location is not None

    unknown = {**_REQUIRED, "settlement": "Nepostojeće Selo"}
    again = client.post("/patients", json=unknown)
    assert again.status_code == 200
    assert again.json()["location"] == location


def test_post_patients_same_name_matches_ignoring_case_and_diacritics(
    client: TestClient,
) -> None:
    assert client.post("/patients", json=_REQUIRED).status_code == 201
    again = client.post(
        "/patients", json={**_REQUIRED, "first_name": "katica", "last_name": "STARCEVIC"}
    )
    assert again.status_code == 200


def test_post_patients_different_name_is_409_and_changes_nothing(client: TestClient) -> None:
    assert client.post("/patients", json={**_REQUIRED, "transport_entitlement": "sanitetski"})
    before = _lookup(client, "000000016")

    clash = client.post(
        "/patients",
        json={**_REQUIRED, "last_name": "Horvat", "phone": "+385 00 222 0016"},
    )
    assert clash.status_code == 409
    assert clash.json()["detail"]
    assert "000000016" not in clash.text
    assert "Starčević" not in clash.text
    assert _lookup(client, "000000016") == before


def test_patient_422_never_echoes_the_mbo(client: TestClient) -> None:
    # Missing required fields: pydantic puts the whole body into `input`.
    missing = client.post("/patients", json={"mbo": "12345678a", "name": "x"})
    assert missing.status_code == 422
    assert "12345678a" not in missing.text

    bad_lookup = client.post("/patients/lookup", json={"mbo": "12345678a", "extra": 1})
    assert bad_lookup.status_code == 422
    assert "12345678a" not in bad_lookup.text

    # Valid-length MBO next to another error must not leak either.
    other = client.post("/patients", json={"mbo": "123456789", "first_name": ""})
    assert other.status_code == 422
    assert "123456789" not in other.text


def test_post_requests_generates_candidate_slots_or_sets_pending(
    client: TestClient,
    db: Session,
) -> None:
    facility = Facility(
        key="ob_gospic",
        name="Opća bolnica Gospić",
        level="secondary",
        settlement="Gospić",
        municipality="Gospić",
        county="Ličko-senjska",
        location=make_point_wkt(44.5435, 15.36214),
    )
    db.add(facility)
    db.commit()
    db.refresh(facility)

    slot_morning = Slot(
        facility_id=facility.id,
        department=Department.CARDIOLOGY.value,
        start_time=datetime.combine(date(2026, 11, 17), time(8, 30), tzinfo=ZAGREB_TZ),
        end_time=datetime.combine(date(2026, 11, 17), time(9, 0), tzinfo=ZAGREB_TZ),
        capacity=2,
    )
    slot_afternoon = Slot(
        facility_id=facility.id,
        department=Department.CARDIOLOGY.value,
        start_time=datetime.combine(date(2026, 11, 19), time(13, 0), tzinfo=ZAGREB_TZ),
        end_time=datetime.combine(date(2026, 11, 19), time(13, 30), tzinfo=ZAGREB_TZ),
        capacity=2,
    )
    slot_outside_fixed = Slot(
        facility_id=facility.id,
        department=Department.DIALYSIS.value,
        start_time=datetime.combine(date(2026, 11, 20), time(7, 30), tzinfo=ZAGREB_TZ),
        end_time=datetime.combine(date(2026, 11, 20), time(12, 0), tzinfo=ZAGREB_TZ),
        capacity=4,
    )
    db.add_all([slot_morning, slot_afternoon, slot_outside_fixed])
    db.commit()

    pat_resp = client.post(
        "/patients",
        json={
            "first_name": "Mirko",
            "last_name": "Devčić",
            "mbo": "000000009",
            "phone": "+385 00 000 0009",
            "settlement": "Smiljan",
            "municipality": "Gospić",
            "county": "Ličko-senjska",
        },
    )
    patient_id = pat_resp.json()["id"]

    # 1. Matching slots found within window -> attached to candidate_slots, pending=False
    req1 = client.post(
        "/requests",
        json={
            "patient_id": patient_id,
            "facility_id": facility.id,
            "department": "cardiology",
            "visit_type": "first_visit",
            "urgency_class": "within_week",
            "earliest_date": "2026-11-16",
            "latest_date": "2026-11-22",
        },
    )
    assert req1.status_code == 201
    r1_data = req1.json()
    assert r1_data["slot_request_pending"] is False
    assert [s["id"] for s in r1_data["candidate_slots"]] == [
        slot_morning.id,
        slot_afternoon.id,
    ]

    # 2. Urgency class FIXED (max_shift_days = 0) clamps window to earliest_date;
    #    no slot on 2026-11-16 -> slot_request_pending=True with preferred_time_of_day
    req2 = client.post(
        "/requests",
        json={
            "patient_id": patient_id,
            "facility_id": facility.id,
            "department": "dialysis",
            "visit_type": "dialysis_session",
            "urgency_class": "fixed",
            "earliest_date": "2026-11-16",
            "latest_date": "2026-11-22",
            "preferred_time_of_day": "afternoon",
        },
    )
    assert req2.status_code == 201
    r2_data = req2.json()
    assert r2_data["candidate_slots"] == []
    assert r2_data["slot_request_pending"] is True
    assert r2_data["preferred_time_of_day"] == "afternoon"
    assert r2_data["latest_date"] == "2026-11-16"

    # 3. Department with no open slots and no preferred_time_of_day defaults to "morning"
    req3 = client.post(
        "/requests",
        json={
            "patient_id": patient_id,
            "facility_id": facility.id,
            "department": "neurology",
            "visit_type": "follow_up",
            "urgency_class": "within_week",
            "earliest_date": "2026-11-16",
            "latest_date": "2026-11-20",
        },
    )
    assert req3.status_code == 201
    r3_data = req3.json()
    assert r3_data["candidate_slots"] == []
    assert r3_data["slot_request_pending"] is True
    assert r3_data["preferred_time_of_day"] == "morning"
