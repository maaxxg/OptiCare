"""Independent check of a solver result against the hard constraints (CLAUDE.md rule 11).

Recomputes everything from the `PlanProblem` and the returned routes/assignments; it does not
use any solver internals. Returns human-readable violations (ids only, no personal data).
"""

from __future__ import annotations

from collections import Counter

from app.models import TransportEntitlement, VehicleProviderType
from app.plan_schemas import StopKind
from app.planner.problem import PlanProblem, SolveResult, demand


class PlanCheckError(Exception):
    def __init__(self, violations: list[str]):
        super().__init__(f"{len(violations)} plan violation(s): " + "; ".join(violations))
        self.violations = violations


def check_solution(problem: PlanProblem, result: SolveResult) -> list[str]:
    errors: list[str] = []
    params = problem.params
    requests = {r.id: r for r in problem.requests}
    vehicles = {v.id: v for v in problem.vehicles}
    slots = {s.id: s for s in problem.slots}
    dur = problem.durations_min

    # Every request is served or unserved: exactly once, none missing.
    served = Counter(a.request_id for a in result.assignments)
    unserved = Counter(u.request_id for u in result.unserved)
    for rid in requests:
        if served[rid] + unserved[rid] != 1:
            errors.append(f"request {rid}: served {served[rid]}x, unserved {unserved[rid]}x")
    for rid in (*served, *unserved):
        if rid not in requests:
            errors.append(f"unknown request {rid} in result")

    assignments = {a.request_id: a for a in result.assignments if a.request_id in requests}

    # Routes: structure, travel times, shift, load.
    pickups: dict[int, tuple[int, int, int]] = {}  # request -> (vehicle, position, arrival)
    dropoffs: dict[int, tuple[int, int, int]] = {}
    for vid, stops in result.routes.items():
        veh = vehicles.get(vid)
        if veh is None:
            errors.append(f"route of unknown vehicle {vid}")
            continue
        if (
            len(stops) < 2
            or stops[0].kind != StopKind.DEPOT_START
            or stops[-1].kind != StopKind.DEPOT_END
        ):
            errors.append(f"vehicle {vid}: route must start and end at the depot")
            continue
        if stops[0].arrival_min < veh.shift_start_min or stops[-1].arrival_min > veh.shift_end_min:
            errors.append(f"vehicle {vid}: outside shift")
        load = [0, 0, 0]
        prev_loc: int | None = None
        prev_departure = 0
        cap = (veh.seats, veh.wheelchair_spots, veh.stretcher_spots)
        for i, stop in enumerate(stops):
            if stop.vehicle_id != vid:
                errors.append(f"vehicle {vid}: stop of another vehicle")
            req = requests.get(stop.request_id) if stop.request_id is not None else None
            # Location and service time come from the problem, not from the stop under test.
            if stop.kind in (StopKind.DEPOT_START, StopKind.DEPOT_END):
                expected_loc: int | None = veh.depot
                service = 0
            elif req is None:
                expected_loc, service = None, 0
            else:
                service = req.boarding_min
                if stop.kind == StopKind.PICKUP_HOME:
                    expected_loc = req.home
                else:
                    a = assignments.get(req.id)
                    slot = slots.get(a.slot_id) if a is not None else None
                    expected_loc = slot.facility if slot is not None else None
            if expected_loc is not None and stop.location != expected_loc:
                errors.append(f"vehicle {vid}: stop {i} is at the wrong location")
            if stop.departure_min - stop.arrival_min != service:
                errors.append(f"vehicle {vid}: stop {i} has a wrong service time")
            if i > 0 and expected_loc is not None and prev_loc is not None:
                if stop.arrival_min < prev_departure + dur[prev_loc][expected_loc]:
                    errors.append(f"vehicle {vid}: stop {i} reached faster than travel time")
            prev_loc = expected_loc
            prev_departure = stop.arrival_min + service
            if stop.kind not in (StopKind.PICKUP_HOME, StopKind.DROPOFF_FACILITY):
                continue
            if req is None:
                errors.append(f"vehicle {vid}: stop {i} has an unknown request")
                continue
            sign = 1 if stop.kind == StopKind.PICKUP_HOME else -1
            for k, amount in enumerate(demand(req)):
                load[k] += sign * amount
            if any(load[k] > cap[k] for k in range(3)):
                errors.append(f"vehicle {vid}: capacity exceeded at stop {i}")
            target = pickups if stop.kind == StopKind.PICKUP_HOME else dropoffs
            if req.id in target:
                errors.append(f"request {req.id}: duplicate {stop.kind} stop")
            target[req.id] = (vid, i, stop.arrival_min)
        if any(load):
            errors.append(f"vehicle {vid}: route does not end empty")

    # Stops belong to served requests only.
    for rid in (*pickups, *dropoffs):
        if rid not in assignments:
            errors.append(f"request {rid}: has stops but is not served")

    # Per assignment.
    slot_use: Counter[int] = Counter()
    for rid, a in assignments.items():
        req = requests[rid]
        slot = slots.get(a.slot_id)
        veh = vehicles.get(a.vehicle_id)
        if slot is None or a.slot_id not in req.candidate_slot_ids:
            errors.append(f"request {rid}: slot {a.slot_id} is not a candidate")
            continue
        slot_use[a.slot_id] += 1
        if veh is None or a.vehicle_id not in req.allowed_vehicle_ids:
            errors.append(f"request {rid}: vehicle {a.vehicle_id} not allowed")
        elif (
            veh.provider_type == VehicleProviderType.SANITETSKI
            and req.transport_entitlement != TransportEntitlement.SANITETSKI
        ):
            errors.append(f"request {rid}: sanitetski vehicle without entitlement")  # rule 7
        p, d = pickups.get(rid), dropoffs.get(rid)
        if p is None or d is None:
            errors.append(f"request {rid}: missing pickup or dropoff stop")
            continue
        if p[0] != a.vehicle_id or d[0] != a.vehicle_id:
            errors.append(f"request {rid}: stops are not on the assigned vehicle")
        if p[1] >= d[1]:
            errors.append(f"request {rid}: pickup is not before dropoff")
        if p[2] != a.pickup_min or d[2] != a.facility_arrival_min:
            errors.append(f"request {rid}: assignment times differ from the route")
        lo = slot.start_min - params.max_early_arrival_min
        hi = slot.start_min - params.arrival_buffer_min
        if not lo <= d[2] <= hi:
            errors.append(f"request {rid}: facility arrival outside the slot window")
        limit = dur[req.home][slot.facility] + req.boarding_min + params.max_ride_extra_min
        if d[2] - p[2] > limit:
            errors.append(f"request {rid}: ride time over the limit")
        if req.pin is not None:
            if a.slot_id != req.pin.slot_id or a.vehicle_id != req.pin.vehicle_id:
                errors.append(f"request {rid}: pin not respected")
            elif (
                req.pin.pickup_min is not None
                and abs(p[2] - req.pin.pickup_min) > params.pinned_time_tolerance_min
            ):
                errors.append(f"request {rid}: pinned pickup time not respected")

    for sid, used in slot_use.items():
        if used > slots[sid].capacity_left:
            errors.append(f"slot {sid}: capacity exceeded")
    return errors
