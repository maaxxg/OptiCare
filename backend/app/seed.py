from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.codebooks import get_visit_duration
from app.db import SessionLocal
from app.models import (
    Assignment,
    Department,
    Facility,
    MobilityClass,
    Municipality,
    Patient,
    PhoneType,
    RequestStatus,
    Slot,
    TransportEntitlement,
    TripLog,
    UrgencyClass,
    Vehicle,
    VehicleProviderType,
    VisitRequest,
    VisitType,
    make_multipolygon_wkt,
    make_point_wkt,
    visit_request_candidate_slots,
)

# Real WGS84 (lat, lon) coordinates for settlements in Ličko-senjska županija
# plus tertiary referral cities (Rijeka, Zagreb).
SETTLEMENT_COORDINATES: dict[str, tuple[float, float]] = {
    "Gospić": (44.5469, 15.3747),
    "Smiljan": (44.5639, 15.3114),
    "Lički Osik": (44.6036, 15.4244),
    "Otočac": (44.8694, 15.2375),
    "Kuterevo": (44.8264, 15.1408),
    "Švica": (44.8492, 15.1764),
    "Sinac": (44.8128, 15.3247),
    "Senj": (44.9894, 14.9058),
    "Jablanac": (44.7061, 14.8969),
    "Krasno Polje": (44.8211, 15.0519),
    "Novalja": (44.5567, 14.8867),
    "Metajna": (44.5022, 14.9969),
    "Korenica": (44.7453, 15.7069),
    "Plitvička Jezera": (44.8806, 15.6214),
    "Perušić": (44.6497, 15.3839),
    "Kosinj": (44.7408, 15.2764),
    "Udbina": (44.5314, 15.7661),
    "Brinje": (45.0025, 15.1339),
    "Karlobag": (44.5275, 15.0739),
    "Baške Oštarije": (44.5256, 15.1742),
    "Vrhovine": (44.8511, 15.4253),
    "Donji Lapac": (44.5522, 15.9611),
    "Lovinac": (44.3911, 15.6869),
    "Rijeka": (45.3312, 14.4267),
    "Zagreb": (45.8242, 16.0058),
}


def _box_multipolygon(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> str:
    """Create a valid closed MULTIPOLYGON WKT around a municipality bounding box."""
    return (
        f"MULTIPOLYGON((({min_lon} {min_lat}, {max_lon} {min_lat}, "
        f"{max_lon} {max_lat}, {min_lon} {max_lat}, {min_lon} {min_lat})))"
    )


# 12 administrative units (4 cities + 8 municipalities) of Ličko-senjska županija
MUNICIPALITIES_DATA: list[dict[str, Any]] = [
    {
        "name": "Gospić",
        "county": "Ličko-senjska",
        "population_65_plus_share": 0.238,
        "wkt": _box_multipolygon(15.15, 44.42, 15.55, 44.63),
    },
    {
        "name": "Otočac",
        "county": "Ličko-senjska",
        "population_65_plus_share": 0.254,
        "wkt": _box_multipolygon(15.08, 44.76, 15.38, 44.95),
    },
    {
        "name": "Senj",
        "county": "Ličko-senjska",
        "population_65_plus_share": 0.279,
        "wkt": _box_multipolygon(14.84, 44.68, 15.08, 45.05),
    },
    {
        "name": "Novalja",
        "county": "Ličko-senjska",
        "population_65_plus_share": 0.221,
        "wkt": _box_multipolygon(14.78, 44.48, 15.02, 44.68),
    },
    {
        "name": "Plitvička Jezera",
        "county": "Ličko-senjska",
        "population_65_plus_share": 0.265,
        "wkt": _box_multipolygon(15.55, 44.68, 15.85, 44.92),
    },
    {
        "name": "Perušić",
        "county": "Ličko-senjska",
        "population_65_plus_share": 0.292,
        "wkt": _box_multipolygon(15.22, 44.62, 15.50, 44.76),
    },
    {
        "name": "Udbina",
        "county": "Ličko-senjska",
        "population_65_plus_share": 0.334,
        "wkt": _box_multipolygon(15.62, 44.45, 15.88, 44.65),
    },
    {
        "name": "Brinje",
        "county": "Ličko-senjska",
        "population_65_plus_share": 0.301,
        "wkt": _box_multipolygon(15.02, 44.95, 15.28, 45.08),
    },
    {
        "name": "Karlobag",
        "county": "Ličko-senjska",
        "population_65_plus_share": 0.318,
        "wkt": _box_multipolygon(15.02, 44.44, 15.22, 44.62),
    },
    {
        "name": "Vrhovine",
        "county": "Ličko-senjska",
        "population_65_plus_share": 0.362,
        "wkt": _box_multipolygon(15.38, 44.78, 15.55, 44.90),
    },
    {
        "name": "Donji Lapac",
        "county": "Ličko-senjska",
        "population_65_plus_share": 0.348,
        "wkt": _box_multipolygon(15.88, 44.45, 16.12, 44.68),
    },
    {
        "name": "Lovinac",
        "county": "Ličko-senjska",
        "population_65_plus_share": 0.329,
        "wkt": _box_multipolygon(15.55, 44.32, 15.82, 44.45),
    },
]

FACILITIES_DATA: list[dict[str, Any]] = [
    {
        "key": "ob_gospic",
        "name": "Opća bolnica Gospić",
        "level": "secondary",
        "address": "Kaniška 111, 53000 Gospić",
        "settlement": "Gospić",
        "municipality": "Gospić",
        "county": "Ličko-senjska",
        "lat": 44.5447,
        "lon": 15.3664,
    },
    {
        "key": "kbc_rijeka",
        "name": "Klinički bolnički centar Rijeka",
        "level": "tertiary",
        "address": "Krešimirova 42, 51000 Rijeka",
        "settlement": "Rijeka",
        "municipality": "Rijeka",
        "county": "Primorsko-goranska",
        "lat": 45.3312,
        "lon": 14.4267,
    },
    {
        "key": "kbc_zagreb",
        "name": "Klinički bolnički centar Zagreb (Rebro)",
        "level": "tertiary",
        "address": "Kišpatićeva 12, 10000 Zagreb",
        "settlement": "Zagreb",
        "municipality": "Zagreb",
        "county": "Grad Zagreb",
        "lat": 45.8242,
        "lon": 16.0058,
    },
]

# Non-patient fleet: sanitetska vozila across branches (Gospić, Otočac, Senj, Korenica, Novalja),
# 1 Crveni križ vehicle, 1 municipal (općinsko) vehicle, and Lika Line public transit lines.
BASE_VEHICLES_DATA: list[dict[str, Any]] = [
    {
        "key": "sanitet_gospic_1",
        "name": "Sanitet Gospić 1 (nosila + kolica)",
        "provider_type": VehicleProviderType.SANITETSKI.value,
        "seats": 2,
        "wheelchair_spots": 1,
        "stretcher_spots": 1,
        "shift_start": time(6, 0),
        "shift_end": time(18, 0),
        "base_settlement": "Gospić",
        "base_municipality": "Gospić",
        "driver_name": "Marko Jurić",
        "driver_phone": "+385 91 500 1001",
        "has_driver_assistance": True,
    },
    {
        "key": "sanitet_gospic_2",
        "name": "Sanitet Gospić 2 (dijaliza i kolica)",
        "provider_type": VehicleProviderType.SANITETSKI.value,
        "seats": 3,
        "wheelchair_spots": 2,
        "stretcher_spots": 0,
        "shift_start": time(6, 0),
        "shift_end": time(18, 0),
        "base_settlement": "Gospić",
        "base_municipality": "Gospić",
        "driver_name": "Ivica Kovač",
        "driver_phone": "+385 91 500 1002",
        "has_driver_assistance": True,
    },
    {
        "key": "sanitet_otocac_1",
        "name": "Sanitet Otočac 1",
        "provider_type": VehicleProviderType.SANITETSKI.value,
        "seats": 3,
        "wheelchair_spots": 1,
        "stretcher_spots": 1,
        "shift_start": time(6, 30),
        "shift_end": time(16, 30),
        "base_settlement": "Otočac",
        "base_municipality": "Otočac",
        "driver_name": "Goran Barković",
        "driver_phone": "+385 91 500 1003",
        "has_driver_assistance": True,
    },
    {
        "key": "sanitet_senj_1",
        "name": "Sanitet Senj 1",
        "provider_type": VehicleProviderType.SANITETSKI.value,
        "seats": 2,
        "wheelchair_spots": 1,
        "stretcher_spots": 1,
        "shift_start": time(6, 30),
        "shift_end": time(16, 30),
        "base_settlement": "Senj",
        "base_municipality": "Senj",
        "driver_name": "Davor Nekić",
        "driver_phone": "+385 91 500 1004",
        "has_driver_assistance": True,
    },
    {
        "key": "sanitet_korenica_1",
        "name": "Sanitet Korenica 1",
        "provider_type": VehicleProviderType.SANITETSKI.value,
        "seats": 3,
        "wheelchair_spots": 1,
        "stretcher_spots": 0,
        "shift_start": time(6, 0),
        "shift_end": time(16, 0),
        "base_settlement": "Korenica",
        "base_municipality": "Plitvička Jezera",
        "driver_name": "Milan Bićanić",
        "driver_phone": "+385 91 500 1005",
        "has_driver_assistance": True,
    },
    {
        "key": "sanitet_novalja_1",
        "name": "Sanitet Novalja 1",
        "provider_type": VehicleProviderType.SANITETSKI.value,
        "seats": 3,
        "wheelchair_spots": 1,
        "stretcher_spots": 0,
        "shift_start": time(7, 0),
        "shift_end": time(17, 0),
        "base_settlement": "Novalja",
        "base_municipality": "Novalja",
        "driver_name": "Šime Dabo",
        "driver_phone": "+385 91 500 1006",
        "has_driver_assistance": True,
    },
    {
        "key": "crveni_kriz_gospic_1",
        "name": "Crveni križ Gospić — kombi",
        "provider_type": VehicleProviderType.CRVENI_KRIZ.value,
        "seats": 5,
        "wheelchair_spots": 1,
        "stretcher_spots": 0,
        "shift_start": time(7, 0),
        "shift_end": time(15, 30),
        "base_settlement": "Gospić",
        "base_municipality": "Gospić",
        "driver_name": "Tomislav Starčević (CK)",
        "driver_phone": "+385 91 500 2001",
        "has_driver_assistance": True,
    },
    {
        "key": "opcinsko_vozilo_perusic_1",
        "name": "Općinsko vozilo Perušić / Udbina",
        "provider_type": VehicleProviderType.OPCINSKI.value,
        "seats": 4,
        "wheelchair_spots": 0,
        "stretcher_spots": 0,
        "shift_start": time(7, 0),
        "shift_end": time(15, 0),
        "base_settlement": "Perušić",
        "base_municipality": "Perušić",
        "driver_name": "Josip Kasumović",
        "driver_phone": "+385 91 500 3001",
        "has_driver_assistance": True,
    },
    {
        "key": "lika_line_udbina_gospic",
        "name": "Lika Line LL-1 (Donji Lapac – Udbina – Gospić)",
        "provider_type": VehicleProviderType.JAVNI_PRIJEVOZ.value,
        "seats": 16,
        "wheelchair_spots": 0,
        "stretcher_spots": 0,
        "shift_start": time(6, 30),
        "shift_end": time(15, 30),
        "base_settlement": "Donji Lapac",
        "base_municipality": "Donji Lapac",
        "driver_name": "Lika Line (linija LL-1)",
        "driver_phone": "+385 53 572 100",
        "has_driver_assistance": False,
    },
    {
        "key": "lika_line_otocac_gospic",
        "name": "Lika Line LL-2 (Brinje – Otočac – Perušić – Gospić)",
        "provider_type": VehicleProviderType.JAVNI_PRIJEVOZ.value,
        "seats": 16,
        "wheelchair_spots": 0,
        "stretcher_spots": 0,
        "shift_start": time(6, 45),
        "shift_end": time(16, 0),
        "base_settlement": "Brinje",
        "base_municipality": "Brinje",
        "driver_name": "Lika Line (linija LL-2)",
        "driver_phone": "+385 53 572 101",
        "has_driver_assistance": False,
    },
    {
        "key": "lika_line_lovinac_gospic",
        "name": "Lika Line LL-3 (Lovinac – Gospić)",
        "provider_type": VehicleProviderType.JAVNI_PRIJEVOZ.value,
        "seats": 14,
        "wheelchair_spots": 0,
        "stretcher_spots": 0,
        "shift_start": time(7, 0),
        "shift_end": time(14, 30),
        "base_settlement": "Lovinac",
        "base_municipality": "Lovinac",
        "driver_name": "Lika Line (linija LL-3)",
        "driver_phone": "+385 53 572 102",
        "has_driver_assistance": False,
    },
]


def _default_patient_profiles_path() -> Path:
    """Locate data/domain/patient_profiles.yaml relative to backend/app/seed.py."""
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data" / "domain" / "patient_profiles.yaml"


def load_patient_profiles(yaml_path: Path | str | None = None) -> list[dict[str, Any]]:
    """Load the 18 synthetic patient profiles from YAML."""
    path = Path(yaml_path) if yaml_path else _default_patient_profiles_path()
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    patients = raw.get("patients", [])
    if not isinstance(patients, list) or not patients:
        raise ValueError(f"No patients found in {path}")
    return patients


def get_settlement_coords(settlement: str, index_offset: int = 0) -> tuple[float, float]:
    """Return (lat, lon) for a settlement with a tiny deterministic offset per patient."""
    base_lat, base_lon = SETTLEMENT_COORDINATES.get(
        settlement, SETTLEMENT_COORDINATES["Gospić"]
    )
    if index_offset == 0:
        return base_lat, base_lon
    # Deterministic ~100m-300m jitter so patients in the same settlement have distinct points
    d_lat = ((index_offset % 5) - 2) * 0.0012
    d_lon = (((index_offset // 2) % 5) - 2) * 0.0015
    return round(base_lat + d_lat, 6), round(base_lon + d_lon, 6)


@dataclass
class SeedBundle:
    """In-memory collection of all seeded entities (useful for both DB seeding and unit tests)."""

    base_date: date
    municipalities: list[Municipality]
    facilities: list[Facility]
    slots: list[Slot]
    patients: list[Patient]
    visit_requests: list[VisitRequest]
    vehicles: list[Vehicle]


def build_seed_objects(
    base_date: date | None = None,
    yaml_path: Path | str | None = None,
) -> SeedBundle:
    """Construct all ORM objects for E1-T3 demo seed data."""
    plan_base_date = base_date or date.today()

    # 1. Municipalities with PostGIS MultiPolygon boundaries
    municipalities: list[Municipality] = []
    for m_data in MUNICIPALITIES_DATA:
        municipalities.append(
            Municipality(
                name=m_data["name"],
                county=m_data["county"],
                population_65_plus_share=m_data["population_65_plus_share"],
                boundary=make_multipolygon_wkt(m_data["wkt"]),
            )
        )

    # 2. Facilities
    facilities: list[Facility] = []
    facilities_by_key: dict[str, Facility] = {}
    for f_data in FACILITIES_DATA:
        fac = Facility(
            key=f_data["key"],
            name=f_data["name"],
            level=f_data["level"],
            address=f_data["address"],
            settlement=f_data["settlement"],
            municipality=f_data["municipality"],
            county=f_data["county"],
            location=make_point_wkt(f_data["lat"], f_data["lon"]),
        )
        facilities.append(fac)
        facilities_by_key[fac.key] = fac

    # 3. Slots:
    # - Opća bolnica Gospić (ob_gospic): all 8 departments across 2 days (day+1 and day+2)
    #   with multiple morning/midday slots per department.
    # - KBC Rijeka (kbc_rijeka): cardiology & oncology slots across day+1 and day+2.
    # - KBC Zagreb (kbc_zagreb): neurology slots across day+1 and day+2.
    slots: list[Slot] = []
    ob_gospic = facilities_by_key["ob_gospic"]
    gospic_slot_hours: dict[str, list[tuple[int, int]]] = {
        Department.INTERNAL_MEDICINE.value: [(8, 30), (10, 0), (11, 30), (13, 0)],
        Department.CARDIOLOGY.value: [(8, 30), (9, 30), (11, 0), (12, 30)],
        Department.OPHTHALMOLOGY.value: [(8, 30), (9, 30), (10, 30), (12, 0)],
        Department.ORTHOPAEDICS.value: [(9, 0), (10, 30), (12, 0)],
        Department.NEUROLOGY.value: [(8, 30), (10, 0), (11, 30)],
        Department.RADIOLOGY.value: [(8, 0), (9, 30), (11, 0), (13, 0)],
        Department.ONCOLOGY.value: [(8, 30), (10, 30), (12, 30)],
        Department.DIALYSIS.value: [(7, 30), (12, 30)],
    }

    for day_offset in (1, 2):
        slot_date = plan_base_date + timedelta(days=day_offset)
        for dept, hm_list in gospic_slot_hours.items():
            default_vtype = (
                VisitType.DIALYSIS_SESSION.value
                if dept == Department.DIALYSIS.value
                else VisitType.FOLLOW_UP.value
            )
            dur = get_visit_duration(dept, default_vtype)
            for hour, minute in hm_list:
                start_dt = datetime.combine(slot_date, time(hour, minute), tzinfo=UTC)
                end_dt = start_dt + timedelta(minutes=dur.median_min)
                slots.append(
                    Slot(
                        facility=ob_gospic,
                        facility_key=ob_gospic.key,
                        facility_name=ob_gospic.name,
                        facility_location=ob_gospic.location,
                        department=dept,
                        start_time=start_dt,
                        end_time=end_dt,
                        capacity=4 if dept == Department.DIALYSIS.value else 2,
                    )
                )

    # Out-of-county referral slots (KBC Rijeka and KBC Zagreb) across 2 days
    external_slot_specs = [
        ("kbc_rijeka", Department.CARDIOLOGY.value, VisitType.PROCEDURE_TEST.value, [(9, 30), (11, 0)]),
        ("kbc_rijeka", Department.ONCOLOGY.value, VisitType.FOLLOW_UP.value, [(9, 30), (11, 30)]),
        ("kbc_zagreb", Department.NEUROLOGY.value, VisitType.FIRST_VISIT.value, [(10, 0), (12, 0)]),
    ]
    for day_offset in (1, 2):
        slot_date = plan_base_date + timedelta(days=day_offset)
        for fac_key, dept, vtype, hm_list in external_slot_specs:
            fac = facilities_by_key[fac_key]
            dur = get_visit_duration(dept, vtype)
            for hour, minute in hm_list:
                start_dt = datetime.combine(slot_date, time(hour, minute), tzinfo=UTC)
                end_dt = start_dt + timedelta(minutes=dur.median_min)
                slots.append(
                    Slot(
                        facility=fac,
                        facility_key=fac.key,
                        facility_name=fac.name,
                        facility_location=fac.location,
                        department=dept,
                        start_time=start_dt,
                        end_time=end_dt,
                        capacity=2,
                    )
                )

    # 4. Patients & VisitRequests
    raw_profiles = load_patient_profiles(yaml_path)
    patients: list[Patient] = []
    visit_requests: list[VisitRequest] = []

    for idx, prof in enumerate(raw_profiles, start=1):
        settlement = prof["settlement"]
        lat, lon = get_settlement_coords(settlement, index_offset=idx)
        patient = Patient(
            key=prof["key"],
            first_name=prof["first_name"],
            last_name=prof["last_name"],
            birth_year=prof.get("birth_year"),
            mbo=str(prof["mbo"]),
            phone=prof["phone"],
            phone_type=PhoneType(prof["phone_type"]).value,
            address=f"{settlement} {idx}",
            settlement=settlement,
            municipality=prof["municipality"],
            county=prof.get("county", "Ličko-senjska"),
            location=make_point_wkt(lat, lon),
            mobility_class=MobilityClass(prof["mobility_class"]).value,
            lives_alone=bool(prof.get("lives_alone", False)),
            companion=bool(prof.get("companion", False)),
            floor=int(prof.get("floor", 0)),
            elevator=bool(prof.get("elevator", False)),
            transport_entitlement=TransportEntitlement(
                prof["expected_transport_entitlement"]
            ).value,
            social_order_today=bool(prof.get("social_order_today", False)),
            own_car=bool(prof.get("own_car", False)),
            carpool_driver_seats=int(prof.get("carpool_driver_seats", 0)),
            carpool_consent=bool(prof.get("carpool_consent", False)),
            driver_registration_valid=bool(prof.get("driver_registration_valid", False)),
            driver_insurance_valid=bool(prof.get("driver_insurance_valid", False)),
            driver_license_valid=bool(prof.get("driver_license_valid", False)),
            volunteer_partner=prof.get("volunteer_partner"),
            missed_visits_last_year=int(prof.get("missed_visits_last_year", 0)),
            consent_given=bool(prof.get("consent_given", True)),
            story=prof.get("story"),
        )
        patients.append(patient)

        v_spec = prof["visit"]
        fac_key = v_spec["destination"]
        fac = facilities_by_key[fac_key]
        dept = Department(v_spec["department"]).value
        vtype = VisitType(v_spec["visit_type"]).value
        uclass = UrgencyClass(v_spec["urgency_class"]).value
        earliest_dt = plan_base_date + timedelta(days=int(v_spec["earliest_offset_days"]))
        latest_dt = plan_base_date + timedelta(days=int(v_spec["latest_offset_days"]))

        matching_slots = [
            s
            for s in slots
            if s.facility_key == fac_key
            and s.department == dept
            and earliest_dt <= s.start_time.date() <= latest_dt
        ]

        req = VisitRequest(
            patient=patient,
            referral_ref=f"UPUT-{prof['key'].upper()}-{plan_base_date.strftime('%Y%m%d')}",
            facility=fac,
            facility_key=fac_key,
            department=dept,
            visit_type=vtype,
            urgency_class=uclass,
            earliest_date=earliest_dt,
            latest_date=latest_dt,
            recurrence=v_spec.get("recurrence"),
            status=RequestStatus.OPEN.value,
            candidate_slots=matching_slots,
        )
        visit_requests.append(req)

    # 5. Vehicles: Base fleet + Patient-driver vehicles (pacijent_vozac)
    vehicles: list[Vehicle] = []
    for v_data in BASE_VEHICLES_DATA:
        b_lat, b_lon = SETTLEMENT_COORDINATES[v_data["base_settlement"]]
        vehicles.append(
            Vehicle(
                key=v_data["key"],
                name=v_data["name"],
                provider_type=v_data["provider_type"],
                seats=v_data["seats"],
                wheelchair_spots=v_data["wheelchair_spots"],
                stretcher_spots=v_data["stretcher_spots"],
                shift_start=v_data["shift_start"],
                shift_end=v_data["shift_end"],
                base_settlement=v_data["base_settlement"],
                base_municipality=v_data["base_municipality"],
                base_location=make_point_wkt(b_lat, b_lon),
                driver_name=v_data["driver_name"],
                driver_phone=v_data["driver_phone"],
                has_driver_assistance=v_data["has_driver_assistance"],
                active=True,
            )
        )

    for patient in patients:
        if patient.own_car and patient.carpool_consent and patient.carpool_driver_seats > 0:
            vehicles.append(
                Vehicle(
                    key=f"pacijent_vozac_{patient.key}",
                    name=f"Osobni auto — {patient.name} ({patient.settlement})",
                    provider_type=VehicleProviderType.PACIJENT_VOZAC.value,
                    seats=patient.carpool_driver_seats,
                    wheelchair_spots=0,
                    stretcher_spots=0,
                    shift_start=time(7, 0),
                    shift_end=time(16, 0),
                    base_settlement=patient.settlement,
                    base_municipality=patient.municipality,
                    base_location=patient.location,
                    driver_name=patient.name,
                    driver_phone=patient.phone,
                    patient_driver=patient,
                    has_driver_assistance=False,
                    active=True,
                )
            )

    return SeedBundle(
        base_date=plan_base_date,
        municipalities=municipalities,
        facilities=facilities,
        slots=slots,
        patients=patients,
        visit_requests=visit_requests,
        vehicles=vehicles,
    )


def seed_database(
    session: Session,
    base_date: date | None = None,
    yaml_path: Path | str | None = None,
) -> dict[str, int]:
    """Delete all existing demo data and repopulate the database cleanly."""
    # Delete in reverse foreign-key order
    session.execute(delete(TripLog))
    session.execute(delete(Assignment))
    session.execute(delete(visit_request_candidate_slots))
    session.execute(delete(VisitRequest))
    session.execute(delete(Slot))
    session.execute(delete(Vehicle))
    session.execute(delete(Patient))
    session.execute(delete(Facility))
    session.execute(delete(Municipality))
    session.flush()

    bundle = build_seed_objects(base_date=base_date, yaml_path=yaml_path)

    session.add_all(bundle.municipalities)
    session.add_all(bundle.facilities)
    session.add_all(bundle.slots)
    session.add_all(bundle.patients)
    session.add_all(bundle.visit_requests)
    session.add_all(bundle.vehicles)
    session.commit()

    return {
        "municipalities": len(bundle.municipalities),
        "facilities": len(bundle.facilities),
        "slots": len(bundle.slots),
        "patients": len(bundle.patients),
        "visit_requests": len(bundle.visit_requests),
        "vehicles": len(bundle.vehicles),
    }


def main() -> None:
    with SessionLocal() as session:
        counts = seed_database(session)
        print("OptiCare demo database seeded successfully:", counts)


if __name__ == "__main__":
    main()
