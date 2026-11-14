from __future__ import annotations

import json
from collections.abc import Generator
from datetime import date
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.adapters import get_llm_client
from app.adapters.geocoding import MockGeocodingClient
from app.adapters.llm import MockLLMClient
from app.config import get_settings
from app.db import get_db
from app.intake import (
    EXTRACTION_EXAMPLES_PATH,
    SYSTEM_PROMPT_HR,
    extract_intake,
    strip_mbo_from_text,
)
from app.main import app
from app.models import (
    Department,
    MobilityClass,
    UrgencyClass,
    VisitType,
)


class SpyLLMClient:
    """Test double that records the exact prompt sent to the LLM (E11-T1)."""

    def __init__(self, delegate: Any | None = None) -> None:
        self.delegate = delegate or MockLLMClient()
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return str(self.delegate.complete(system, user))


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Client for DB-free endpoints; any use of the database fails loudly."""

    def _no_db() -> Generator[Session, None, None]:
        raise AssertionError("this test must not touch the database")
        yield  # pragma: no cover

    app.dependency_overrides[get_db] = _no_db
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
        # cued runs of the wrong length are redacted whole and never become the MBO
        ("MBO 12345678901", "MBO [MBO_REDACTED]", None),
        ("MBO 12345678", "MBO [MBO_REDACTED]", None),
        ("MBO 123 456 789 01", "MBO [MBO_REDACTED]", None),
        (
            "MBO je nula nula nula nula nula nula tri nula tri jedan",
            "MBO je [MBO_REDACTED]",
            None,
        ),
        ("MBO 000 000 301, tel 091 555 1234", "MBO [MBO_REDACTED], tel 091 555 1234", "000000301"),
        ("MBO 000 000 301 091 555 1234", "MBO [MBO_REDACTED]", None),
        (
            "MBO 12345678901, ispravak: MBO 123456789",
            "MBO [MBO_REDACTED], ispravak: MBO [MBO_REDACTED]",
            None,
        ),
        ("MBO ne znam, rođen 1950", "MBO ne znam, rođen 1950", None),
        # uncued behaviour unchanged
        ("tel 0915551234", "tel 0915551234", None),
        ("tel 091 555 1234", "tel 091 555 1234", None),
        ("Rođen 1950 053 123 456", "Rođen 1950 [MBO_REDACTED]", None),
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


def test_overlong_cued_number_is_not_sent_to_llm_and_flagged() -> None:
    spy = SpyLLMClient(delegate=MockLLMClient(response="{}"))
    result = extract_intake(
        text="MBO 12345678901.",
        llm_client=spy,
        geocoding_client=MockGeocodingClient(),
    )
    assert "12345678901" not in spy.calls[0][1]
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
