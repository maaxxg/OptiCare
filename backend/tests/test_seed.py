from __future__ import annotations

from datetime import date

from app.models import (
    Department,
    MobilityClass,
    UrgencyClass,
    VehicleProviderType,
    VisitType,
)
from app.schemas import FacilityRead, MunicipalityRead, PatientRead, SlotRead, VehicleRead
from app.seed import build_seed_objects


def test_seed_municipalities_and_facilities() -> None:
    bundle = build_seed_objects(base_date=date(2026, 11, 14))

    assert len(bundle.municipalities) == 12
    muni_names = {m.name for m in bundle.municipalities}
    expected_munis = {
        "Gospić",
        "Otočac",
        "Senj",
        "Novalja",
        "Plitvička Jezera",
        "Perušić",
        "Udbina",
        "Brinje",
        "Karlobag",
        "Vrhovine",
        "Donji Lapac",
        "Lovinac",
    }
    assert muni_names == expected_munis

    for idx, m in enumerate(bundle.municipalities, start=1):
        m.id = idx
        read_m = MunicipalityRead.model_validate(m)
        assert read_m.county == "Ličko-senjska"
        assert read_m.population_65_plus_share is not None
        assert 0.15 < read_m.population_65_plus_share < 0.50

    assert len(bundle.facilities) == 3
    fac_keys = {f.key for f in bundle.facilities}
    assert fac_keys == {"ob_gospic", "kbc_rijeka", "kbc_zagreb"}
    for idx, f in enumerate(bundle.facilities, start=1):
        f.id = idx
        read_f = FacilityRead.model_validate(f)
        assert read_f.latitude is not None
        assert read_f.longitude is not None


def test_seed_patients_and_visit_requests_coverage() -> None:
    bundle = build_seed_objects(base_date=date(2026, 11, 14))

    assert 15 <= len(bundle.patients) <= 20
    assert len(bundle.patients) == 18
    assert len(bundle.visit_requests) == 18

    # Check coverage of mobility classes, departments, visit types, urgency classes
    mobilities = {p.mobility_class for p in bundle.patients}
    assert mobilities == {m.value for m in MobilityClass}

    departments = {r.department for r in bundle.visit_requests}
    assert departments == {d.value for d in Department}

    visit_types = {r.visit_type for r in bundle.visit_requests}
    assert visit_types == {vt.value for vt in VisitType}

    urgencies = {r.urgency_class for r in bundle.visit_requests}
    assert urgencies == {u.value for u in UrgencyClass}

    # Check patient-drivers accuracy (must walk, have valid docs, and volunteer_partner)
    drivers = [p for p in bundle.patients if p.own_car]
    assert len(drivers) >= 2
    for d in drivers:
        assert d.mobility_class == MobilityClass.WALKS.value
        assert d.carpool_consent is True
        assert d.carpool_driver_seats >= 1
        assert d.driver_registration_valid is True
        assert d.driver_insurance_valid is True
        assert d.driver_license_valid is True
        assert d.volunteer_partner is not None

    # Non-drivers must not claim driver seats
    for p in bundle.patients:
        if not p.own_car:
            assert p.carpool_driver_seats == 0
        if p.lives_alone:
            assert p.companion is False

    # Check social_order_today patients (mobile patients who would get sanitetski today for social reasons)
    social_orders = [p for p in bundle.patients if p.social_order_today]
    assert len(social_orders) >= 4
    for sp in social_orders:
        assert sp.mobility_class == MobilityClass.WALKS.value

    # Every VisitRequest must have candidate slots within [earliest_date, latest_date]
    for idx, p in enumerate(bundle.patients, start=1):
        p.id = idx
        read_p = PatientRead.model_validate(p)
        assert read_p.latitude is not None
        assert read_p.longitude is not None

    for req in bundle.visit_requests:
        assert len(req.candidate_slots) >= 2
        for slot in req.candidate_slots:
            assert slot.facility_key == req.facility_key
            assert slot.department == req.department
            assert req.earliest_date <= slot.start_time.date() <= req.latest_date


def test_seed_slots_and_vehicles() -> None:
    bundle = build_seed_objects(base_date=date(2026, 11, 14))

    # OB Gospić must have slots across all 8 departments for 2 days
    gospic_slots = [s for s in bundle.slots if s.facility_key == "ob_gospic"]
    gospic_dates = {s.start_time.date() for s in gospic_slots}
    assert len(gospic_dates) == 2
    gospic_depts = {s.department for s in gospic_slots}
    assert gospic_depts == {d.value for d in Department}

    for idx, s in enumerate(bundle.slots, start=1):
        s.id = idx
        SlotRead.model_validate(s)

    # Check vehicles: sanitetski across 5 branches (Gospić, Otočac, Senj, Korenica, Novalja),
    # Crveni križ, općinsko, Lika Line (javni_prijevoz), and pacijent_vozac
    sanitet_branches = {
        v.base_settlement
        for v in bundle.vehicles
        if v.provider_type == VehicleProviderType.SANITETSKI.value
    }
    assert sanitet_branches == {"Gospić", "Otočac", "Senj", "Korenica", "Novalja"}

    provider_types = {v.provider_type for v in bundle.vehicles}
    assert VehicleProviderType.SANITETSKI.value in provider_types
    assert VehicleProviderType.CRVENI_KRIZ.value in provider_types
    assert VehicleProviderType.OPCINSKI.value in provider_types
    assert VehicleProviderType.JAVNI_PRIJEVOZ.value in provider_types
    assert VehicleProviderType.PACIJENT_VOZAC.value in provider_types

    for idx, v in enumerate(bundle.vehicles, start=1):
        v.id = idx
        read_v = VehicleRead.model_validate(v)
        assert read_v.latitude is not None
        assert read_v.longitude is not None
