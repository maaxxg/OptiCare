"""Testovi za modul app.entitlement (HZZO pravila)."""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from app.db import get_db
from app.entitlement import (
    HZZORules,
    HZZORulesError,
    get_hzzo_rules,
    load_hzzo_rules_from_path,
    propose_entitlement,
)
from app.main import StartupCheckError, app, lifespan
from app.models import MobilityClass, VisitRequest, VisitType

REPO_ROOT = Path(__file__).resolve().parents[2]
HZZO_YAML_PATH = REPO_ROOT / "data" / "domain" / "hzzo_rules.yaml"


def test_load_real_hzzo_rules() -> None:
    rules = load_hzzo_rules_from_path(HZZO_YAML_PATH)
    assert isinstance(rules, HZZORules)

    # Sanitetski prijevoz
    assert len(rules.sanitetski.legal_criteria) > 0
    assert len(rules.sanitetski.by_mobility_class) > 0
    assert len(rules.sanitetski.issued_by) > 0
    assert all(
        hasattr(entry, "who") and hasattr(entry, "when") for entry in rules.sanitetski.issued_by
    )

    # Putni nalog
    assert len(rules.travel_order.conditions) > 0
    assert rules.travel_order.min_distance_km > 0
    band = rules.travel_order.distance.borderline_band_km
    assert len(band) == 2
    assert band[0] < band[1]
    assert rules.travel_order.place.separate_if_km_from_town > 0
    assert rules.travel_order.nearest_provider.rule != ""
    assert len(rules.travel_order.nearest_provider.manual_overrides) > 0
    assert len(rules.travel_order.distance_exceptions) > 0
    assert all(
        exc.key and exc.label and exc.system_check for exc in rules.travel_order.distance_exceptions
    )
    assert rules.travel_order.compensation.rate != ""
    assert rules.travel_order.compensation.approx_eur_per_km > 0
    assert isinstance(rules.travel_order.compensation.round_trip, bool)
    assert len(rules.travel_order.issued_by) > 0

    # Izvori
    assert len(rules.sources) > 0
    assert all(src.title and src.url for src in rules.sources)


def test_get_hzzo_rules_cached() -> None:
    get_hzzo_rules.cache_clear()
    first = get_hzzo_rules()
    second = get_hzzo_rules()
    assert first is second


def test_missing_file_raises_hzzo_rules_error(tmp_path: Path) -> None:
    non_existent = tmp_path / "does_not_exist.yaml"
    with pytest.raises(HZZORulesError, match="Cannot read HZZO rules YAML"):
        load_hzzo_rules_from_path(non_existent)


def test_malformed_yaml_raises_hzzo_rules_error(tmp_path: Path) -> None:
    bad_yaml = tmp_path / "malformed.yaml"
    bad_yaml.write_text("sanitetski: [invalid yaml: {", encoding="utf-8")
    with pytest.raises(HZZORulesError, match="Cannot read HZZO rules YAML"):
        load_hzzo_rules_from_path(bad_yaml)


def test_non_dict_yaml_raises_hzzo_rules_error(tmp_path: Path) -> None:
    bad_yaml = tmp_path / "list.yaml"
    bad_yaml.write_text("- item 1\n- item 2\n", encoding="utf-8")
    with pytest.raises(HZZORulesError, match="must be a mapping"):
        load_hzzo_rules_from_path(bad_yaml)


def test_extra_field_raises_hzzo_rules_error(tmp_path: Path) -> None:
    raw = yaml.safe_load(HZZO_YAML_PATH.read_text(encoding="utf-8"))
    raw["unexpected_top_level_field"] = "boom"
    bad_yaml = tmp_path / "extra.yaml"
    bad_yaml.write_text(yaml.dump(raw), encoding="utf-8")
    with pytest.raises(HZZORulesError, match="Invalid HZZO rules YAML"):
        load_hzzo_rules_from_path(bad_yaml)


def test_invalid_borderline_band_raises_hzzo_rules_error(tmp_path: Path) -> None:
    raw = yaml.safe_load(HZZO_YAML_PATH.read_text(encoding="utf-8"))
    raw["travel_order"]["distance"]["borderline_band_km"] = [55, 45]  # reversed
    bad_yaml = tmp_path / "bad_band.yaml"
    bad_yaml.write_text(yaml.dump(raw), encoding="utf-8")
    with pytest.raises(HZZORulesError, match="strictly less than max"):
        load_hzzo_rules_from_path(bad_yaml)


def test_invalid_borderline_band_length_raises_hzzo_rules_error(tmp_path: Path) -> None:
    raw = yaml.safe_load(HZZO_YAML_PATH.read_text(encoding="utf-8"))
    raw["travel_order"]["distance"]["borderline_band_km"] = [45]  # single element
    bad_yaml = tmp_path / "bad_band_len.yaml"
    bad_yaml.write_text(yaml.dump(raw), encoding="utf-8")
    with pytest.raises(HZZORulesError, match="borderline_band_km must contain exactly two numbers"):
        load_hzzo_rules_from_path(bad_yaml)


def test_missing_required_section_raises_hzzo_rules_error(tmp_path: Path) -> None:
    raw = yaml.safe_load(HZZO_YAML_PATH.read_text(encoding="utf-8"))
    del raw["sanitetski"]
    bad_yaml = tmp_path / "missing_section.yaml"
    bad_yaml.write_text(yaml.dump(raw), encoding="utf-8")
    with pytest.raises(HZZORulesError, match="Invalid HZZO rules YAML"):
        load_hzzo_rules_from_path(bad_yaml)


def test_broken_hzzo_rules_fail_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken() -> None:
        raise HZZORulesError("synthetic failure")

    monkeypatch.setattr("app.main.get_hzzo_rules", broken)

    async def run() -> None:
        async with lifespan(app):
            pass

    with pytest.raises(StartupCheckError, match="HZZO rules are invalid: synthetic failure"):
        asyncio.run(run())


# ---------------------------------------------------------------------------
# Testovi funkcije propose_entitlement
# ---------------------------------------------------------------------------


def test_propose_entitlement_sanitetski_for_wheelchair_and_stretcher() -> None:
    for m in (MobilityClass.WHEELCHAIR, MobilityClass.STRETCHER, "wheelchair", "stretcher"):
        res = propose_entitlement(
            mobility_class=m,
            birth_year=1980,
            visit_type=VisitType.FIRST_VISIT,
            distance_km=60.0,
            is_nearest_facility=True,
            reference_date=date(2026, 11, 14),
        )
        assert res.proposal == "sanitetski"
        assert res.flags == []
        assert res.distance_km == 60.0
        assert res.exceptions_applied == []
        assert res.order_data is None


def test_propose_entitlement_cane_flags_doctor_judgement_and_continues() -> None:
    res = propose_entitlement(
        mobility_class=MobilityClass.CANE,
        birth_year=1980,
        visit_type=VisitType.FIRST_VISIT,
        distance_km=60.0,
        is_nearest_facility=True,
        reference_date=date(2026, 11, 14),
    )
    assert res.proposal == "travel_order"
    assert any(f.code == "doctor_judgement" for f in res.flags)
    assert "liječnik" in next(f.text for f in res.flags if f.code == "doctor_judgement")
    assert res.order_data is not None
    assert res.order_data.distance_km_one_way == 60.0
    assert res.order_data.distance_km_round_trip == 120.0


def test_propose_entitlement_distance_unknown_sets_none_and_flags() -> None:
    res = propose_entitlement(
        mobility_class=MobilityClass.WALKS,
        birth_year=1980,
        visit_type=VisitType.FIRST_VISIT,
        distance_km=None,
        is_nearest_facility=True,
        reference_date=date(2026, 11, 14),
    )
    assert res.proposal == "none"
    assert any(f.code == "distance_unknown" for f in res.flags)
    assert res.order_data is None


def test_propose_entitlement_under_18_exception() -> None:
    # 2026 - 2012 = 14 god (< 18)
    res = propose_entitlement(
        mobility_class=MobilityClass.WALKS,
        birth_year=2012,
        visit_type=VisitType.FIRST_VISIT,
        distance_km=25.0,  # manje od 50 km
        is_nearest_facility=True,
        reference_date=date(2026, 11, 14),
    )
    assert res.proposal == "travel_order"
    assert "under_18" in res.exceptions_applied
    assert res.order_data is not None
    assert res.order_data.distance_km_one_way == 25.0
    assert res.order_data.distance_km_round_trip == 50.0


def test_propose_entitlement_chemotherapy_and_radiotherapy_exception() -> None:
    for v_type in (VisitType.CHEMOTHERAPY, VisitType.RADIOTHERAPY, "chemotherapy", "radiotherapy"):
        res = propose_entitlement(
            mobility_class=MobilityClass.WALKS,
            birth_year=1970,
            visit_type=v_type,
            distance_km=20.0,
            is_nearest_facility=True,
            reference_date=date(2026, 11, 14),
        )
        assert res.proposal == "travel_order"
        assert "radiotherapy_chemotherapy" in res.exceptions_applied
        assert res.order_data is not None


def test_propose_entitlement_dialysis_session_maps_to_hemodialysis() -> None:
    res = propose_entitlement(
        mobility_class=MobilityClass.WALKS,
        birth_year=1970,
        visit_type=VisitType.DIALYSIS_SESSION,
        distance_km=15.0,
        is_nearest_facility=True,
        reference_date=date(2026, 11, 14),
    )
    assert res.proposal == "travel_order"
    assert "hemodialysis" in res.exceptions_applied
    assert res.order_data is not None


def test_propose_entitlement_oncology_department_alone_not_exception() -> None:
    # Redovni pregled na onkologiji nije iznimka
    res = propose_entitlement(
        mobility_class=MobilityClass.WALKS,
        birth_year=1970,
        visit_type=VisitType.FOLLOW_UP,
        distance_km=30.0,  # < 50 km
        is_nearest_facility=True,
        department="oncology",
        reference_date=date(2026, 11, 14),
    )
    assert res.proposal == "none"
    assert res.exceptions_applied == []
    assert res.order_data is None


def test_propose_entitlement_borderline_band_below_threshold() -> None:
    # 48 km je u pojasu [45, 55], ali < 50 km bez iznimke
    res = propose_entitlement(
        mobility_class=MobilityClass.WALKS,
        birth_year=1970,
        visit_type=VisitType.FIRST_VISIT,
        distance_km=48.0,
        is_nearest_facility=True,
        reference_date=date(2026, 11, 14),
    )
    assert res.proposal == "none"
    assert any(f.code == "distance_borderline" for f in res.flags)
    borderline_flag = next(f for f in res.flags if f.code == "distance_borderline")
    assert "HAK" in borderline_flag.text
    assert res.order_data is None


def test_propose_entitlement_borderline_band_above_threshold() -> None:
    # 52 km je u pojasu [45, 55], i >= 50 km
    res = propose_entitlement(
        mobility_class=MobilityClass.WALKS,
        birth_year=1970,
        visit_type=VisitType.FIRST_VISIT,
        distance_km=52.0,
        is_nearest_facility=True,
        reference_date=date(2026, 11, 14),
    )
    assert res.proposal == "travel_order"
    assert any(f.code == "distance_borderline" for f in res.flags)
    assert res.order_data is not None
    assert res.order_data.distance_km_one_way == 52.0
    assert res.order_data.distance_km_round_trip == 104.0


def test_propose_entitlement_borderline_with_exception() -> None:
    # 48 km uz dijalizu -> travel_order uz borderline flag
    res = propose_entitlement(
        mobility_class=MobilityClass.WALKS,
        birth_year=1970,
        visit_type=VisitType.DIALYSIS_SESSION,
        distance_km=48.0,
        is_nearest_facility=True,
        reference_date=date(2026, 11, 14),
    )
    assert res.proposal == "travel_order"
    assert any(f.code == "distance_borderline" for f in res.flags)
    assert "hemodialysis" in res.exceptions_applied
    assert res.order_data is not None


def test_propose_entitlement_not_nearest_facility_denies_travel_order() -> None:
    res = propose_entitlement(
        mobility_class=MobilityClass.WALKS,
        birth_year=1970,
        visit_type=VisitType.FIRST_VISIT,
        distance_km=70.0,
        is_nearest_facility=False,
        reference_date=date(2026, 11, 14),
    )
    assert res.proposal == "none"
    assert any(f.code == "not_nearest_facility" for f in res.flags)
    flag = next(f for f in res.flags if f.code == "not_nearest_facility")
    assert "liječnik" in flag.text
    assert res.order_data is None


def test_propose_entitlement_order_data_calculation_and_metadata() -> None:
    res = propose_entitlement(
        mobility_class=MobilityClass.WALKS,
        birth_year=1985,
        visit_type=VisitType.FIRST_VISIT,
        distance_km=60.0,
        is_nearest_facility=True,
        patient_name="Marko Horvat",
        address="Ilica 10, Zagreb",
        facility_name="KBC Rebro",
        department="Kardiologija",
        appointment_date=date(2026, 12, 1),
        reference_date=date(2026, 11, 14),
    )
    assert res.proposal == "travel_order"
    assert res.order_data is not None
    assert res.order_data.patient_name == "Marko Horvat"
    assert res.order_data.address == "Ilica 10, Zagreb"
    assert res.order_data.facility_name == "KBC Rebro"
    assert res.order_data.department == "Kardiologija"
    assert res.order_data.appointment_date == date(2026, 12, 1)
    assert res.order_data.distance_km_one_way == 60.0
    assert res.order_data.distance_km_round_trip == 120.0
    # approx_eur_per_km iz YAML-a je 0.11 -> 0.11 * 120 = 13.20 €
    rules = get_hzzo_rules()
    expected_compensation = round(rules.travel_order.compensation.approx_eur_per_km * 120.0, 2)
    assert res.order_data.estimated_compensation_eur == expected_compensation
    assert res.order_data.issued_by == rules.travel_order.issued_by


# ---------------------------------------------------------------------------
# Testovi endpointa GET /entitlement/{request_id}
# ---------------------------------------------------------------------------


class _FakeDb:
    def __init__(self, objects: dict[Any, Any], scalars_result: Any = None) -> None:
        self._objects = objects
        self._scalars_result = scalars_result

    def get(self, model: type, key: int) -> Any:
        return self._objects.get((model, key))

    def scalars(self, stmt: Any) -> Any:
        class _Result:
            def __init__(self, item: Any) -> None:
                self._item = item

            def first(self) -> Any:
                return self._item

        return _Result(self._scalars_result)


def _fake_patient(
    lat: float | None = 44.55,
    lon: float | None = 15.37,
    mobility: str = "walks",
    birth_year: int = 1980,
    entitlement: str = "none",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        first_name="Ivan",
        last_name="Horvat",
        name="Ivan Horvat",
        address="Glavna 1, Gospić",
        birth_year=birth_year,
        mobility_class=mobility,
        transport_entitlement=entitlement,
        location=SimpleNamespace() if lat is not None else None,
        latitude=lat,
        longitude=lon,
    )


def _fake_facility(
    fac_id: int = 10,
    name: str = "Opća bolnica Gospić",
    lat: float | None = 44.54,
    lon: float | None = 15.36,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=fac_id,
        name=name,
        latitude=lat,
        longitude=lon,
    )


def _fake_request(
    patient: Any,
    facility: Any,
    department: str = "cardiology",
    visit_type: str = "first_visit",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=5,
        patient_id=patient.id,
        facility_id=facility.id,
        patient=patient,
        facility=facility,
        department=department,
        visit_type=visit_type,
        earliest_date=date(2026, 12, 1),
    )


def test_entitlement_endpoint_404_when_request_missing() -> None:
    app.dependency_overrides[get_db] = lambda: _FakeDb({})
    try:
        response = TestClient(app).get("/entitlement/999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Zahtjev nije pronađen."
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_entitlement_endpoint_returns_proposal_and_does_not_modify_db() -> None:
    # Pacijent u Gospiću (44.55, 15.37), bolnica u Zagrebu (45.81, 15.98) -> cca 150+ km
    patient = _fake_patient(44.55, 15.37, mobility="walks", entitlement="none")
    facility = _fake_facility(10, "KBC Zagreb", 45.81, 15.98)
    req = _fake_request(patient, facility)

    # Najbliža ustanova za tu djelatnost je upravo ta ustanova
    db = _FakeDb({(VisitRequest, 5): req}, scalars_result=facility)
    app.dependency_overrides[get_db] = lambda: db

    try:
        client = TestClient(app)
        response = client.get("/entitlement/5")
        assert response.status_code == 200
        body = response.json()
        assert body["proposal"] == "travel_order"
        assert body["distance_km"] > 50.0
        assert body["order_data"] is not None
        assert body["order_data"]["patient_name"] == "Ivan Horvat"
        assert body["order_data"]["facility_name"] == "KBC Zagreb"
        # Baza se ne smije mijenjati: transport_entitlement ostaje 'none'
        assert patient.transport_entitlement == "none"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_entitlement_endpoint_not_nearest_facility() -> None:
    # Pacijent u Gospiću, ciljana ustanova Zagreb, ali najbliža je Gospić
    patient = _fake_patient(44.55, 15.37, mobility="walks", entitlement="none")
    target_facility = _fake_facility(10, "KBC Zagreb", 45.81, 15.98)
    nearest_facility = _fake_facility(20, "OB Gospić", 44.54, 15.38)
    req = _fake_request(patient, target_facility)

    db = _FakeDb({(VisitRequest, 5): req}, scalars_result=nearest_facility)
    app.dependency_overrides[get_db] = lambda: db

    try:
        client = TestClient(app)
        response = client.get("/entitlement/5")
        assert response.status_code == 200
        body = response.json()
        assert body["proposal"] == "none"
        assert any(f["code"] == "not_nearest_facility" for f in body["flags"])
        assert patient.transport_entitlement == "none"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_entitlement_endpoint_sanitetski_for_wheelchair() -> None:
    patient = _fake_patient(44.55, 15.37, mobility="wheelchair", entitlement="none")
    facility = _fake_facility(10, "KBC Zagreb", 45.81, 15.98)
    req = _fake_request(patient, facility)

    db = _FakeDb({(VisitRequest, 5): req}, scalars_result=facility)
    app.dependency_overrides[get_db] = lambda: db

    try:
        client = TestClient(app)
        response = client.get("/entitlement/5")
        assert response.status_code == 200
        body = response.json()
        assert body["proposal"] == "sanitetski"
        assert patient.transport_entitlement == "none"
    finally:
        app.dependency_overrides.pop(get_db, None)
