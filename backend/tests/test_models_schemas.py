from __future__ import annotations

import struct
from datetime import UTC, date, datetime, time

import pytest
from geoalchemy2 import Geography, WKBElement
from pydantic import ValidationError
from sqlalchemy import CheckConstraint

from app.db import Base
from app.models import (
    Assignment,
    AssignmentStatus,
    Department,
    DriverStatusEvent,
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
    extract_lon_lat,
    make_multipolygon_wkt,
    make_point_wkt,
)
from app.schemas import (
    AssignmentCreate,
    AssignmentRead,
    AssignmentUpdate,
    FacilityRead,
    GeoPoint,
    MunicipalityCreate,
    PatientCreate,
    PatientRead,
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


def test_enums_use_exact_english_values_without_aliases() -> None:
    assert [m.value for m in VehicleProviderType] == [
        "sanitetski",
        "red_cross",
        "municipal",
        "volunteer",
        "taxi",
        "patient_driver",
    ]
    assert [m.value for m in AssignmentStatus] == [
        "proposed",
        "confirmed",
        "modified",
        "completed",
    ]
    assert [m.value for m in DriverStatusEvent] == [
        "arrived",
        "boarded",
        "dropped_off",
        "patient_absent",
        "running_late",
    ]
    for enum_cls, bad in (
        (VehicleProviderType, "Crveni križ"),
        (AssignmentStatus, "potvrđeno"),
        (MobilityClass, "kolica"),
        (TransportEntitlement, "putni nalog"),
        (DriverStatusEvent, "stigao"),
    ):
        with pytest.raises(ValueError):
            enum_cls(bad)


def test_check_constraints_mirror_enums() -> None:
    expected = {
        ("patients", "mobility_class"): MobilityClass,
        ("patients", "transport_entitlement"): TransportEntitlement,
        ("patients", "phone_type"): PhoneType,
        ("vehicles", "provider_type"): VehicleProviderType,
        ("assignments", "status"): AssignmentStatus,
        ("visit_requests", "status"): RequestStatus,
        ("trip_logs", "driver_status_event"): DriverStatusEvent,
    }
    for (table, col), enum_cls in expected.items():
        checks = {
            c.name: str(c.sqltext)
            for c in Base.metadata.tables[table].constraints
            if isinstance(c, CheckConstraint)
        }
        text = checks[f"ck_{table}_{col}"]
        for member in enum_cls:
            assert f"'{member.value}'" in text


def test_removed_fields_are_absent_and_consent_is_split() -> None:
    cols = {t: set(Base.metadata.tables[t].c.keys()) for t in Base.metadata.tables}
    assert not cols["patients"] & {
        "story",
        "consent_given",
        "volunteer_partner",
        "carpool_consent",
        "driver_registration_valid",
        "driver_insurance_valid",
        "driver_license_valid",
    }
    assert {"carpool_rider_consent", "driver_documents_confirmed"} <= cols["patients"]
    assert "has_driver_assistance" not in cols["vehicles"]
    assert not cols["assignments"] & {"backup_vehicle_id", "distance_km", "carpool_confirmed"}
    assert "carpool_driver_confirmed" in cols["assignments"]
    assert "notes" not in cols["trip_logs"]
    for table in ("slots", "visit_requests"):
        assert "facility_key" not in cols[table]
        assert Base.metadata.tables[table].c["facility_id"].nullable is False
    assert not cols["slots"] & {"facility_name", "facility_location"}


def test_county_is_required() -> None:
    kw = {k: v for k, v in _PATIENT_KW.items() if k != "county"}
    with pytest.raises(ValidationError):
        PatientCreate(mbo="000000004", **kw)


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
        carpool_rider_consent=False,
        driver_documents_confirmed=False,
        missed_visits_last_year=1,
        created_at=now,
        updated_at=now,
    )
    pat_read = PatientRead.model_validate(patient)
    assert pat_read.name == "Marija Horvat"
    assert pat_read.latitude == pytest.approx(44.55)
    assert pat_read.longitude == pytest.approx(15.38)
    assert pat_read.mobility_class == MobilityClass.CANE
    dumped = pat_read.model_dump_json()
    assert pat_read.mbo_masked == "*****0001"
    assert "000000001" not in dumped
    assert "mbo" not in pat_read.model_dump()
    assert "000000001" not in repr(patient)

    slot = Slot(
        id=100,
        facility_id=1,
        facility=facility,
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
        department=Department.CARDIOLOGY.value,
        visit_type=VisitType.FOLLOW_UP.value,
        urgency_class=UrgencyClass.WITHIN_MONTH.value,
        earliest_date=date(2026, 11, 15),
        latest_date=date(2026, 11, 24),
        slot_request_pending=False,
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
        provider_type="red_cross",  # type: ignore[arg-type]
        seats=4,
        wheelchair_spots=1,
        shift_start=time(7, 0),
        shift_end=time(17, 0),
        base_settlement="Gospić",
        base_municipality="Gospić",
        base_location=GeoPoint(lat=44.5469, lon=15.3747),
    )
    assert veh_in.provider_type == VehicleProviderType.RED_CROSS

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
        active=True,
    )
    veh_read = VehicleRead.model_validate(vehicle)
    assert veh_read.provider_type == VehicleProviderType.RED_CROSS
    assert veh_read.latitude == pytest.approx(44.5469)

    asgn_in = AssignmentCreate(
        request_id=200,
        slot_id=100,
        vehicle_id=300,
        pickup_time=now,
        status="confirmed",  # type: ignore[arg-type]
        is_locked=True,
    )
    assert asgn_in.status == AssignmentStatus.CONFIRMED
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
    assert asgn_read.status == AssignmentStatus.CONFIRMED
    assert asgn_read.is_locked is True

    patch = AssignmentUpdate(status="modified", is_locked=True)  # type: ignore[arg-type]
    assert patch.status == AssignmentStatus.MODIFIED

    log_in = TripLogCreate(
        assignment_id=400,
        actual_arrival_at_door=now,
        driver_status_event="arrived",  # type: ignore[arg-type]
        recorded_by="driver",
    )
    log_orm = TripLog(
        id=500,
        assignment_id=log_in.assignment_id,
        actual_arrival_at_door=log_in.actual_arrival_at_door,
        driver_status_event=log_in.driver_status_event.value
        if log_in.driver_status_event
        else None,
        recorded_by=log_in.recorded_by,
        created_at=now,
    )
    log_read = TripLogRead.model_validate(log_orm)
    assert log_read.id == 500

    muni_in = MunicipalityCreate(
        name="Gospić",
        county="Ličko-senjska",
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
            county="Ličko-senjska",
        )

    with pytest.raises(ValidationError, match="Najkasniji datum ne smije biti prije najranijeg"):
        VisitRequestCreate(
            patient_id=1,
            facility_id=1,
            department=Department.CARDIOLOGY,
            visit_type=VisitType.FOLLOW_UP,
            urgency_class=UrgencyClass.WITHIN_WEEK,
            earliest_date=date(2026, 11, 20),
            latest_date=date(2026, 11, 15),
        )


def test_preferred_time_of_day_accepts_only_codebook_values() -> None:
    kw = dict(
        patient_id=1,
        facility_id=1,
        department=Department.CARDIOLOGY,
        visit_type=VisitType.FOLLOW_UP,
        urgency_class=UrgencyClass.WITHIN_WEEK,
        earliest_date=date(2026, 11, 16),
        latest_date=date(2026, 11, 20),
    )
    assert VisitRequestCreate(**kw).preferred_time_of_day is None
    for key in ("morning", "afternoon"):
        assert VisitRequestCreate(**kw, preferred_time_of_day=key).preferred_time_of_day == key
    with pytest.raises(ValidationError, match="Željeni dio dana"):
        VisitRequestCreate(**kw, preferred_time_of_day="ujutro")


_PATIENT_KW = dict(
    first_name="Ivo",
    last_name="Ivić",
    phone="+385 00 000 0001",
    settlement="Gospić",
    municipality="Gospić",
    county="Ličko-senjska",
)


def test_invalid_mbo_is_not_echoed_in_errors_or_repr() -> None:
    with pytest.raises(ValidationError) as exc:
        PatientCreate(mbo="123456", **_PATIENT_KW)
    assert "123456" not in str(exc.value)
    assert "123456" not in repr(exc.value.errors())
    assert [e["input"] for e in exc.value.errors()] == ["***"]

    ok = PatientCreate(mbo="000000002", **_PATIENT_KW)
    assert "000000002" not in repr(ok)


def test_patient_requires_last_name_and_ignores_aliases() -> None:
    with pytest.raises(ValidationError):
        PatientCreate(mbo="000000003", **{**_PATIENT_KW, "last_name": None})
    kw = {k: v for k, v in _PATIENT_KW.items() if k not in ("first_name", "last_name")}
    with pytest.raises(ValidationError) as exc:
        PatientCreate.model_validate({"mbo": "000000003", "name": "Ivo", **kw})
    assert {e["loc"][0] for e in exc.value.errors()} == {"first_name", "last_name"}
