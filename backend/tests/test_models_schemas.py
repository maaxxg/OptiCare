from __future__ import annotations

import struct
from datetime import UTC, date, datetime, time
from pathlib import Path

import pytest
import yaml
from geoalchemy2 import Geography, WKBElement
from pydantic import ValidationError

from app.db import Base
from app.models import (
    Assignment,
    AssignmentStatus,
    Department,
    Facility,
    MobilityClass,
    Municipality,
    Patient,
    PhoneType,
    Slot,
    TransportEntitlement,
    TripLog,
    UrgencyClass,
    Vehicle,
    VehicleProviderType,
    VisitRequest,
    VisitType,
    extract_lon_lat,
    make_multipolygon_wkt,
    make_point_wkt,
)
from app.schemas import (
    AssignmentCreate,
    AssignmentRead,
    AssignmentUpdate,
    FacilityCreate,
    FacilityRead,
    GeoPoint,
    MunicipalityCreate,
    PatientCreate,
    PatientRead,
    SlotCreate,
    SlotRead,
    TripLogCreate,
    TripLogRead,
    VehicleCreate,
    VehicleRead,
    VisitRequestCreate,
    VisitRequestRead,
)


def test_metadata_tables_and_postgis_columns() -> None:
    expected_tables = {
        "municipalities",
        "facilities",
        "patients",
        "slots",
        "visit_requests",
        "visit_request_candidate_slots",
        "vehicles",
        "assignments",
        "trip_logs",
    }
    assert expected_tables.issubset(set(Base.metadata.tables.keys()))

    # Verify PostGIS Geography(Point, 4326) columns and GiST spatial indexes
    point_Targets = [
        ("patients", "location"),
        ("facilities", "location"),
        ("slots", "facility_location"),
        ("vehicles", "base_location"),
    ]
    for table_name, col_name in point_Targets:
        table = Base.metadata.tables[table_name]
        col = table.c[col_name]
        assert isinstance(col.type, Geography)
        assert col.type.geometry_type == "POINT"
        assert col.type.srid == 4326
        assert col.type.spatial_index is True

    # Verify Municipality polygon column
    muni_col = Base.metadata.tables["municipalities"].c["boundary"]
    assert isinstance(muni_col.type, Geography)
    assert muni_col.type.geometry_type == "MULTIPOLYGON"
    assert muni_col.type.srid == 4326
    assert muni_col.type.spatial_index is True


def test_enums_support_croatian_and_english_aliases() -> None:
    assert VehicleProviderType("sanitetski") == VehicleProviderType.SANITETSKI
    assert VehicleProviderType("Crveni križ") == VehicleProviderType.CRVENI_KRIZ
    assert VehicleProviderType("općinski") == VehicleProviderType.OPCINSKI
    assert VehicleProviderType("volonter") == VehicleProviderType.VOLONTER
    assert VehicleProviderType("taksi") == VehicleProviderType.TAKSI
    assert VehicleProviderType("pacijent-vozač") == VehicleProviderType.PACIJENT_VOZAC
    assert VehicleProviderType("patient_driver") == VehicleProviderType.PACIJENT_VOZAC

    assert AssignmentStatus("predloženo") == AssignmentStatus.PREDLOZENO
    assert AssignmentStatus("potvrđeno") == AssignmentStatus.POTVRDENO
    assert AssignmentStatus("izmijenjeno") == AssignmentStatus.IZMIJENJENO
    assert AssignmentStatus("obavljeno") == AssignmentStatus.OBAVLJENO
    assert AssignmentStatus("confirmed") == AssignmentStatus.POTVRDENO

    assert MobilityClass("hoda") == MobilityClass.WALKS
    assert MobilityClass("štap") == MobilityClass.CANE
    assert MobilityClass("kolica") == MobilityClass.WHEELCHAIR
    assert MobilityClass("nosila") == MobilityClass.STRETCHER

    assert TransportEntitlement("sanitetski prijevoz") == TransportEntitlement.SANITETSKI
    assert TransportEntitlement("putni nalog") == TransportEntitlement.TRAVEL_ORDER
    assert TransportEntitlement("ništa") == TransportEntitlement.NONE


def test_wkt_and_wkb_coordinate_extraction() -> None:
    # Gospić approximate coordinates: lat=44.5469, lon=15.3747
    wkt_pt = make_point_wkt(lat=44.5469, lon=15.3747)
    assert extract_lon_lat(wkt_pt) == pytest.approx((15.3747, 44.5469))

    # Build EWKB Point with SRID 4326 (little-endian: 0x01, type: 0x20000001, srid: 4326)
    ewkb_bytes = struct.pack("<BIIdd", 1, 0x20000001, 4326, 15.3747, 44.5469)
    wkb_pt = WKBElement(ewkb_bytes, srid=4326)
    assert extract_lon_lat(wkb_pt) == pytest.approx((15.3747, 44.5469))

    poly_wkt = make_multipolygon_wkt(
        "POLYGON((15.0 44.0, 15.5 44.0, 15.5 44.6, 15.0 44.6, 15.0 44.0))"
    )
    assert poly_wkt.srid == 4326
    assert poly_wkt.data.startswith("MULTIPOLYGON")


def test_orm_models_and_pydantic_roundtrip() -> None:
    now = datetime(2026, 11, 14, 8, 30, tzinfo=UTC)

    facility = Facility(
        id=1,
        key="ob_gospic",
        name="Opća bolnica Gospić",
        level="secondary",
        settlement="Gospić",
        municipality="Gospić",
        county="Ličko-senjska",
        location=make_point_wkt(44.5469, 15.3747),
    )
    fac_read = FacilityRead.model_validate(facility)
    assert fac_read.location == GeoPoint(lat=44.5469, lon=15.3747)
    assert fac_read.latitude == pytest.approx(44.5469)
    assert fac_read.longitude == pytest.approx(15.3747)

    patient = Patient(
        id=10,
        key="p01",
        first_name="Marija",
        last_name="Horvat",
        birth_year=1941,
        mbo="000000001",
        phone="+385 00 000 0001",
        phone_type=PhoneType.LANDLINE.value,
        settlement="Gospić",
        municipality="Gospić",
        county="Ličko-senjska",
        location=make_point_wkt(44.5500, 15.3800),
        mobility_class=MobilityClass.CANE.value,
        lives_alone=True,
        companion=False,
        floor=2,
        elevator=False,
        transport_entitlement=TransportEntitlement.NONE.value,
        social_order_today=False,
        own_car=False,
        carpool_driver_seats=0,
        carpool_consent=False,
        missed_visits_last_year=1,
        consent_given=True,
        created_at=now,
        updated_at=now,
    )
    pat_read = PatientRead.model_validate(patient)
    assert pat_read.name == "Marija Horvat"
    assert pat_read.latitude == pytest.approx(44.55)
    assert pat_read.longitude == pytest.approx(15.38)
    assert pat_read.mobility_class == MobilityClass.CANE

    slot = Slot(
        id=100,
        facility_id=1,
        facility_key="ob_gospic",
        facility_name="Opća bolnica Gospić",
        facility_location=make_point_wkt(44.5469, 15.3747),
        department=Department.CARDIOLOGY.value,
        start_time=now,
        capacity=1,
    )
    slot_read = SlotRead.model_validate(slot)
    assert slot_read.department == Department.CARDIOLOGY
    assert slot_read.latitude == pytest.approx(44.5469)

    req = VisitRequest(
        id=200,
        patient_id=patient.id,
        referral_ref="EUP-2026-0001",
        facility_id=1,
        facility_key="ob_gospic",
        department=Department.CARDIOLOGY.value,
        visit_type=VisitType.FOLLOW_UP.value,
        urgency_class=UrgencyClass.WITHIN_MONTH.value,
        earliest_date=date(2026, 11, 15),
        latest_date=date(2026, 11, 24),
        status="open",
        candidate_slots=[slot],
        created_at=now,
    )
    req_read = VisitRequestRead.model_validate(req)
    assert len(req_read.candidate_slots) == 1
    assert req_read.candidate_slots[0].id == 100

    veh_in = VehicleCreate(
        key="ck_gospic_1",
        name="Crveni križ Gospić 1",
        provider_type="Crveni križ",  # type: ignore[arg-type]
        seats=4,
        wheelchair_spots=1,
        shift_start=time(7, 0),
        shift_end=time(17, 0),
        base_settlement="Gospić",
        base_municipality="Gospić",
        base_location=GeoPoint(lat=44.5469, lon=15.3747),
    )
    assert veh_in.provider_type == VehicleProviderType.CRVENI_KRIZ

    vehicle = Vehicle(
        id=300,
        key=veh_in.key,
        name=veh_in.name,
        provider_type=veh_in.provider_type.value,
        seats=veh_in.seats,
        wheelchair_spots=veh_in.wheelchair_spots,
        stretcher_spots=veh_in.stretcher_spots,
        shift_start=veh_in.shift_start,
        shift_end=veh_in.shift_end,
        base_settlement=veh_in.base_settlement,
        base_municipality=veh_in.base_municipality,
        base_location=make_point_wkt(veh_in.base_location.lat, veh_in.base_location.lon),
        has_driver_assistance=True,
        active=True,
    )
    veh_read = VehicleRead.model_validate(vehicle)
    assert veh_read.provider_type == VehicleProviderType.CRVENI_KRIZ
    assert veh_read.latitude == pytest.approx(44.5469)

    asgn_in = AssignmentCreate(
        request_id=200,
        slot_id=100,
        vehicle_id=300,
        pickup_time=now,
        status="potvrđeno",  # type: ignore[arg-type]
        is_locked=True,
    )
    assert asgn_in.status == AssignmentStatus.POTVRDENO
    assert asgn_in.is_locked is True

    asgn = Assignment(
        id=400,
        request_id=asgn_in.request_id,
        slot_id=asgn_in.slot_id,
        vehicle_id=asgn_in.vehicle_id,
        pickup_time=asgn_in.pickup_time,
        status=asgn_in.status.value,
        is_locked=asgn_in.is_locked,
        created_at=now,
        updated_at=now,
    )
    asgn_read = AssignmentRead.model_validate(asgn)
    assert asgn_read.status == AssignmentStatus.POTVRDENO
    assert asgn_read.is_locked is True

    patch = AssignmentUpdate(status="izmijenjeno", is_locked=True)  # type: ignore[arg-type]
    assert patch.status == AssignmentStatus.IZMIJENJENO

    log_in = TripLogCreate(
        assignment_id=400,
        actual_arrival_at_door=now,
        driver_status_event="stigao",  # type: ignore[arg-type]
        recorded_by="driver",
    )
    log_orm = TripLog(
        id=500,
        assignment_id=log_in.assignment_id,
        actual_arrival_at_door=log_in.actual_arrival_at_door,
        driver_status_event=log_in.driver_status_event.value if log_in.driver_status_event else None,
        recorded_by=log_in.recorded_by,
        created_at=now,
    )
    log_read = TripLogRead.model_validate(log_orm)
    assert log_read.id == 500

    muni_in = MunicipalityCreate(
        name="Gospić",
        boundary_wkt="POLYGON((15.0 44.0, 15.5 44.0, 15.5 44.6, 15.0 44.6, 15.0 44.0))",
    )
    muni_orm = Municipality(
        id=1,
        name=muni_in.name,
        county=muni_in.county,
        boundary=make_multipolygon_wkt(muni_in.boundary_wkt),
    )
    assert muni_orm.name == "Gospić"


def test_schema_validation_errors() -> None:
    with pytest.raises(ValidationError, match="MBO mora sadržavati točno 9 znamenki"):
        PatientCreate(
            first_name="Ivo",
            last_name="Ivić",
            mbo="12345",
            phone="+385 00 000 0001",
            settlement="Gospić",
            municipality="Gospić",
        )

    with pytest.raises(ValidationError, match="latest_date ne smije biti prije earliest_date"):
        VisitRequestCreate(
            patient_id=1,
            facility_key="ob_gospic",
            department=Department.CARDIOLOGY,
            visit_type=VisitType.FOLLOW_UP,
            urgency_class=UrgencyClass.WITHIN_WEEK,
            earliest_date=date(2026, 11, 20),
            latest_date=date(2026, 11, 15),
        )


def test_domain_patient_profiles_yaml_compatible_with_schemas() -> None:
    yaml_path = Path(__file__).resolve().parents[2] / "data" / "domain" / "patient_profiles.yaml"
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    patients = data["patients"]
    assert len(patients) >= 15

    base_date = date(2026, 11, 14)
    for idx, raw in enumerate(patients, start=1):
        pat = PatientCreate.model_validate(raw)
        assert len(pat.mbo) == 9
        visit_raw = dict(raw["visit"])
        visit_raw["patient_id"] = idx
        visit_raw["earliest_date"] = base_date
        visit_raw["latest_date"] = base_date
        req = VisitRequestCreate.model_validate(visit_raw)
        assert req.patient_id == idx


def test_alembic_migration_file_contains_postgis_and_tables() -> None:
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0001_initial_schema.py"
    )
    content = migration_path.read_text(encoding="utf-8")
    assert "CREATE EXTENSION IF NOT EXISTS postgis" in content
    for table_name in (
        "municipalities",
        "facilities",
        "patients",
        "slots",
        "visit_requests",
        "vehicles",
        "assignments",
        "trip_logs",
    ):
        assert f'"{table_name}"' in content
