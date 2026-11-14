from __future__ import annotations

from datetime import UTC, date, datetime, time
from enum import StrEnum
from typing import Any

from geoalchemy2 import Geography, WKBElement, WKTElement
from geoalchemy2.shape import to_shape
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class PhoneType(StrEnum):
    LANDLINE = "landline"
    BASIC_MOBILE = "basic_mobile"
    SMARTPHONE = "smartphone"


class MobilityClass(StrEnum):
    WALKS = "walks"
    CANE = "cane"
    WHEELCHAIR = "wheelchair"
    STRETCHER = "stretcher"


class TransportEntitlement(StrEnum):
    SANITETSKI = "sanitetski"
    TRAVEL_ORDER = "travel_order"
    NONE = "none"


class Department(StrEnum):
    INTERNAL_MEDICINE = "internal_medicine"
    CARDIOLOGY = "cardiology"
    OPHTHALMOLOGY = "ophthalmology"
    ORTHOPAEDICS = "orthopaedics"
    NEUROLOGY = "neurology"
    RADIOLOGY = "radiology"
    ONCOLOGY = "oncology"
    DIALYSIS = "dialysis"


class VisitType(StrEnum):
    FIRST_VISIT = "first_visit"
    FOLLOW_UP = "follow_up"
    PROCEDURE_TEST = "procedure_test"
    DIALYSIS_SESSION = "dialysis_session"
    # Separate types because the HZZO distance exception covers chemo- and radiotherapy only,
    # not oncology in general (hzzo_rules.yaml), and their durations differ widely.
    CHEMOTHERAPY = "chemotherapy"
    RADIOTHERAPY = "radiotherapy"


class UrgencyClass(StrEnum):
    FIXED = "fixed"
    WITHIN_FEW_DAYS = "within_few_days"
    WITHIN_WEEK = "within_week"
    WITHIN_MONTH = "within_month"


class VehicleProviderType(StrEnum):
    SANITETSKI = "sanitetski"
    RED_CROSS = "red_cross"
    MUNICIPAL = "municipal"
    VOLUNTEER = "volunteer"
    TAXI = "taxi"
    PATIENT_DRIVER = "patient_driver"


class AssignmentStatus(StrEnum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    MODIFIED = "modified"
    COMPLETED = "completed"


class RequestStatus(StrEnum):
    OPEN = "open"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DriverStatusEvent(StrEnum):
    ARRIVED = "arrived"
    BOARDED = "boarded"
    DROPPED_OFF = "dropped_off"
    PATIENT_ABSENT = "patient_absent"
    RUNNING_LATE = "running_late"


def _in_check(column: str, enum_cls: type[StrEnum], name: str) -> CheckConstraint:
    values = ", ".join(f"'{m.value}'" for m in enum_cls)
    return CheckConstraint(f"{column} IN ({values})", name=name)


def make_point_wkt(lat: float, lon: float) -> WKTElement:
    """Create a PostGIS SRID 4326 WKTElement from (lat, lon). Note: WKT order is POINT(lon lat)."""
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


def make_multipolygon_wkt(wkt: str) -> WKTElement:
    """Wrap a POLYGON or MULTIPOLYGON WKT string in a PostGIS SRID 4326 WKTElement."""
    cleaned = wkt.strip()
    if cleaned.upper().startswith("POLYGON"):
        body = cleaned[len("POLYGON") :].strip()
        cleaned = f"MULTIPOLYGON({body})"
    return WKTElement(cleaned, srid=4326)


def extract_lon_lat(geom: Any) -> tuple[float, float] | None:
    """Return (lon, lat) of a Point stored as WKTElement/WKBElement, else None."""
    if not isinstance(geom, (WKTElement, WKBElement)):
        return None
    shape = to_shape(geom)
    if shape.geom_type != "Point":
        return None
    return float(shape.x), float(shape.y)


visit_request_candidate_slots = Table(
    "visit_request_candidate_slots",
    Base.metadata,
    Column(
        "request_id",
        Integer,
        ForeignKey("visit_requests.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "slot_id",
        Integer,
        ForeignKey("slots.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Municipality(Base):
    """Tablica općina i gradova s granicama (poligoni) za zone grupiranja i prognozu potražnje."""

    __tablename__ = "municipalities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    county: Mapped[str] = mapped_column(String(120), nullable=False)
    population_65_plus_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    boundary: Mapped[Any] = mapped_column(
        Geography(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=True),
        nullable=False,
    )


class Facility(Base):
    """Zdravstvena ustanova (dom zdravlja, opća bolnica, poliklinika, KBC)."""

    __tablename__ = "facilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    level: Mapped[str] = mapped_column(String(32), nullable=False, default="secondary")
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    settlement: Mapped[str] = mapped_column(String(120), nullable=False)
    municipality: Mapped[str] = mapped_column(String(120), nullable=False)
    county: Mapped[str] = mapped_column(String(120), nullable=False)
    location: Mapped[Any] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=False,
    )

    slots: Mapped[list[Slot]] = relationship("Slot", back_populates="facility")
    visit_requests: Mapped[list[VisitRequest]] = relationship(
        "VisitRequest", back_populates="facility"
    )

    @property
    def latitude(self) -> float | None:
        coords = extract_lon_lat(self.location)
        return coords[1] if coords else None

    @property
    def longitude(self) -> float | None:
        coords = extract_lon_lat(self.location)
        return coords[0] if coords else None


class Patient(Base):
    """Pacijent prema odjeljku 4 arhitekture."""

    __tablename__ = "patients"
    __table_args__ = (
        _in_check("mobility_class", MobilityClass, "ck_patients_mobility_class"),
        _in_check(
            "transport_entitlement", TransportEntitlement, "ck_patients_transport_entitlement"
        ),
        _in_check("phone_type", PhoneType, "ck_patients_phone_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    birth_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mbo: Mapped[str] = mapped_column(String(9), unique=True, nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(40), nullable=False)
    phone_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default=PhoneType.LANDLINE.value
    )

    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    settlement: Mapped[str] = mapped_column(String(120), nullable=False)
    municipality: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    county: Mapped[str] = mapped_column(String(120), nullable=False)
    location: Mapped[Any | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=True,
    )

    mobility_class: Mapped[str] = mapped_column(
        String(32), nullable=False, default=MobilityClass.WALKS.value
    )
    lives_alone: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    companion: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    floor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    elevator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    transport_entitlement: Mapped[str] = mapped_column(
        String(32), nullable=False, default=TransportEntitlement.NONE.value
    )
    social_order_today: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    own_car: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    carpool_driver_seats: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    carpool_rider_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    driver_documents_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    missed_visits_last_year: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    visit_requests: Mapped[list[VisitRequest]] = relationship(
        "VisitRequest", back_populates="patient", cascade="all, delete-orphan"
    )
    vehicles: Mapped[list[Vehicle]] = relationship("Vehicle", back_populates="patient_driver")

    @property
    def name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def mbo_masked(self) -> str:
        return "*****" + self.mbo[-4:]

    def __repr__(self) -> str:
        # Never include the MBO (or other personal data) in reprs/logs.
        return f"<Patient id={self.id!r}>"

    @property
    def latitude(self) -> float | None:
        coords = extract_lon_lat(self.location)
        return coords[1] if coords else None

    @property
    def longitude(self) -> float | None:
        coords = extract_lon_lat(self.location)
        return coords[0] if coords else None


class Slot(Base):
    """Termin u ustanovi otvoren za naručivanje."""

    __tablename__ = "slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    facility_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("facilities.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    department: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    facility: Mapped[Facility] = relationship("Facility", back_populates="slots")
    candidate_for_requests: Mapped[list[VisitRequest]] = relationship(
        "VisitRequest",
        secondary=visit_request_candidate_slots,
        back_populates="candidate_slots",
    )
    assignments: Mapped[list[Assignment]] = relationship("Assignment", back_populates="slot")

    @property
    def latitude(self) -> float | None:
        return self.facility.latitude if self.facility is not None else None

    @property
    def longitude(self) -> float | None:
        return self.facility.longitude if self.facility is not None else None


class VisitRequest(Base):
    """Zahtjev za pregled prema odjeljku 4 arhitekture."""

    __tablename__ = "visit_requests"
    __table_args__ = (_in_check("status", RequestStatus, "ck_visit_requests_status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    referral_ref: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    facility_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("facilities.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    department: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    visit_type: Mapped[str] = mapped_column(String(64), nullable=False)
    urgency_class: Mapped[str] = mapped_column(String(64), nullable=False)
    earliest_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    latest_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    recurrence: Mapped[str | None] = mapped_column(String(64), nullable=True)
    preferred_time_of_day: Mapped[str | None] = mapped_column(String(32), nullable=True)
    slot_request_pending: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=RequestStatus.OPEN.value, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    patient: Mapped[Patient] = relationship("Patient", back_populates="visit_requests")
    facility: Mapped[Facility] = relationship("Facility", back_populates="visit_requests")
    candidate_slots: Mapped[list[Slot]] = relationship(
        "Slot",
        secondary=visit_request_candidate_slots,
        back_populates="candidate_for_requests",
    )
    assignments: Mapped[list[Assignment]] = relationship(
        "Assignment", back_populates="request", cascade="all, delete-orphan"
    )


class Vehicle(Base):
    """Vozilo prema odjeljku 4 arhitekture."""

    __tablename__ = "vehicles"
    __table_args__ = (_in_check("provider_type", VehicleProviderType, "ck_vehicles_provider_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provider_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    seats: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    wheelchair_spots: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stretcher_spots: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shift_start: Mapped[time] = mapped_column(Time, nullable=False, default=time(6, 0))
    shift_end: Mapped[time] = mapped_column(Time, nullable=False, default=time(18, 0))
    base_settlement: Mapped[str | None] = mapped_column(String(120), nullable=True)
    base_municipality: Mapped[str | None] = mapped_column(String(120), nullable=True)
    base_location: Mapped[Any] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=False,
    )
    driver_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    driver_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    patient_driver_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="SET NULL"), nullable=True, index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    patient_driver: Mapped[Patient | None] = relationship("Patient", back_populates="vehicles")
    assignments: Mapped[list[Assignment]] = relationship(
        "Assignment",
        foreign_keys="Assignment.vehicle_id",
        back_populates="vehicle",
    )

    @property
    def latitude(self) -> float | None:
        coords = extract_lon_lat(self.base_location)
        return coords[1] if coords else None

    @property
    def longitude(self) -> float | None:
        coords = extract_lon_lat(self.base_location)
        return coords[0] if coords else None


class Assignment(Base):
    """Dodjela termina i vozila zahtjevu pacijenta."""

    __tablename__ = "assignments"
    __table_args__ = (_in_check("status", AssignmentStatus, "ck_assignments_status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("visit_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("slots.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    vehicle_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("vehicles.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    return_vehicle_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True
    )

    pickup_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    facility_arrival_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    return_pickup_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    home_dropoff_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    pickup_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    return_order: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=AssignmentStatus.PROPOSED.value,
        index=True,
    )
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    carpool_driver_confirmed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    request: Mapped[VisitRequest] = relationship("VisitRequest", back_populates="assignments")
    slot: Mapped[Slot] = relationship("Slot", back_populates="assignments")
    vehicle: Mapped[Vehicle] = relationship(
        "Vehicle", foreign_keys=[vehicle_id], back_populates="assignments"
    )
    return_vehicle: Mapped[Vehicle | None] = relationship(
        "Vehicle", foreign_keys=[return_vehicle_id]
    )
    trip_logs: Mapped[list[TripLog]] = relationship(
        "TripLog", back_populates="assignment", cascade="all, delete-orphan"
    )


class TripLog(Base):
    """Stvarna vremena vožnje i pregleda (ulaz za treniranje ML modela)."""

    __tablename__ = "trip_logs"
    __table_args__ = (
        _in_check("driver_status_event", DriverStatusEvent, "ck_trip_logs_driver_status_event"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assignment_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("assignments.id", ondelete="SET NULL"), nullable=True, index=True
    )

    actual_arrival_at_door: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actual_departure_from_door: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actual_check_in_at_facility: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actual_check_out_from_facility: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actual_dropoff_at_home: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    driver_status_event: Mapped[str | None] = mapped_column(String(32), nullable=True)
    recorded_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Optional denormalized context for synthetic TripLog rows (E1-T4) and ML training (E4)
    department: Mapped[str | None] = mapped_column(String(64), nullable=True)
    visit_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mobility_class: Mapped[str | None] = mapped_column(String(32), nullable=True)
    floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elevator: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    companion: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    patient_age: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    assignment: Mapped[Assignment | None] = relationship("Assignment", back_populates="trip_logs")
