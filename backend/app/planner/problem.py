"""Pure in-memory description of one day's planning problem and its solution.

Times are integer minutes from local midnight of the plan day (Europe/Zagreb). Conversion to
and from aware datetimes happens only at the DB/API boundary, with `to_minutes`/`from_minutes`.
Locations are indices into `durations_min` / `distances_m`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.models import MobilityClass, TransportEntitlement, VehicleProviderType
from app.plan_schemas import Estimate, StopKind, UnservedReason

ZAGREB = ZoneInfo("Europe/Zagreb")


def _midnight(day: date) -> datetime:
    return datetime.combine(day, time(0), tzinfo=ZAGREB)


def from_minutes(day: date, minutes: int) -> datetime:
    """Minutes from local midnight of `day` to an aware Europe/Zagreb datetime.

    Wall-clock arithmetic, so on DST change days minutes count wall-clock time.
    """
    return _midnight(day) + timedelta(minutes=minutes)


def to_minutes(day: date, moment: datetime) -> int:
    """Aware datetime to minutes from local midnight of `day` (inverse of `from_minutes`)."""
    if moment.tzinfo is None:
        raise ValueError("Naive datetime: planner times must be timezone-aware")
    local = moment.astimezone(ZAGREB)
    delta = local.replace(tzinfo=None) - datetime.combine(day, time(0))
    return int(delta.total_seconds() // 60)


@dataclass(frozen=True)
class PlannerParams:
    time_limit_s: int
    arrival_buffer_min: int
    max_early_arrival_min: int
    max_ride_extra_min: int
    max_return_wait_min: int
    pinned_time_tolerance_min: int

    @classmethod
    def from_settings(cls) -> PlannerParams:
        s = get_settings()
        return cls(
            time_limit_s=s.planner_time_limit_s,
            arrival_buffer_min=s.planner_arrival_buffer_min,
            max_early_arrival_min=s.planner_max_early_arrival_min,
            max_ride_extra_min=s.planner_max_ride_extra_min,
            max_return_wait_min=s.planner_max_return_wait_min,
            pinned_time_tolerance_min=s.planner_pinned_time_tolerance_min,
        )


@dataclass(frozen=True)
class PVehicle:
    id: int
    provider_type: VehicleProviderType
    seats: int
    wheelchair_spots: int
    stretcher_spots: int
    shift_start_min: int
    shift_end_min: int
    depot: int


@dataclass(frozen=True)
class PSlot:
    id: int
    facility: int
    start_min: int
    # Capacity minus assignments of requests that are not part of this problem.
    capacity_left: int


@dataclass(frozen=True)
class Pin:
    slot_id: int
    vehicle_id: int
    return_vehicle_id: int | None = None
    # Set only when the times themselves are pinned.
    pickup_min: int | None = None


@dataclass(frozen=True)
class PRequest:
    id: int
    patient_id: int
    home: int
    facility: int
    mobility_class: MobilityClass
    companion: bool
    transport_entitlement: TransportEntitlement
    support_level: str
    urgency_rank: int
    boarding_min: int
    # p90, used for the return window.
    visit_duration: Estimate
    # Slots on this day only.
    candidate_slot_ids: tuple[int, ...]
    allowed_vehicle_ids: frozenset[int]
    pin: Pin | None = None


@dataclass(frozen=True)
class PlanProblem:
    day: date
    durations_min: list[list[int]]
    distances_m: list[list[float]]
    vehicles: list[PVehicle]
    slots: list[PSlot]
    requests: list[PRequest]
    params: PlannerParams


@dataclass(frozen=True)
class PStop:
    vehicle_id: int
    kind: StopKind
    request_id: int | None
    location: int
    arrival_min: int
    departure_min: int


@dataclass(frozen=True)
class PAssignment:
    request_id: int
    slot_id: int
    vehicle_id: int
    pickup_min: int
    facility_arrival_min: int
    return_vehicle_id: int | None = None
    return_pickup_min: int | None = None
    home_dropoff_min: int | None = None


@dataclass(frozen=True)
class PUnserved:
    request_id: int
    reason: UnservedReason


@dataclass(frozen=True)
class SolveResult:
    assignments: list[PAssignment] = field(default_factory=list)
    routes: dict[int, list[PStop]] = field(default_factory=dict)
    unserved: list[PUnserved] = field(default_factory=list)


def demand(request: PRequest) -> tuple[int, int, int]:
    """(seats, wheelchair spots, stretcher spots) the request occupies; a companion adds a seat."""
    match request.mobility_class:
        case MobilityClass.WHEELCHAIR:
            base = (0, 1, 0)
        case MobilityClass.STRETCHER:
            base = (0, 0, 1)
        case _:
            base = (1, 0, 0)
    return (base[0] + (1 if request.companion else 0), base[1], base[2])
