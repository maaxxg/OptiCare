from __future__ import annotations

from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import yaml
from geoalchemy2.shape import to_shape
from shapely.geometry.base import BaseGeometry

from app.codebooks import get_urgency_max_shift_days
from app.config import get_settings
from app.models import (
    Department,
    MobilityClass,
    Patient,
    VehicleProviderType,
)
from app.seed import SETTLEMENT_COORDINATES, SeedBundle, build_seed_objects

PLAN_DATE = date(2026, 11, 16)


@pytest.fixture(scope="module")
def bundle() -> SeedBundle:
    return build_seed_objects(base_date=PLAN_DATE)


def _boundaries(bundle: SeedBundle) -> dict[str, BaseGeometry]:
    return {m.name: to_shape(m.boundary) for m in bundle.municipalities}


def test_patients_are_obviously_synthetic(bundle: SeedBundle) -> None:
    assert len(bundle.patients) == 18
    for p in bundle.patients:
        assert p.mbo.startswith("0000000"), p.key
        assert p.phone.startswith("+385 00 "), p.key
    for v in bundle.vehicles:
        assert v.driver_phone is not None and v.driver_phone.startswith("+385 00 "), v.key


def test_twelve_real_municipalities_cover_every_patient(bundle: SeedBundle) -> None:
    boundaries = _boundaries(bundle)
    assert len(boundaries) == 12
    for p in bundle.patients:
        assert p.municipality in boundaries, p.key
        assert p.location is not None, p.key
        assert boundaries[p.municipality].contains(to_shape(p.location)), p.key


def test_vehicle_bases_lie_in_their_municipality(bundle: SeedBundle) -> None:
    boundaries = _boundaries(bundle)
    for v in bundle.vehicles:
        assert v.base_municipality is not None
        assert boundaries[v.base_municipality].contains(to_shape(v.base_location)), v.key


def test_every_request_has_candidate_slots_in_its_window(bundle: SeedBundle) -> None:
    for req in bundle.visit_requests:
        assert len(req.candidate_slots) >= 2, req.patient.key
        for slot in req.candidate_slots:
            assert slot.facility is req.facility
            assert slot.department == req.department
            assert req.earliest_date <= slot.start_time.date() <= req.latest_date


def test_request_window_fits_urgency_class(bundle: SeedBundle) -> None:
    for req in bundle.visit_requests:
        span = (req.latest_date - req.earliest_date).days
        assert span <= get_urgency_max_shift_days(req.urgency_class), req.patient.key


def test_slots_are_local_time_and_no_oncology_in_gospic(bundle: SeedBundle) -> None:
    for slot in bundle.slots:
        assert slot.start_time.tzinfo == ZoneInfo("Europe/Zagreb")
        if slot.facility.key == "ob_gospic":
            assert slot.department != Department.ONCOLOGY.value
    gospic = {s.department for s in bundle.slots if s.facility.key == "ob_gospic"}
    assert gospic == {d.value for d in Department} - {Department.ONCOLOGY.value}


def test_fleet_matches_plan(bundle: SeedBundle) -> None:
    sanitetski_bases = {
        v.base_settlement
        for v in bundle.vehicles
        if v.provider_type == VehicleProviderType.SANITETSKI.value
    }
    assert sanitetski_bases == {"Gospić", "Otočac", "Senj", "Korenica", "Novalja"}
    types = {v.provider_type for v in bundle.vehicles}
    assert VehicleProviderType.RED_CROSS.value in types
    assert VehicleProviderType.MUNICIPAL.value in types


def test_patient_driver_cars_need_confirmed_documents(bundle: SeedBundle) -> None:
    by_patient = {v.patient_driver.key: v for v in bundle.vehicles if v.patient_driver is not None}
    assert len(by_patient) >= 2
    for p in bundle.patients:
        has_car = p.key in by_patient
        assert has_car == (
            p.own_car and p.carpool_driver_seats > 0 and p.driver_documents_confirmed
        )
        if has_car:
            assert by_patient[p.key].seats == p.carpool_driver_seats
            assert by_patient[p.key].provider_type == VehicleProviderType.PATIENT_DRIVER.value


def test_social_order_patients_are_mobile(bundle: SeedBundle) -> None:
    social: list[Patient] = [p for p in bundle.patients if p.social_order_today]
    assert len(social) >= 2
    for p in social:
        assert p.mobility_class == MobilityClass.WALKS.value


def test_lika_line_stops_have_coordinates() -> None:
    path = Path(get_settings().data_dir) / "domain" / "lika_line.yaml"
    lines = yaml.safe_load(path.read_text(encoding="utf-8"))["lines"]
    assert lines
    for line in lines:
        assert line["stops"][-1] == "Gospić"
        for stop in line["stops"]:
            assert stop in SETTLEMENT_COORDINATES, (line["key"], stop)
