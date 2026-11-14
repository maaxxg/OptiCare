"""Demo seed data for Ličko-senjska županija (E1-T3).

Run: `uv run python -m app.seed` (backend dir) or `docker compose exec backend python -m app.seed`.
Deletes all rows in the domain tables and inserts the demo data again (including the synthetic
TripLog history from `app.synthetic_trips`), so it can be re-run.
All people are synthetic (rule 4). Geography is public: municipality boundaries, settlement and
hospital coordinates come from OpenStreetMap (see data/geo/README.md).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml
from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.codebooks import get_visit_duration
from app.config import get_settings
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
from app.synthetic_trips import generate_synthetic_trip_logs

logger = logging.getLogger(__name__)

ZAGREB = ZoneInfo("Europe/Zagreb")
COUNTY = "Ličko-senjska"

PATIENT_PROFILES_PATH = Path("domain") / "patient_profiles.yaml"
MUNICIPALITIES_GEOJSON_PATH = Path("geo") / "lika_senj_municipalities.geojson"

# Settlement centres (lat, lon) from OpenStreetMap place nodes.
SETTLEMENT_COORDINATES: dict[str, tuple[float, float]] = {
    "Baške Oštarije": (44.52694, 15.17603),
    "Brinje": (44.99981, 15.13127),
    "Donji Kosinj": (44.75986, 15.24962),
    "Donji Lapac": (44.55213, 15.96096),
    "Gospić": (44.5464, 15.37542),
    "Jablanac": (44.70625, 14.89778),
    "Karlobag": (44.52792, 15.0725),
    "Korenica": (44.74386, 15.70656),
    "Kuterevo": (44.82659, 15.13895),
    "Lički Osik": (44.60256, 15.41026),
    "Lovinac": (44.39088, 15.68644),
    "Novalja": (44.55612, 14.88447),
    "Otočac": (44.8688, 15.23587),
    "Perušić": (44.65002, 15.38326),
    "Senj": (44.99015, 14.90212),
    "Smiljan": (44.56175, 15.3214),
    "Udbina": (44.53175, 15.76652),
    "Vrhovine": (44.85176, 15.42057),
}

# REVIEW: estimates, not census figures; replace with DZS 2021 data before use in forecasting.
MUNICIPALITY_65_PLUS_SHARE: dict[str, float] = {
    "Brinje": 0.301,
    "Donji Lapac": 0.348,
    "Gospić": 0.238,
    "Karlobag": 0.318,
    "Lovinac": 0.329,
    "Novalja": 0.221,
    "Otočac": 0.254,
    "Perušić": 0.292,
    "Plitvička Jezera": 0.265,
    "Senj": 0.279,
    "Udbina": 0.334,
    "Vrhovine": 0.362,
}

# Hospital coordinates from OpenStreetMap.
FACILITIES_DATA: list[dict[str, Any]] = [
    {
        "key": "ob_gospic",
        "name": "Opća bolnica Gospić",
        "level": "secondary",
        "address": "Kaniška ulica 111, 53000 Gospić",
        "settlement": "Gospić",
        "municipality": "Gospić",
        "county": COUNTY,
        "lat": 44.5435,
        "lon": 15.36214,
    },
    {
        "key": "kbc_rijeka",
        "name": "Klinički bolnički centar Rijeka",
        "level": "tertiary",
        "address": "Krešimirova ulica 42, 51000 Rijeka",
        "settlement": "Rijeka",
        "municipality": "Rijeka",
        "county": "Primorsko-goranska",
        "lat": 45.33236,
        "lon": 14.42744,
    },
    {
        "key": "kbc_zagreb",
        "name": "Klinički bolnički centar Zagreb",
        "level": "tertiary",
        "address": "Kišpatićeva ulica 12, 10000 Zagreb",
        "settlement": "Zagreb",
        "municipality": "Zagreb",
        "county": "Grad Zagreb",
        "lat": 45.82458,
        "lon": 16.0063,
    },
]

# Slot start times per department, on plan day +1 and +2.
# OB Gospić has every department except oncology; oncology goes to KBC Rijeka.
SLOT_TIMES: dict[str, dict[Department, list[time]]] = {
    "ob_gospic": {
        Department.INTERNAL_MEDICINE: [time(8, 30), time(10, 0), time(11, 30), time(13, 0)],
        Department.CARDIOLOGY: [time(8, 30), time(9, 30), time(11, 0), time(12, 30)],
        Department.OPHTHALMOLOGY: [time(8, 30), time(9, 30), time(10, 30), time(12, 0)],
        Department.ORTHOPAEDICS: [time(9, 0), time(10, 30), time(12, 0)],
        Department.NEUROLOGY: [time(8, 30), time(10, 0), time(11, 30)],
        Department.RADIOLOGY: [time(8, 0), time(9, 30), time(11, 0), time(13, 0)],
        Department.DIALYSIS: [time(7, 30), time(12, 30)],
    },
    "kbc_rijeka": {
        Department.CARDIOLOGY: [time(9, 30), time(11, 0)],
        Department.ONCOLOGY: [time(9, 30), time(11, 30)],
    },
    "kbc_zagreb": {
        Department.NEUROLOGY: [time(10, 0), time(12, 0)],
    },
}
SLOT_DAY_OFFSETS = (1, 2)
# Slot length = median duration of the department's typical visit type (codebooks).
SLOT_VISIT_TYPE: dict[Department, VisitType] = {
    Department.DIALYSIS: VisitType.DIALYSIS_SESSION,
    Department.RADIOLOGY: VisitType.PROCEDURE_TEST,
}

# Fleet: sanitetska vozila by ispostava, one Red Cross van, one municipal vehicle.
# Driver names are invented; phone numbers are obviously fake.
BASE_VEHICLES_DATA: list[dict[str, Any]] = [
    {
        "key": "sanitet_gospic_1",
        "name": "Sanitet Gospić 1",
        "provider_type": VehicleProviderType.SANITETSKI,
        "seats": 2,
        "wheelchair_spots": 1,
        "stretcher_spots": 1,
        "shift": (time(6, 0), time(18, 0)),
        "base_settlement": "Gospić",
        "base_municipality": "Gospić",
        "driver_name": "Marko Jurić",
    },
    {
        "key": "sanitet_gospic_2",
        "name": "Sanitet Gospić 2",
        "provider_type": VehicleProviderType.SANITETSKI,
        "seats": 3,
        "wheelchair_spots": 2,
        "stretcher_spots": 0,
        "shift": (time(6, 0), time(18, 0)),
        "base_settlement": "Gospić",
        "base_municipality": "Gospić",
        "driver_name": "Ivica Kovač",
    },
    {
        "key": "sanitet_otocac_1",
        "name": "Sanitet Otočac 1",
        "provider_type": VehicleProviderType.SANITETSKI,
        "seats": 3,
        "wheelchair_spots": 1,
        "stretcher_spots": 1,
        "shift": (time(6, 30), time(16, 30)),
        "base_settlement": "Otočac",
        "base_municipality": "Otočac",
        "driver_name": "Goran Barković",
    },
    {
        "key": "sanitet_senj_1",
        "name": "Sanitet Senj 1",
        "provider_type": VehicleProviderType.SANITETSKI,
        "seats": 2,
        "wheelchair_spots": 1,
        "stretcher_spots": 1,
        "shift": (time(6, 30), time(16, 30)),
        "base_settlement": "Senj",
        "base_municipality": "Senj",
        "driver_name": "Davor Nekić",
    },
    {
        "key": "sanitet_korenica_1",
        "name": "Sanitet Korenica 1",
        "provider_type": VehicleProviderType.SANITETSKI,
        "seats": 3,
        "wheelchair_spots": 1,
        "stretcher_spots": 0,
        "shift": (time(6, 0), time(16, 0)),
        "base_settlement": "Korenica",
        "base_municipality": "Plitvička Jezera",
        "driver_name": "Milan Bićanić",
    },
    {
        "key": "sanitet_novalja_1",
        "name": "Sanitet Novalja 1",
        "provider_type": VehicleProviderType.SANITETSKI,
        "seats": 3,
        "wheelchair_spots": 1,
        "stretcher_spots": 0,
        "shift": (time(7, 0), time(17, 0)),
        "base_settlement": "Novalja",
        "base_municipality": "Novalja",
        "driver_name": "Šime Dabo",
    },
    {
        "key": "crveni_kriz_gospic_1",
        "name": "Crveni križ Gospić, kombi",
        "provider_type": VehicleProviderType.RED_CROSS,
        "seats": 5,
        "wheelchair_spots": 1,
        "stretcher_spots": 0,
        "shift": (time(7, 0), time(15, 30)),
        "base_settlement": "Gospić",
        "base_municipality": "Gospić",
        "driver_name": "Tomislav Starčević",
    },
    {
        "key": "opcinsko_perusic_1",
        "name": "Općinsko vozilo Perušić",
        "provider_type": VehicleProviderType.MUNICIPAL,
        "seats": 4,
        "wheelchair_spots": 0,
        "stretcher_spots": 0,
        "shift": (time(7, 0), time(15, 0)),
        "base_settlement": "Perušić",
        "base_municipality": "Perušić",
        "driver_name": "Josip Kasumović",
    },
]

# Patient-driver cars are available for the day of the driver's own visit.
PATIENT_DRIVER_SHIFT = (time(7, 0), time(16, 0))


def settlement_point(
    settlement: str, jitter_index: int = 0, within: BaseGeometry | None = None
) -> tuple[float, float]:
    """(lat, lon) of a settlement, shifted by up to ~300 m so patients get distinct points.

    If the shifted point falls outside `within` (e.g. into the sea), the centre is used.
    """
    try:
        lat, lon = SETTLEMENT_COORDINATES[settlement]
    except KeyError as exc:
        raise ValueError(f"No coordinates for settlement {settlement!r}") from exc
    if jitter_index == 0:
        return lat, lon
    d_lat = ((jitter_index % 5) - 2) * 0.0012
    d_lon = (((jitter_index // 2) % 5) - 2) * 0.0015
    j_lat, j_lon = round(lat + d_lat, 6), round(lon + d_lon, 6)
    if within is not None and not within.contains(Point(j_lon, j_lat)):
        return lat, lon
    return j_lat, j_lon


def load_patient_profiles(path: Path) -> list[dict[str, Any]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    patients = raw.get("patients") if isinstance(raw, dict) else None
    if not isinstance(patients, list) or not patients:
        raise ValueError(f"No patients found in {path}")
    return patients


def load_municipality_boundaries(path: Path) -> dict[str, BaseGeometry]:
    """Municipality name -> MULTIPOLYGON geometry."""
    collection = json.loads(path.read_text(encoding="utf-8"))
    return {
        feature["properties"]["name"]: shape(feature["geometry"])
        for feature in collection["features"]
    }


@dataclass
class SeedBundle:
    """All seeded ORM objects, before they are added to a session."""

    base_date: date
    municipalities: list[Municipality]
    facilities: list[Facility]
    slots: list[Slot]
    patients: list[Patient]
    visit_requests: list[VisitRequest]
    vehicles: list[Vehicle]
    trip_logs: list[TripLog]


def _build_slots(facilities: dict[str, Facility], base_date: date) -> list[Slot]:
    slots: list[Slot] = []
    for day_offset in SLOT_DAY_OFFSETS:
        slot_date = base_date + timedelta(days=day_offset)
        for facility_key, departments in SLOT_TIMES.items():
            for department, start_times in departments.items():
                visit_type = SLOT_VISIT_TYPE.get(department, VisitType.FOLLOW_UP)
                duration = get_visit_duration(department, visit_type)
                for start in start_times:
                    start_dt = datetime.combine(slot_date, start, tzinfo=ZAGREB)
                    slots.append(
                        Slot(
                            facility=facilities[facility_key],
                            department=department.value,
                            start_time=start_dt,
                            end_time=start_dt + timedelta(minutes=duration.median_min),
                            capacity=4 if department == Department.DIALYSIS else 2,
                        )
                    )
    return slots


def _build_patient(
    index: int, profile: dict[str, Any], boundaries: dict[str, BaseGeometry]
) -> Patient:
    lat, lon = settlement_point(
        profile["settlement"], jitter_index=index, within=boundaries.get(profile["municipality"])
    )
    own_car = bool(profile.get("own_car", False))
    carpool_consent = bool(profile.get("carpool_consent", False))
    return Patient(
        key=profile["key"],
        first_name=profile["first_name"],
        last_name=profile["last_name"],
        birth_year=profile.get("birth_year"),
        mbo=str(profile["mbo"]),
        phone=profile["phone"],
        phone_type=PhoneType(profile["phone_type"]).value,
        # Synthetic data has no streets or house numbers.
        address=profile["settlement"],
        settlement=profile["settlement"],
        municipality=profile["municipality"],
        county=profile.get("county", COUNTY),
        location=make_point_wkt(lat, lon),
        mobility_class=MobilityClass(profile["mobility_class"]).value,
        lives_alone=bool(profile.get("lives_alone", False)),
        companion=bool(profile.get("companion", False)),
        floor=int(profile.get("floor", 0)),
        elevator=bool(profile.get("elevator", False)),
        # A proposal only; the chosen doctor decides (rule 8).
        transport_entitlement=TransportEntitlement(profile["expected_transport_entitlement"]).value,
        social_order_today=bool(profile.get("social_order_today", False)),
        own_car=own_car,
        carpool_driver_seats=int(profile.get("carpool_driver_seats", 0)),
        carpool_rider_consent=carpool_consent and not own_car,
        driver_documents_confirmed=bool(profile.get("driver_documents_confirmed", False)),
        missed_visits_last_year=int(profile.get("missed_visits_last_year", 0)),
    )


def _build_visit_request(
    patient: Patient,
    visit: dict[str, Any],
    facilities: dict[str, Facility],
    slots: list[Slot],
    base_date: date,
) -> VisitRequest:
    facility = facilities[visit["destination"]]
    department = Department(visit["department"]).value
    earliest = base_date + timedelta(days=int(visit["earliest_offset_days"]))
    latest = base_date + timedelta(days=int(visit["latest_offset_days"]))
    candidates = [
        s
        for s in slots
        if s.facility is facility
        and s.department == department
        and earliest <= s.start_time.date() <= latest
    ]
    return VisitRequest(
        patient=patient,
        referral_ref=f"DEMO-{str(patient.key).upper()}",
        facility=facility,
        department=department,
        visit_type=VisitType(visit["visit_type"]).value,
        urgency_class=UrgencyClass(visit["urgency_class"]).value,
        earliest_date=earliest,
        latest_date=latest,
        recurrence=visit.get("recurrence"),
        status=RequestStatus.OPEN.value,
        candidate_slots=candidates,
    )


def _build_vehicles(patients: list[Patient]) -> list[Vehicle]:
    vehicles: list[Vehicle] = []
    for i, data in enumerate(BASE_VEHICLES_DATA, start=1):
        lat, lon = settlement_point(data["base_settlement"])
        vehicles.append(
            Vehicle(
                key=data["key"],
                name=data["name"],
                provider_type=data["provider_type"].value,
                seats=data["seats"],
                wheelchair_spots=data["wheelchair_spots"],
                stretcher_spots=data["stretcher_spots"],
                shift_start=data["shift"][0],
                shift_end=data["shift"][1],
                base_settlement=data["base_settlement"],
                base_municipality=data["base_municipality"],
                base_location=make_point_wkt(lat, lon),
                driver_name=data["driver_name"],
                driver_phone=f"+385 00 100 {i:04d}",
                active=True,
            )
        )
    # A patient's car joins the fleet only with consent, free seats and checked documents.
    for patient in patients:
        if not (
            patient.own_car
            and patient.carpool_driver_seats > 0
            and patient.driver_documents_confirmed
        ):
            continue
        vehicles.append(
            Vehicle(
                key=f"patient_driver_{patient.key}",
                name=f"Osobni auto, {patient.settlement}",
                provider_type=VehicleProviderType.PATIENT_DRIVER.value,
                seats=patient.carpool_driver_seats,
                wheelchair_spots=0,
                stretcher_spots=0,
                shift_start=PATIENT_DRIVER_SHIFT[0],
                shift_end=PATIENT_DRIVER_SHIFT[1],
                base_settlement=patient.settlement,
                base_municipality=patient.municipality,
                base_location=patient.location,
                driver_name=f"{patient.first_name} {patient.last_name}",
                driver_phone=patient.phone,
                patient_driver=patient,
                active=True,
            )
        )
    return vehicles


def build_seed_objects(base_date: date | None = None, data_dir: Path | None = None) -> SeedBundle:
    """Build all demo objects in memory. `base_date` is the plan day (default: today in Zagreb)."""
    plan_date = base_date or datetime.now(ZAGREB).date()
    root = data_dir or get_settings().data_dir

    boundaries = load_municipality_boundaries(root / MUNICIPALITIES_GEOJSON_PATH)
    municipalities = [
        Municipality(
            name=name,
            county=COUNTY,
            population_65_plus_share=MUNICIPALITY_65_PLUS_SHARE.get(name),
            boundary=make_multipolygon_wkt(geom.wkt),
        )
        for name, geom in sorted(boundaries.items())
    ]

    facilities = {
        f["key"]: Facility(
            key=f["key"],
            name=f["name"],
            level=f["level"],
            address=f["address"],
            settlement=f["settlement"],
            municipality=f["municipality"],
            county=f["county"],
            location=make_point_wkt(f["lat"], f["lon"]),
        )
        for f in FACILITIES_DATA
    }

    slots = _build_slots(facilities, plan_date)

    patients: list[Patient] = []
    visit_requests: list[VisitRequest] = []
    for index, profile in enumerate(load_patient_profiles(root / PATIENT_PROFILES_PATH), start=1):
        patient = _build_patient(index, profile, boundaries)
        patients.append(patient)
        visit_requests.append(
            _build_visit_request(patient, profile["visit"], facilities, slots, plan_date)
        )

    return SeedBundle(
        base_date=plan_date,
        municipalities=municipalities,
        facilities=list(facilities.values()),
        slots=slots,
        patients=patients,
        visit_requests=visit_requests,
        vehicles=_build_vehicles(patients),
        trip_logs=generate_synthetic_trip_logs(end_date=plan_date, data_dir=root),
    )


def seed_database(
    session: Session, base_date: date | None = None, data_dir: Path | None = None
) -> dict[str, int]:
    """Delete all domain rows and insert the demo data."""
    bundle = build_seed_objects(base_date=base_date, data_dir=data_dir)

    # Children before parents (foreign keys).
    session.execute(delete(TripLog))
    session.execute(delete(Assignment))
    session.execute(delete(visit_request_candidate_slots))
    session.execute(delete(VisitRequest))
    session.execute(delete(Slot))
    session.execute(delete(Vehicle))
    session.execute(delete(Patient))
    session.execute(delete(Facility))
    session.execute(delete(Municipality))

    session.add_all(bundle.municipalities)
    session.add_all(bundle.facilities)
    session.add_all(bundle.slots)
    session.add_all(bundle.patients)
    session.add_all(bundle.visit_requests)
    session.add_all(bundle.vehicles)
    session.add_all(bundle.trip_logs)
    session.commit()

    return {
        "municipalities": len(bundle.municipalities),
        "facilities": len(bundle.facilities),
        "slots": len(bundle.slots),
        "patients": len(bundle.patients),
        "visit_requests": len(bundle.visit_requests),
        "vehicles": len(bundle.vehicles),
        "trip_logs": len(bundle.trip_logs),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as session:
        counts = seed_database(session)
    logger.info("Demo data seeded: %s", counts)


if __name__ == "__main__":
    main()
