from __future__ import annotations

import re
from datetime import date, datetime, time
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ModelWrapValidatorHandler,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_core import InitErrorDetails, PydanticCustomError

from app.models import (
    AssignmentStatus,
    Department,
    DriverStatusEvent,
    MobilityClass,
    PhoneType,
    RequestStatus,
    TransportEntitlement,
    UrgencyClass,
    VehicleProviderType,
    VisitType,
    extract_lon_lat,
)

_MBO_RE = re.compile(r"^\d{9}$")


class GeoPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    lat: float = Field(..., ge=-90.0, le=90.0, description="Geografska širina (WGS84)")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Geografska dužina (WGS84)")


def _coerce_geopoint(val: Any) -> GeoPoint | None:
    if val is None or isinstance(val, GeoPoint):
        return val
    coords = extract_lon_lat(val)
    if coords is not None:
        lon, lat = coords
        return GeoPoint(lat=lat, lon=lon)
    if isinstance(val, dict) and "lat" in val and "lon" in val:
        return GeoPoint(lat=float(val["lat"]), lon=float(val["lon"]))
    return None


# ---------------------------------------------------------------------------
# Municipality
# ---------------------------------------------------------------------------


class MunicipalityBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    county: str = Field(default="Ličko-senjska", max_length=120)
    population_65_plus_share: float | None = Field(default=None, ge=0.0, le=1.0)


class MunicipalityCreate(MunicipalityBase):
    boundary_wkt: str = Field(..., min_length=10, description="POLYGON ili MULTIPOLYGON WKT")


class MunicipalityRead(MunicipalityBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


# ---------------------------------------------------------------------------
# Facility
# ---------------------------------------------------------------------------


class FacilityBase(BaseModel):
    key: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=200)
    level: str = Field(default="secondary", max_length=32)
    address: str | None = Field(default=None, max_length=255)
    settlement: str = Field(..., min_length=1, max_length=120)
    municipality: str = Field(..., min_length=1, max_length=120)
    county: str = Field(default="Ličko-senjska", max_length=120)
    location: GeoPoint

    @field_validator("location", mode="before")
    @classmethod
    def _validate_location(cls, v: Any) -> Any:
        coerced = _coerce_geopoint(v)
        return coerced if coerced is not None else v


class FacilityCreate(FacilityBase):
    pass


class FacilityRead(FacilityBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    latitude: float | None = None
    longitude: float | None = None


# ---------------------------------------------------------------------------
# Patient
# ---------------------------------------------------------------------------


class PatientBase(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    key: str | None = Field(default=None, max_length=32)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    birth_year: int | None = Field(default=None, ge=1900, le=2100)
    phone: str = Field(..., min_length=3, max_length=40)
    phone_type: PhoneType = Field(default=PhoneType.LANDLINE)

    address: str | None = Field(default=None, max_length=255)
    settlement: str = Field(..., min_length=1, max_length=120)
    municipality: str = Field(..., min_length=1, max_length=120)
    county: str = Field(default="Ličko-senjska", max_length=120)
    location: GeoPoint | None = None

    mobility_class: MobilityClass = Field(default=MobilityClass.WALKS)
    lives_alone: bool = False
    companion: bool = False
    floor: int = Field(default=0, ge=-2, le=50)
    elevator: bool = False

    transport_entitlement: TransportEntitlement = Field(default=TransportEntitlement.NONE)
    social_order_today: bool = False

    own_car: bool = False
    carpool_driver_seats: int = Field(default=0, ge=0, le=8)
    carpool_consent: bool = False

    driver_registration_valid: bool = False
    driver_insurance_valid: bool = False
    driver_license_valid: bool = False
    volunteer_partner: str | None = Field(default=None, max_length=120)

    missed_visits_last_year: int = Field(default=0, ge=0)
    consent_given: bool = True
    story: str | None = None

    @field_validator("location", mode="before")
    @classmethod
    def _validate_location(cls, v: Any) -> Any:
        return _coerce_geopoint(v)


class PatientCreate(PatientBase):
    model_config = ConfigDict(hide_input_in_errors=True)

    mbo: str = Field(
        ...,
        repr=False,
        description="Matični broj osigurane osobe (9 znamenki)",
    )

    @model_validator(mode="wrap")
    @classmethod
    def _mask_mbo_in_errors(cls, data: Any, handler: ModelWrapValidatorHandler[Any]) -> Any:
        # `hide_input_in_errors` only affects str(); `.errors()` (used by FastAPI for
        # 422 bodies) still carries the input. Rebuild the error without the MBO value.
        try:
            return handler(data)
        except ValidationError as exc:
            lines: list[InitErrorDetails] = []
            for err in exc.errors():
                is_mbo = err["loc"][:1] == ("mbo",)
                kind: Any = (
                    PydanticCustomError(err["type"], err["msg"])
                    if err["type"] == "mbo_format"
                    else err["type"]
                )
                line: InitErrorDetails = {
                    "type": kind,
                    "loc": err["loc"],
                    "input": "***" if is_mbo else err["input"],
                }
                if "ctx" in err and not is_mbo:
                    line["ctx"] = err["ctx"]
                lines.append(line)
            raise ValidationError.from_exception_data(
                cls.__name__, lines, hide_input=True
            ) from None

    @field_validator("mbo")
    @classmethod
    def _validate_mbo(cls, v: str) -> str:
        cleaned = v.strip()
        if not _MBO_RE.match(cleaned):
            raise PydanticCustomError("mbo_format", "MBO mora sadržavati točno 9 znamenki")
        return cleaned


class PatientUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    birth_year: int | None = Field(default=None, ge=1900, le=2100)
    phone: str | None = Field(default=None, min_length=3, max_length=40)
    phone_type: PhoneType | None = None
    address: str | None = None
    settlement: str | None = None
    municipality: str | None = None
    county: str | None = None
    location: GeoPoint | None = None
    mobility_class: MobilityClass | None = None
    lives_alone: bool | None = None
    companion: bool | None = None
    floor: int | None = Field(default=None, ge=-2, le=50)
    elevator: bool | None = None
    transport_entitlement: TransportEntitlement | None = None
    social_order_today: bool | None = None
    own_car: bool | None = None
    carpool_driver_seats: int | None = Field(default=None, ge=0, le=8)
    carpool_consent: bool | None = None
    driver_registration_valid: bool | None = None
    driver_insurance_valid: bool | None = None
    driver_license_valid: bool | None = None
    volunteer_partner: str | None = None
    missed_visits_last_year: int | None = Field(default=None, ge=0)
    consent_given: bool | None = None
    story: str | None = None

    @field_validator("location", mode="before")
    @classmethod
    def _validate_location(cls, v: Any) -> Any:
        return _coerce_geopoint(v)


class PatientRead(PatientBase):
    model_config = ConfigDict(from_attributes=True, hide_input_in_errors=True)

    id: int
    name: str
    mbo_masked: str
    latitude: float | None = None
    longitude: float | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Slot
# ---------------------------------------------------------------------------


class SlotBase(BaseModel):
    facility_id: int | None = None
    facility_key: str = Field(..., min_length=1, max_length=64)
    facility_name: str | None = Field(default=None, max_length=200)
    facility_location: GeoPoint | None = None
    department: Department
    start_time: datetime
    end_time: datetime | None = None
    capacity: int = Field(default=1, ge=1)

    @field_validator("facility_location", mode="before")
    @classmethod
    def _validate_facility_location(cls, v: Any) -> Any:
        return _coerce_geopoint(v)


class SlotCreate(SlotBase):
    pass


class SlotRead(SlotBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    latitude: float | None = None
    longitude: float | None = None


# ---------------------------------------------------------------------------
# VisitRequest
# ---------------------------------------------------------------------------


class VisitRequestBase(BaseModel):
    patient_id: int
    referral_ref: str | None = Field(default=None, max_length=64)
    facility_id: int | None = None
    facility_key: str = Field(..., min_length=1, max_length=64)
    department: Department
    visit_type: VisitType
    urgency_class: UrgencyClass
    earliest_date: date
    latest_date: date
    recurrence: str | None = Field(default=None, max_length=64)
    preferred_time_of_day: str | None = Field(default=None, max_length=32)
    slot_request_pending: bool = False
    status: RequestStatus = Field(default=RequestStatus.OPEN)

    @model_validator(mode="after")
    def _check_dates(self) -> VisitRequestBase:
        if self.latest_date < self.earliest_date:
            raise PydanticCustomError(
                "date_order", "Najkasniji datum ne smije biti prije najranijeg."
            )
        return self


class VisitRequestCreate(VisitRequestBase):
    candidate_slot_ids: list[int] = Field(default_factory=list)


class VisitRequestRead(VisitRequestBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    candidate_slots: list[SlotRead] = Field(default_factory=list)
    created_at: datetime


# ---------------------------------------------------------------------------
# Vehicle
# ---------------------------------------------------------------------------


class VehicleBase(BaseModel):
    key: str | None = Field(default=None, max_length=64)
    name: str | None = Field(default=None, max_length=120)
    provider_type: VehicleProviderType
    seats: int = Field(default=3, ge=0, le=50)
    wheelchair_spots: int = Field(default=0, ge=0, le=10)
    stretcher_spots: int = Field(default=0, ge=0, le=5)
    shift_start: time = Field(default=time(6, 0))
    shift_end: time = Field(default=time(18, 0))
    base_settlement: str | None = Field(default=None, max_length=120)
    base_municipality: str | None = Field(default=None, max_length=120)
    base_location: GeoPoint
    driver_name: str | None = Field(default=None, max_length=120)
    driver_phone: str | None = Field(default=None, max_length=40)
    patient_driver_id: int | None = None
    has_driver_assistance: bool = True
    active: bool = True

    @field_validator("base_location", mode="before")
    @classmethod
    def _validate_base_location(cls, v: Any) -> Any:
        coerced = _coerce_geopoint(v)
        return coerced if coerced is not None else v


class VehicleCreate(VehicleBase):
    pass


class VehicleRead(VehicleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    latitude: float | None = None
    longitude: float | None = None


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------


class AssignmentBase(BaseModel):
    request_id: int
    slot_id: int
    vehicle_id: int
    return_vehicle_id: int | None = None
    backup_vehicle_id: int | None = None
    pickup_time: datetime
    facility_arrival_time: datetime | None = None
    return_pickup_time: datetime | None = None
    home_dropoff_time: datetime | None = None
    pickup_order: int | None = Field(default=None, ge=0)
    return_order: int | None = Field(default=None, ge=0)
    status: AssignmentStatus = Field(default=AssignmentStatus.PREDLOZENO)
    is_locked: bool = False
    carpool_confirmed: bool | None = None
    distance_km: float | None = Field(default=None, ge=0.0)


class AssignmentCreate(AssignmentBase):
    pass


class AssignmentUpdate(BaseModel):
    slot_id: int | None = None
    vehicle_id: int | None = None
    return_vehicle_id: int | None = None
    backup_vehicle_id: int | None = None
    pickup_time: datetime | None = None
    facility_arrival_time: datetime | None = None
    return_pickup_time: datetime | None = None
    home_dropoff_time: datetime | None = None
    pickup_order: int | None = Field(default=None, ge=0)
    return_order: int | None = Field(default=None, ge=0)
    status: AssignmentStatus | None = None
    is_locked: bool | None = None
    carpool_confirmed: bool | None = None
    distance_km: float | None = Field(default=None, ge=0.0)


class AssignmentRead(AssignmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# TripLog
# ---------------------------------------------------------------------------


class TripLogBase(BaseModel):
    assignment_id: int | None = None
    actual_arrival_at_door: datetime | None = None
    actual_departure_from_door: datetime | None = None
    actual_check_in_at_facility: datetime | None = None
    actual_check_out_from_facility: datetime | None = None
    actual_dropoff_at_home: datetime | None = None
    driver_status_event: DriverStatusEvent | None = None
    recorded_by: str | None = Field(default=None, max_length=32)
    distance_km: float | None = Field(default=None, ge=0.0)

    department: Department | None = None
    visit_type: VisitType | None = None
    mobility_class: MobilityClass | None = None
    floor: int | None = None
    elevator: bool | None = None
    companion: bool | None = None
    patient_age: int | None = Field(default=None, ge=0, le=120)
    notes: str | None = None


class TripLogCreate(TripLogBase):
    pass


class TripLogRead(TripLogBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
