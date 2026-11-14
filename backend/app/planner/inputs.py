"""Load one day's planner input from the database (E5-T1).

`load_problem` selects the requests that belong to the plan day, builds the pure `PlanProblem`
and returns it together with the pre-solve unserved list (rule 1: nothing is dropped silently)
and the ORM lookups the response builder needs. It never writes to the database.

Existing assignments on the day become `Pin`s (rule 2): locked, confirmed or modified ones.
Unpinned `proposed` assignments are ignored here; the persistence step replaces them.
Logs carry ids and counts only (rule 3).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date, time

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.adapters.routing import RoutingClient
from app.adapters.routing_ors import MAX_MATRIX_ROUTES
from app.adapters.types import AdapterError, LatLon
from app.codebooks import get_urgency_info
from app.models import (
    Assignment,
    AssignmentStatus,
    Facility,
    MobilityClass,
    Patient,
    RequestStatus,
    Slot,
    TransportEntitlement,
    Vehicle,
    VehicleProviderType,
    VisitRequest,
)
from app.plan_schemas import UnservedReason
from app.planner.eligibility import allowed_vehicles
from app.planner.estimates import boarding_minutes, visit_duration
from app.planner.problem import (
    ZAGREB,
    Pin,
    PlannerParams,
    PlanProblem,
    PRequest,
    PSlot,
    PUnserved,
    PVehicle,
    to_minutes,
)
from app.scoring import compute_score, get_scoring_config

logger = logging.getLogger("uvicorn.error")

# Assignment statuses that pin the request to its slot and vehicles.
PINNING_STATUSES = frozenset({AssignmentStatus.CONFIRMED.value, AssignmentStatus.MODIFIED.value})


class TooManyPointsError(AdapterError):
    """The day has more distinct points than one routing matrix call can take."""


@dataclass
class LoadedProblem:
    problem: PlanProblem
    unserved: list[PUnserved]
    patients: dict[int, Patient] = field(default_factory=dict)
    requests: dict[int, VisitRequest] = field(default_factory=dict)
    slots: dict[int, Slot] = field(default_factory=dict)
    vehicles: dict[int, Vehicle] = field(default_factory=dict)
    facilities: dict[int, Facility] = field(default_factory=dict)
    # Location index -> coordinates, in the order of the matrix.
    locations: list[LatLon] = field(default_factory=list)


def _skip_own_car(request: VisitRequest) -> bool:
    """Patients who drive themselves are not part of the plan (Q6).

    Temporary: brief 006 (carpool) changes this for patient-drivers; keep it the single place.
    """
    return request.patient.own_car


def _day_of(slot: Slot) -> date:
    return slot.start_time.astimezone(ZAGREB).date()


def _minutes_of_day(value: time) -> int:
    return value.hour * 60 + value.minute


def _pin_for(request: VisitRequest, day: date) -> Pin | None:
    pinned = [
        a
        for a in sorted(request.assignments, key=lambda a: a.id)
        if _day_of(a.slot) == day and (a.is_locked or a.status in PINNING_STATUSES)
    ]
    if not pinned:
        return None
    a = pinned[0]
    # The pickup time is pinned only when confirmed: the patient may already know it.
    pickup = (
        to_minutes(day, a.pickup_time) if a.status == AssignmentStatus.CONFIRMED.value else None
    )
    return Pin(
        slot_id=a.slot_id,
        vehicle_id=a.vehicle_id,
        return_vehicle_id=a.return_vehicle_id,
        pickup_min=pickup,
    )


def _has_assignment_on_other_day(request: VisitRequest, day: date) -> bool:
    return any(
        _day_of(a.slot) != day and a.status != AssignmentStatus.COMPLETED.value
        for a in request.assignments
    )


def _has_live_assignment_on_day(request: VisitRequest, day: date) -> bool:
    return any(
        _day_of(a.slot) == day and a.status != AssignmentStatus.COMPLETED.value
        for a in request.assignments
    )


class _Locations:
    """Dedupes points by coordinates into one ordered list."""

    def __init__(self) -> None:
        self.points: list[LatLon] = []
        self._index: dict[tuple[float, float], int] = {}

    def add(self, lat: float, lon: float) -> int:
        key = (lat, lon)
        if key not in self._index:
            self._index[key] = len(self.points)
            self.points.append(LatLon(lat, lon))
        return self._index[key]


def load_problem(
    session: Session, day: date, routing: RoutingClient, params: PlannerParams
) -> LoadedProblem:
    unserved: list[PUnserved] = []

    # --- Requests that belong to the day -------------------------------------------------
    candidates = session.scalars(
        select(VisitRequest)
        .where(VisitRequest.status.in_([RequestStatus.OPEN.value, RequestStatus.SCHEDULED.value]))
        .options(
            selectinload(VisitRequest.patient),
            selectinload(VisitRequest.facility),
            selectinload(VisitRequest.candidate_slots),
            selectinload(VisitRequest.assignments).selectinload(Assignment.slot),
        )
        .order_by(VisitRequest.id)
    ).all()

    selected: list[tuple[VisitRequest, list[Slot], Pin | None]] = []
    for request in candidates:
        has_assignment_today = _has_live_assignment_on_day(request, day)
        if request.status != RequestStatus.OPEN.value and not has_assignment_today:
            continue
        if _has_assignment_on_other_day(request, day):
            continue
        if _skip_own_car(request):
            continue
        pin = _pin_for(request, day)
        day_slots = [s for s in request.candidate_slots if _day_of(s) == day]
        if pin is None and not day_slots:
            # Candidates only on other days: not part of this day.
            if not request.candidate_slots and request.earliest_date <= day <= request.latest_date:
                unserved.append(PUnserved(request.id, UnservedReason.NO_SLOT_IN_WINDOW))
            continue
        if request.patient.latitude is None or request.patient.longitude is None:
            unserved.append(PUnserved(request.id, UnservedReason.LOCATION_MISSING))
            continue
        selected.append((request, day_slots, pin))

    # --- Vehicles, slots ------------------------------------------------------------------
    vehicle_rows = session.scalars(
        select(Vehicle).where(Vehicle.active.is_(True)).order_by(Vehicle.id)
    ).all()
    in_problem_ids = {r.id for r, _, _ in selected}
    slot_rows = [
        s
        for s in session.scalars(
            select(Slot)
            .options(selectinload(Slot.facility), selectinload(Slot.assignments))
            .order_by(Slot.id)
        ).all()
        if _day_of(s) == day
    ]

    locations = _Locations()
    p_vehicles: list[PVehicle] = []
    for v in vehicle_rows:
        p_vehicles.append(
            PVehicle(
                id=v.id,
                provider_type=VehicleProviderType(v.provider_type),
                seats=v.seats,
                wheelchair_spots=v.wheelchair_spots,
                stretcher_spots=v.stretcher_spots,
                shift_start_min=_minutes_of_day(v.shift_start),
                shift_end_min=_minutes_of_day(v.shift_end),
                depot=locations.add(v.latitude or 0.0, v.longitude or 0.0),
            )
        )

    p_slots: list[PSlot] = []
    facilities: dict[int, Facility] = {}
    for s in slot_rows:
        taken = sum(1 for a in s.assignments if a.request_id not in in_problem_ids)
        facilities[s.facility_id] = s.facility
        p_slots.append(
            PSlot(
                id=s.id,
                facility=locations.add(s.facility.latitude or 0.0, s.facility.longitude or 0.0),
                start_min=to_minutes(day, s.start_time),
                capacity_left=max(0, s.capacity - taken),
            )
        )

    # --- Request geometry (needed for the matrix) -----------------------------------------
    homes: dict[int, int] = {}
    request_facility: dict[int, int] = {}
    for request, _, _ in selected:
        patient = request.patient
        assert patient.latitude is not None and patient.longitude is not None
        homes[request.id] = locations.add(patient.latitude, patient.longitude)
        facilities[request.facility_id] = request.facility
        request_facility[request.id] = locations.add(
            request.facility.latitude or 0.0, request.facility.longitude or 0.0
        )

    # --- Matrix ---------------------------------------------------------------------------
    points = locations.points
    if len(points) ** 2 > MAX_MATRIX_ROUTES:
        raise TooManyPointsError(
            f"Too many distinct points for one routing matrix: {len(points)} "
            f"(limit {MAX_MATRIX_ROUTES} routes)"
        )
    matrix = routing.matrix(points)  # AdapterError propagates; no silent fallback.
    durations_min = [[math.ceil(sec / 60) for sec in row] for row in matrix.durations_s]
    distances_m = [list(row) for row in matrix.distances_m]

    # --- Requests -------------------------------------------------------------------------
    scoring_config = get_scoring_config()
    p_requests: list[PRequest] = []
    for request, day_slots, pin in selected:
        patient = request.patient
        home, facility = homes[request.id], request_facility[request.id]
        score = compute_score(
            patient_id=patient.id,
            mobility_class=patient.mobility_class,
            distance_km=distances_m[home][facility] / 1000,
            birth_year=patient.birth_year,
            lives_alone=patient.lives_alone,
            missed_visits_last_year=patient.missed_visits_last_year,
            phone_type=patient.phone_type,
            companion_available=patient.companion,
            config=scoring_config,
        )
        slot_ids = [s.id for s in day_slots]
        if pin is not None and pin.slot_id not in slot_ids:
            slot_ids.append(pin.slot_id)
        allowed = allowed_vehicles(
            mobility_class=patient.mobility_class,
            transport_entitlement=patient.transport_entitlement,
            support_level=score.level_key,
            companion=patient.companion,
            vehicles=p_vehicles,
        )
        p_requests.append(
            PRequest(
                id=request.id,
                patient_id=patient.id,
                home=home,
                facility=facility,
                mobility_class=MobilityClass(patient.mobility_class),
                companion=patient.companion,
                transport_entitlement=TransportEntitlement(patient.transport_entitlement),
                support_level=score.level_key,
                urgency_rank=get_urgency_info(request.urgency_class).unserved_penalty_rank,
                boarding_min=boarding_minutes(patient.mobility_class),
                visit_duration=visit_duration(request.department, request.visit_type),
                candidate_slot_ids=tuple(slot_ids),
                allowed_vehicle_ids=allowed,
                pin=pin,
            )
        )

    logger.info(
        "Planner input for %s: %d requests, %d unserved pre-solve, %d vehicles, %d slots, "
        "%d points",
        day,
        len(p_requests),
        len(unserved),
        len(p_vehicles),
        len(p_slots),
        len(points),
    )
    return LoadedProblem(
        problem=PlanProblem(
            day=day,
            durations_min=durations_min,
            distances_m=distances_m,
            vehicles=p_vehicles,
            slots=p_slots,
            requests=p_requests,
            params=params,
        ),
        unserved=unserved,
        patients={r.patient_id: r.patient for r, _, _ in selected},
        requests={r.id: r for r, _, _ in selected},
        slots={s.id: s for s in slot_rows},
        vehicles={v.id: v for v in vehicle_rows},
        facilities=facilities,
        locations=list(points),
    )
