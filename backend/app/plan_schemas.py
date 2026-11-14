"""Response contract for `GET /plan?date=` (dispatch dashboard, E9).

The planner (E5) fills this shape; until it exists `plan_mock.py` returns a fixed example.
Enum values are codes; the frontend shows Croatian labels from `GET /codebooks`.
Free-text reasons (`UnservedRequest.reason_text`) are Croatian because they reach the UI.

Never put the MBO in this response: the dashboard does not need it (CLAUDE.md rule 3).
"""

from __future__ import annotations

from datetime import date, datetime, time
from enum import StrEnum

from pydantic import BaseModel, Field

from app.models import (
    AssignmentStatus,
    Department,
    MobilityClass,
    TransportEntitlement,
    UrgencyClass,
    VehicleProviderType,
    VisitType,
)
from app.schemas import GeoPoint


class PlanSource(StrEnum):
    MOCK = "mock"
    SOLVER = "solver"


class StopKind(StrEnum):
    DEPOT_START = "depot_start"
    PICKUP_HOME = "pickup_home"
    DROPOFF_FACILITY = "dropoff_facility"
    PICKUP_FACILITY = "pickup_facility"
    DROPOFF_HOME = "dropoff_home"
    DEPOT_END = "depot_end"


class EstimateSource(StrEnum):
    """Same values as `Prediction.source` (ARHITEKTURA §7); a model fallback is only logged."""

    RULES = "rules"
    MODEL = "model"


class UnservedReason(StrEnum):
    NO_SLOT_IN_WINDOW = "no_slot_in_window"
    NO_ELIGIBLE_VEHICLE = "no_eligible_vehicle"
    NO_VEHICLE_CAPACITY = "no_vehicle_capacity"
    MAX_RIDE_TIME = "max_ride_time"
    LOCATION_MISSING = "location_missing"
    SOLVER_TIMEOUT = "solver_timeout"
    # Immobile patient (wheelchair/stretcher) without the sanitetski entitlement and no other
    # vehicle can take them; the nurse asks the chosen doctor for the order (rule 8).
    SANITETSKI_ORDER_NEEDED = "sanitetski_order_needed"


class Estimate(BaseModel):
    """A predicted value with its origin, for the source badge (E9-T9)."""

    minutes: int = Field(..., ge=0)
    source: EstimateSource
    version: str | None = None


class PlanFacility(BaseModel):
    id: int
    key: str
    name: str
    address: str | None = None
    location: GeoPoint


class PlanPatient(BaseModel):
    """What the dashboard shows about a patient. No MBO."""

    id: int
    first_name: str
    last_name: str
    phone: str
    address: str | None = None
    settlement: str
    municipality: str
    location: GeoPoint | None = None
    mobility_class: MobilityClass
    transport_entitlement: TransportEntitlement
    support_level: str = Field(..., description="Level key from scoring_factors.yaml")


class PlanSlot(BaseModel):
    id: int
    facility_id: int
    department: Department
    start_time: datetime
    end_time: datetime | None = None


class OutboundLeg(BaseModel):
    vehicle_id: int
    pickup_time: datetime
    facility_arrival_time: datetime


class ReturnLeg(BaseModel):
    vehicle_id: int
    pickup_time: datetime
    home_dropoff_time: datetime


class PlanAssignment(BaseModel):
    id: int
    request_id: int
    status: AssignmentStatus
    is_locked: bool
    patient: PlanPatient
    slot: PlanSlot
    visit_type: VisitType
    urgency_class: UrgencyClass
    outbound: OutboundLeg
    return_leg: ReturnLeg | None = Field(
        default=None, description="None when the patient returns on their own"
    )
    visit_duration: Estimate
    carpool_driver_confirmed: bool | None = None


class RouteStop(BaseModel):
    seq: int = Field(..., ge=0)
    kind: StopKind
    assignment_id: int | None = Field(default=None, description="None for depot stops")
    facility_id: int | None = Field(default=None, description="Set for facility stops")
    location: GeoPoint
    label: str = Field(..., description="Settlement or facility name, for the stop list")
    arrival_time: datetime
    departure_time: datetime


class PlanVehicle(BaseModel):
    id: int
    key: str | None = None
    name: str | None = None
    provider_type: VehicleProviderType
    seats: int
    wheelchair_spots: int
    stretcher_spots: int
    shift_start: time
    shift_end: time
    base_settlement: str | None = None
    base_location: GeoPoint
    driver_name: str | None = None
    driver_phone: str | None = None
    stops: list[RouteStop] = Field(default_factory=list, description="Ordered by seq")
    total_km: float | None = None
    total_minutes: int | None = None


class UnservedRequest(BaseModel):
    """A request the plan could not serve. Always shown, never hidden (rule 1)."""

    request_id: int
    patient: PlanPatient
    facility_id: int
    department: Department
    visit_type: VisitType
    urgency_class: UrgencyClass
    earliest_date: date
    latest_date: date
    reason: UnservedReason
    reason_text: str = Field(..., description="Croatian, shown to the dispatcher as is")


class PlanMetrics(BaseModel):
    """Before/after counters (E5-T8, E9-T7). Baseline = one round trip per patient."""

    served: int
    unserved: int
    vehicles_used: int
    planned_trips: int
    baseline_trips: int
    total_km: float
    baseline_km: float


class PlanResponse(BaseModel):
    date: date
    source: PlanSource
    generated_at: datetime
    facilities: list[PlanFacility]
    vehicles: list[PlanVehicle] = Field(description="Only vehicles with at least one stop")
    assignments: list[PlanAssignment]
    unserved: list[UnservedRequest]
    metrics: PlanMetrics | None = None
