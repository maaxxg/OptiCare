from __future__ import annotations

import json
from collections.abc import Generator
from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import pytest
import yaml
from fastapi.testclient import TestClient
from geoalchemy2 import Geography
from shapely import wkt as shapely_wkt
from sqlalchemy import create_engine, event
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.adapters import get_llm_client
from app.adapters.geocoding import MockGeocodingClient
from app.adapters.llm import MockLLMClient
from app.config import get_settings
from app.db import Base, get_db
from app.intake import (
    EXTRACTION_EXAMPLES_PATH,
    SYSTEM_PROMPT_HR,
    extract_intake,
    strip_mbo_from_text,
)
from app.main import app
from app.models import (
    Department,
    Facility,
    MobilityClass,
    UrgencyClass,
    VisitType,
    make_point_wkt,
)

ZAGREB_TZ = ZoneInfo("Europe/Zagreb")


@compiles(Geography, "sqlite")
def _compile_geography_sqlite(_element: Any, _compiler: Any, **_kw: Any) -> str:
    return "TEXT"


class SpyLLMClient:
    """Test double that records the exact prompt sent to the LLM (E11-T1)."""

    def __init__(self, delegate: Any | None = None) -> None:
        self.delegate = delegate or MockLLMClient()
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return str(self.delegate.complete(system, user))


def _wkt_to_ewkb_hex(value: str | bytes | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.hex()
    text = str(value).strip()
    if ";" in text:
        text = text.split(";", 1)[1].strip()
    try:
        geom = shapely_wkt.loads(text)
        return str(geom.wkb_hex)
    except Exception:
        return text


@pytest.fixture
def sqlite_session() -> Generator[Session, None, None]:
    """In-memory SQLite session with lightweight GeoAlchemy2 function shims."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _register_geo_shims(dbapi_conn: Any, _record: Any) -> None:
        dbapi_conn.create_function("RecoverGeometryColumn", -1, lambda *_args: 1)
        dbapi_conn.create_function("DiscardGeometryColumn", -1, lambda *_args: 1)
        dbapi_conn.create_function("AddGeometryColumn", -1, lambda *_args: 1)
        dbapi_conn.create_function("CreateSpatialIndex", -1, lambda *_args: 1)
        dbapi_conn.create_function("DisableSpatialIndex", -1, lambda *_args: 1)
        dbapi_conn.create_function("ST_GeogFromText", 1, _wkt_to_ewkb_hex)
        dbapi_conn.create_function("ST_GeomFromText", -1, lambda wkt, *_a: _wkt_to_ewkb_hex(wkt))
        dbapi_conn.create_function("GeomFromEWKT", 1, _wkt_to_ewkb_hex)
        dbapi_conn.create_function("AsEWKB", 1, _wkt_to_ewkb_hex)
        dbapi_conn.create_function("ST_AsEWKB", 1, _wkt_to_ewkb_hex)
        dbapi_conn.create_function("ST_AsBinary", 1, _wkt_to_ewkb_hex)
        dbapi_conn.create_function("AsBinary", 1, _wkt_to_ewkb_hex)

    for table in Base.metadata.tables.values():
        table.create(bind=engine, checkfirst=True)

    testing_session_local = sessionmaker(bind=engine)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(sqlite_session: Session) -> Generator[TestClient, None, None]:
    def _override_get_db() -> Generator[Session, None, None]:
        yield sqlite_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# E11-T1 (KAN-76): MBO privacy guard — MBO is never sent to the LLM
# ---------------------------------------------------------------------------


def test_mbo_is_stripped_before_llm_and_never_in_prompt() -> None:
    spy = SpyLLMClient()
    raw_text = (
        "Pacijent Ivan Kovačević (1958.), MBO 123456789, tel +385 00 000 0002, mobitel, Otočac. "
        "U invalidskim je kolicima nakon operacije kuka i treba kontrolu kod ortopeda u Gospiću "
        "ovaj tjedan. Supruga ide sa mnom kao pratnja."
    )
    sanitized, extracted_mbo, _ = strip_mbo_from_text(raw_text)
    assert extracted_mbo == "123456789"
    assert "123456789" not in sanitized
    assert "[MBO_REDACTED]" in sanitized

    result = extract_intake(
        text=raw_text,
        llm_client=spy,
        geocoding_client=MockGeocodingClient(),
    )
    assert len(spy.calls) == 1
    sent_system, sent_user = spy.calls[0]
    assert "123456789" not in sent_system
    assert "123456789" not in sent_user
    assert result.mbo_stripped is True
    assert result.patient.mbo == "123456789"
    assert "mbo" not in result.for_review


def test_spaced_and_spoken_mbo_are_stripped() -> None:
    s1, m1, _ = strip_mbo_from_text("Da vam odmah dam MBO, 000 000 301. Hodam sa štapom.")
    assert m1 == "000000301"
    assert "000 000 301" not in s1
    assert "301" not in s1

    s2, m2, _ = strip_mbo_from_text(
        "MBO mi je nula nula nula nula nula nula tri nula tri. Telefon 000 0303."
    )
    assert m2 == "000000303"
    assert "nula nula" not in s2
    assert "tri nula tri" not in s2
    assert "000 0303" in s2


@pytest.mark.parametrize(
    ("text", "expected_text", "expected_mbo"),
    [
        ("+385 91 234 5678", "+385 91 234 5678", None),
        ("tel +385 00 000 0002", "tel +385 00 000 0002", None),
        ("tel 0038591 234 5678", "tel 0038591 234 5678", None),
        ("053 123 456", "[MBO_REDACTED]", None),
        ("tel 053 572 111, MBO 123456789", "tel [MBO_REDACTED], MBO [MBO_REDACTED]", "123456789"),
        ("tel 091 234 567", "tel [MBO_REDACTED]", None),
        ("123456789", "[MBO_REDACTED]", None),
        ("MBO 111111111 i MBO 222222222", "MBO [MBO_REDACTED] i MBO [MBO_REDACTED]", None),
        (
            "MBO 123456789. Ponavljam: MBO 123 456 789",
            "MBO [MBO_REDACTED]. Ponavljam: MBO [MBO_REDACTED]",
            "123456789",
        ),
        ("Matični broj: 123456789", "Matični broj: [MBO_REDACTED]", "123456789"),
        ("M.B.O. 123456789", "M.B.O. [MBO_REDACTED]", "123456789"),
        ("MBO je. 123456789", "MBO je. [MBO_REDACTED]", None),  # cue in another sentence
        ("MBO mi je jedan dva tri 123456789", "MBO mi je jedan dva tri [MBO_REDACTED]", None),
    ],
)
def test_mbo_assigned_only_from_cued_candidate(
    text: str, expected_text: str, expected_mbo: str | None
) -> None:
    sanitized, mbo, _ = strip_mbo_from_text(text)
    assert sanitized == expected_text
    assert mbo == expected_mbo


def test_spoken_mbo_after_cue_keeps_spoken_phone() -> None:
    sanitized, mbo, redacted = strip_mbo_from_text(
        "MBO mi je nula nula nula nula nula nula tri nula tri. Telefon nula nula nula nula "
        "tri nula tri."
    )
    assert mbo == "000000303"
    assert redacted is True
    assert sanitized.startswith("MBO mi je [MBO_REDACTED].")
    assert "nula nula nula nula tri nula tri" in sanitized


def test_ambiguous_mbo_is_flagged_for_review_and_not_sent_to_llm() -> None:
    spy = SpyLLMClient(delegate=MockLLMClient(response="{}"))
    result = extract_intake(
        text="MBO 111111111, a možda MBO 222222222.",
        llm_client=spy,
        geocoding_client=MockGeocodingClient(),
    )
    sent = spy.calls[0][1]
    assert "111111111" not in sent
    assert "222222222" not in sent
    assert result.mbo_stripped is True
    assert result.patient.mbo is None
    assert "mbo" in result.for_review


def test_uncued_number_sets_mbo_stripped_but_not_mbo() -> None:
    spy = SpyLLMClient(delegate=MockLLMClient(response="{}"))
    result = extract_intake(
        text="Zovite me na 053 123 456.",
        llm_client=spy,
        geocoding_client=MockGeocodingClient(),
    )
    assert "053 123 456" not in spy.calls[0][1]
    assert result.mbo_stripped is True
    assert result.patient.mbo is None
    assert "mbo" in result.for_review


def test_all_extraction_examples_mbo_from_cue_and_never_sent_to_llm() -> None:
    path = get_settings().data_dir / EXTRACTION_EXAMPLES_PATH
    examples = yaml.safe_load(path.read_text(encoding="utf-8"))["examples"]
    assert len(examples) >= 34
    for ex in examples:
        expected = ex.get("mbo_in_text")
        sanitized, mbo, _ = strip_mbo_from_text(str(ex["text"]))
        assert mbo == expected, ex.get("id")
        if expected:
            spaced = " ".join([expected[:3], expected[3:6], expected[6:]])
            assert expected not in sanitized
            assert spaced not in sanitized
            assert "nula nula nula nula nula nula" not in sanitized.lower()


def test_llm_hallucinated_mbo_is_discarded() -> None:
    fake_json = json.dumps(
        {
            "patient": {
                "first_name": "Ana",
                "last_name": "Babić",
                "mbo": "987654321",
                "settlement": "Senj",
                "mobility_class": "stretcher",
            },
            "visit_request": {
                "department": "radiology",
                "visit_type": "procedure_test",
                "urgency_class": "within_few_days",
            },
        }
    )
    spy = SpyLLMClient(delegate=MockLLMClient(response=fake_json))
    result = extract_intake(
        text="Majka Ana Babić iz Senja mora na hitno CT snimanje u Gospić.",
        llm_client=spy,
        geocoding_client=MockGeocodingClient(),
    )
    assert result.mbo_stripped is False
    assert result.patient.mbo is None
    assert "mbo" in result.for_review


# ---------------------------------------------------------------------------
# E2-T1 (KAN-18) & E13-T5: Free-text extraction, Croatian prompt & for_review
# ---------------------------------------------------------------------------


def test_croatian_prompt_contains_instructions_and_examples() -> None:
    assert "Ličko-senjskoj županiji" in SYSTEM_PROMPT_HR
    assert "PRIMJER 1" in SYSTEM_PROMPT_HR
    assert "PRIMJER 2" in SYSTEM_PROMPT_HR
    assert '"patient"' in SYSTEM_PROMPT_HR
    assert '"visit_request"' in SYSTEM_PROMPT_HR


def test_all_34_extraction_examples_from_domain_yaml() -> None:
    path = get_settings().data_dir / EXTRACTION_EXAMPLES_PATH
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    examples = data["examples"]
    assert len(examples) == 34

    geo = MockGeocodingClient()
    for item in examples:
        spy = SpyLLMClient()
        res = extract_intake(item["text"], llm_client=spy, geocoding_client=geo)
        _, sent_user = spy.calls[0]

        if "mbo_in_text" in item:
            expected_mbo = str(item["mbo_in_text"])
            spaced_mbo = f"{expected_mbo[:3]} {expected_mbo[3:6]} {expected_mbo[6:]}"
            assert res.mbo_stripped is True, item["id"]
            assert res.patient.mbo == expected_mbo, item["id"]
            assert "[MBO_REDACTED]" in sent_user, item["id"]
            assert expected_mbo not in sent_user, item["id"]
            assert spaced_mbo not in sent_user, item["id"]
            assert "nula nula" not in sent_user.lower(), item["id"]
        else:
            assert res.mbo_stripped is False, item["id"]
            assert res.patient.mbo is None, item["id"]
            assert "mbo" in res.for_review, item["id"]

        combined = {
            **res.patient.model_dump(mode="json"),
            **res.visit_request.model_dump(mode="json"),
        }
        for key, expected_val in item["expected"].items():
            norm_expected = (
                expected_val.isoformat() if isinstance(expected_val, date) else expected_val
            )
            assert combined[key] == norm_expected, f"{item['id']} field {key}"

        for rev_field in item.get("review", []):
            assert rev_field in res.for_review, f"{item['id']} missing review {rev_field}"


def test_extract_intake_endpoint_offline_demo_and_missing_fields(client: TestClient) -> None:
    spy = SpyLLMClient()
    app.dependency_overrides[get_llm_client] = lambda: spy

    resp = client.post(
        "/intake/extract",
        json={
            "text": (
                "Majka je nepokretna i leži u krevetu na prvom katu bez lifta u Senju, "
                "MBO 000000003, a mora na hitno CT snimanje u Gospić. "
                "Ja živim s njom i idem u pratnju."
            )
        },
    )
    assert resp.status_code == 200
    body = resp.json()

    assert len(spy.calls) == 1
    assert "000000003" not in spy.calls[0][1]
    assert body["mbo_stripped"] is True
    assert body["patient"]["mbo"] == "000000003"
    assert body["patient"]["settlement"] == "Senj"
    assert body["patient"]["municipality"] == "Senj"
    assert body["patient"]["county"] == "Ličko-senjska"
    assert body["patient"]["location"]["lat"] == pytest.approx(44.9894, abs=1e-3)
    assert body["patient"]["mobility_class"] == MobilityClass.STRETCHER.value
    assert body["patient"]["floor"] == 1
    assert body["patient"]["elevator"] is False
    assert body["patient"]["companion"] is True
    assert body["visit_request"]["department"] == Department.RADIOLOGY.value
    assert body["visit_request"]["visit_type"] == VisitType.PROCEDURE_TEST.value
    assert body["visit_request"]["urgency_class"] == UrgencyClass.WITHIN_FEW_DAYS.value

    # Unmentioned required fields are flagged for review without guessing
    assert "first_name" in body["for_review"]
    assert "last_name" in body["for_review"]
    assert "phone" in body["for_review"]
    assert "earliest_date" in body["for_review"]
    assert "latest_date" in body["for_review"]


def test_extract_intake_rejects_invalid_llm_enums_into_for_review() -> None:
    bad_llm_json = json.dumps(
        {
            "patient": {
                "first_name": "Josip",
                "last_name": "Marić",
                "phone": "+385 00 000 0004",
                "settlement": "Korenica",
                "mobility_class": "helikopter",
            },
            "visit_request": {
                "department": "nepostojeci_odjel",
                "visit_type": "dialysis_session",
                "urgency_class": "fixed",
                "earliest_date": "2026-11-20",
                "latest_date": "2026-11-18",
            },
        }
    )
    result = extract_intake(
        text="Josip Marić iz Korenice ide na dijalizu.",
        llm_client=MockLLMClient(response=bad_llm_json),
        geocoding_client=MockGeocodingClient(),
    )
    assert result.patient.first_name == "Josip"
    assert result.patient.mobility_class is None
    assert result.visit_request.department is None
    assert result.visit_request.latest_date is None
    assert "mobility_class" in result.for_review
    assert "department" in result.for_review
    assert "latest_date" in result.for_review


# ---------------------------------------------------------------------------
# E2-T3 (KAN-20): Address geocoding
# ---------------------------------------------------------------------------


def test_geocode_endpoint_returns_coordinates_and_administrative_units(
    client: TestClient,
) -> None:
    resp = client.post(
        "/intake/geocode",
        json={"address": "Zagrebačka 12", "settlement": "Korenica"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["settlement"] == "Korenica"
    assert data["municipality"] == "Plitvička Jezera"
    assert data["county"] == "Ličko-senjska"
    assert data["location"]["lat"] == pytest.approx(44.7561, abs=1e-3)
    assert data["location"]["lon"] == pytest.approx(15.7061, abs=1e-3)

    kosinj = client.post("/intake/geocode", json={"address": "Donji Kosinj bb"})
    assert kosinj.status_code == 200
    assert kosinj.json()["settlement"] == "Donji Kosinj"
    assert kosinj.json()["municipality"] == "Perušić"
    assert kosinj.json()["county"] == "Ličko-senjska"

    unknown = client.post("/intake/geocode", json={"address": "Ilica 1, Zagreb"})
    assert unknown.status_code == 404


# ---------------------------------------------------------------------------
# E2-T2 (KAN-19): Saving confirmed records & candidate slot matching
# ---------------------------------------------------------------------------


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
    assert second.status_code == 201
    p2 = second.json()
    assert p2["id"] == p1["id"]
    assert p2["phone"] == "+385 00 999 0006"
    assert p2["mobility_class"] == "cane"

    by_mbo = client.get("/patients", params={"mbo": "000000006"})
    assert by_mbo.status_code == 200
    assert len(by_mbo.json()) == 1
    assert by_mbo.json()[0]["id"] == p1["id"]


def test_post_requests_generates_candidate_slots_or_sets_pending(
    client: TestClient,
    sqlite_session: Session,
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
    sqlite_session.add(facility)
    sqlite_session.commit()
    sqlite_session.refresh(facility)

    from app.models import Slot

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
    sqlite_session.add_all([slot_morning, slot_afternoon, slot_outside_fixed])
    sqlite_session.commit()

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
