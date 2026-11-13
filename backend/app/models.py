from __future__ import annotations

import re
import struct
from datetime import UTC, date, datetime, time
from enum import StrEnum
from typing import Any

from geoalchemy2 import Geography, WKBElement, WKTElement
from sqlalchemy import (
     Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _normalize_token(val: str) -> str:
    """Normalize Croatian diacritics, spaces, and hyphens for flexible enum matching."""
    t = val.strip().lower().replace("-", "_").replace(" ", "_")
    replacements = {
        "č": "c",
        "ć": "c",
        "đ": "d",
        "š": "s",
        "ž": "z",
    }
    for src, dst in replacements.items():
        t = t.replace(src, dst)
    return t


class PhoneType(StrEnum):
    LANDLINE = "landline"
    BASIC_MOBILE = "basic_mobile"
    SMARTPHONE = "smartphone"

    @classmethod
    def _missing_(cls, value: object) -> PhoneType | None:
        if not isinstance(value, str):
            return None
        norm = _normalize_token(value)
        aliases = {
            "fiksni": cls.LANDLINE,
            "obicni_mobitel": cls.BASIC_MOBILE,
            "pametni_telefon": cls.SMARTPHONE,
        }
        for member in cls:
            if member.value == norm:
                return member
        return aliases.get(norm)


class MobilityClass(StrEnum):
    WALKS = "walks"
    CANE = "cane"
    WHEELCHAIR = "wheelchair"
    STRETCHER = "stretcher"

    @classmethod
    def _missing_(cls, value: object) -> MobilityClass | None:
        if not isinstance(value, str):
            return None
        norm = _normalize_token(value)
        aliases = {
            "hoda": cls.WALKS,
            "stap": cls.CANE,
            "kolica": cls.WHEELCHAIR,
            "nosila": cls.STRETCHER,
        }
        for member in cls:
            if member.value == norm:
                return member
        return aliases.get(norm)


class TransportEntitlement(StrEnum):
    SANITETSKI = "sanitetski"
    TRAVEL_ORDER = "travel_order"
    NONE = "none"

    @classmethod
    def _missing_(cls, value: object) -> TransportEntitlement | None:
        if not isinstance(value, str):
            return None
        norm = _normalize_token(value)
        aliases = {
            "sanitetski_prijevoz": cls.SANITETSKI,
            "putni_nalog": cls.TRAVEL_ORDER,
            "nista": cls.NONE,
        }
        for member in cls:
            if member.value == norm:
                return member
        return aliases.get(norm)


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


class UrgencyClass(StrEnum):
    FIXED = "fixed"
    WITHIN_FEW_DAYS = "within_few_days"
    WITHIN_WEEK = "within_week"
    WITHIN_MONTH = "within_month"


class VehicleProviderType(StrEnum):
    SANITETSKI = "sanitetski"
    CRVENI_KRIZ = "crveni_kriz"
    OPCINSKI = "opcinski"
    VOLONTER = "volonter"
    TAKSI = "taksi"
    PACIJENT_VOZAC = "pacijent_vozac"

    @classmethod
    def _missing_(cls, value: object) -> VehicleProviderType | None:
        if not isinstance(value, str):
            return None
        norm = _normalize_token(value)
        aliases = {
            "sanitetski_prijevoz": cls.SANITETSKI,
            "red_cross": cls.CRVENI_KRIZ,
            "municipal": cls.OPCINSKI,
            "opcinski_prijevoz": cls.OPCINSKI,
            "volunteer": cls.VOLONTER,
            "taxi": cls.TAKSI,
            "patient_driver": cls.PACIJENT_VOZAC,
        }
        for member in cls:
            if member.value == norm:
                return member
        return aliases.get(norm)


class AssignmentStatus(StrEnum):
    PREDLOZENO = "predlozeno"
    POTVRDENO = "potvrdeno"
    IZMIJENJENO = "izmijenjeno"
    OBAVLJENO = "obavljeno"

    @classmethod
    def _missing_(cls, value: object) -> AssignmentStatus | None:
        if not isinstance(value, str):
            return None
        norm = _normalize_token(value)
        aliases = {
            "proposed": cls.PREDLOZENO,
            "confirmed": cls.POTVRDENO,
            "modified": cls.IZMIJENJENO,
            "completed": cls.OBAVLJENO,
        }
        for member in cls:
            if member.value == norm:
                return member
        return aliases.get(norm)


class RequestStatus(StrEnum):
    OPEN = "open"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DriverStatusEvent(StrEnum):
    STIGAO = "stigao"
    UKRCAN = "ukrcan"
    ISKRCAN = "iskrcan"
    PACIJENTA_NEMA = "pacijenta_nema"
    KASNIM = "kasnim"

    @classmethod
    def _missing_(cls, value: object) -> DriverStatusEvent | None:
        if not isinstance(value, str):
            return None
        norm = _normalize_token(value)
        aliases = {
            "arrived": cls.STIGAO,
            "boarded": cls.UKRCAN,
            "dropped_off": cls.ISKRCAN,
            "no_show": cls.PACIJENTA_NEMA,
            "late": cls.KASNIM,
        }
        for member in cls:
            if member.value == norm:
                return member
        return aliases.get(norm)


_POINT_WKT_RE = re.compile(
    r"POINT\s*\(\s*([-+]?\d+(?:\.\d+)?)\s+([-+]?\d+(?:\.\d+)?)\s*\)",
    re.IGNORECASE,
)


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
    """Extract (lon, lat) from a GeoAlchemy2 WKTElement, WKBElement, dict, or tuple without requiring C-extensions."""
    if geom is None:
        return None
    if isinstance(geom, WKTElement):
        match = _POINT_WKT_RE.search(geom.data)
        if match:
            return float(match.group(1)), float(match.group(2))
        return None
    if isinstance(geom, WKBElement):
        raw = bytes(geom.data)
        if len(raw) < 21:
            return None
        endian = "<" if raw[0] == 1 else ">"
        (geom_type,) = struct.unpack(f"{endian}I", raw[1:5])
        offset = 5
        # EWKB SRID flag (0x20000000)
        if geom_type & 0x20000000:
            offset += 4
        if (geom_type & 0xFF) != 1 or len(raw) < offset + 16:
            return None
        lon, lat = struct.unpack(f"{endian}dd", raw[offset : offset + 16])
        return float(lon), float(lat)
    if isinstance(geom, str):
        match = _POINT_WKT_RE.search(geom)
        if match:
            return float(match.group(1)), float(match.group(2))
        return None
    if isinstance(geom, dict) and "lat" in geom and "lon" in geom:
        return float(geom["lon"]), float(geom["lat"])
    if isinstance(geom, (tuple, list)) and len(geom) == 2:
        return float(geom[0]), float(geom[1])
    return None


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
    county: Mapped[str] = mapped_column(String(120), nullable=False, default="Ličko-senjska")
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
    county: Mapped[str] = mapped_column(String(120), nullable=False, default="Ličko-senjska")
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
    county: Mapped[str] = mapped_column(String(120), nullable=False, default="Ličko-senjska")
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
    carpool_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    driver_registration_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    driver_insurance_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    driver_license_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    volunteer_partner: Mapped[str | None] = mapped_column(String(120), nullable=True)

    missed_visits_last_year: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consent_given: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    story: Mapped[str | None] = mapped_column(Text, nullable=True)

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
    facility_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("facilities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    facility_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    facility_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    facility_location: Mapped[Any | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=True,
    )
    department: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    facility: Mapped[Facility | None] = relationship("Facility", back_populates="slots")
    candidate_for_requests: Mapped[list[VisitRequest]] = relationship(
        "VisitRequest",
        secondary=visit_request_candidate_slots,
        back_populates="candidate_slots",
    )
    assignments: Mapped[list[Assignment]] = relationship("Assignment", back_populates="slot")

    @property
    def latitude(self) -> float | None:
        coords = extract_lon_lat(self.facility_location)
        if coords:
            return coords[1]
        if self.facility is not None:
            return self.facility.latitude
        return None

    @property
    def longitude(self) -> float | None:
        coords = extract_lon_lat(self.facility_location)
        if coords:
            return coords[0]
        if self.facility is not None:
            return self.facility.longitude
        return None


class VisitRequest(Base):
    """Zahtjev za pregled prema odjeljku 4 arhitekture."""

    __tablename__ = "visit_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    referral_ref: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    facility_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("facilities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    facility_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
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
    facility: Mapped[Facility | None] = relationship("Facility", back_populates="visit_requests")
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
    has_driver_assistance: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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
    backup_vehicle_id: Mapped[int | None] = mapped_column(
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
        default=AssignmentStatus.PREDLOZENO.value,
        index=True,
    )
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    carpool_confirmed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)

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
    backup_vehicle: Mapped[Vehicle | None] = relationship(
        "Vehicle", foreign_keys=[backup_vehicle_id]
    )
    trip_logs: Mapped[list[TripLog]] = relationship(
        "TripLog", back_populates="assignment", cascade="all, delete-orphan"
    )


class TripLog(Base):
    """Stvarna vremena vožnje i pregleda (ulaz za treniranje ML modela)."""

    __tablename__ = "trip_logs"

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
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    assignment: Mapped[Assignment | None] = relationship("Assignment", back_populates="trip_logs")
