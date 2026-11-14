"""OR-Tools model: outbound rides with slot choice (E5-T2, E5-T3).

Pure and DB-free: `PlanProblem` in, `SolveResult` out. The output is verified by
`check_solution` before it is returned (rule 11).

Model
- One depot node per vehicle (start = end = its base). Per request and candidate slot
  ("alternative"): a `pickup_home` + `dropoff_facility` pair. Return trips (E5-T4) add a second
  pair per alternative the same way.
- Slot choice: a disjunction over the request's pickup nodes (max cardinality 1). The dropoff of
  an alternative is active iff its pickup is. Slot capacity bounds the active dropoffs per slot.
- Units: minutes and metres-free integers. Arc cost = travel minutes, plus a span cost of 1 per
  route minute (idle waiting is penalised), plus the drop penalties below.
- Drop penalty = DROP_PENALTY_BASE * 10**min(urgency_rank, MAX_URGENCY_RANK): far above any
  route cost (a day of travel is well under 10**4), so serving always beats dropping, and a more
  urgent request is dropped last. Pinned requests use PINNED_DROP_PENALTY, above every other.
  Scores never enter the cost otherwise (rule 1).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from app.plan_schemas import StopKind, UnservedReason
from app.planner import eligibility
from app.planner.check import PlanCheckError, check_solution
from app.planner.problem import (
    PAssignment,
    PlanProblem,
    PRequest,
    PStop,
    PUnserved,
    SolveResult,
    demand,
)

logger = logging.getLogger(__name__)

DROP_PENALTY_BASE = 100_000
MAX_URGENCY_RANK = 5
PINNED_DROP_PENALTY = 10**12
SPAN_COST = 1
HORIZON_MIN = 24 * 60


@dataclass
class _Alt:
    request: PRequest
    slot_id: int
    pickup: int  # node index
    dropoff: int


def _unserved_reason(request: PRequest, reason: UnservedReason) -> PUnserved:
    # Q2: an immobile patient without the entitlement is told to get the order, instead of a
    # generic vehicle reason (rule 8: the doctor issues it).
    if reason in (
        UnservedReason.NO_ELIGIBLE_VEHICLE,
        UnservedReason.NO_VEHICLE_CAPACITY,
    ) and eligibility.needs_sanitetski_order(request.mobility_class, request.transport_entitlement):
        reason = UnservedReason.SANITETSKI_ORDER_NEEDED
    return PUnserved(request.id, reason)


def solve(problem: PlanProblem) -> SolveResult:
    result = _solve(problem)
    violations = check_solution(problem, result)
    if violations:
        # Ids only; no personal data (rule 3).
        logger.error("planner output failed the check: %s", violations)
        raise PlanCheckError(violations)
    return result


def _solve(problem: PlanProblem) -> SolveResult:
    params = problem.params
    slots = {s.id: s for s in problem.slots}
    vehicle_index = {v.id: i for i, v in enumerate(problem.vehicles)}
    dur = problem.durations_min

    unserved: list[PUnserved] = []
    # Requests that enter the model, with their alternatives (slot ids).
    modelled: list[tuple[PRequest, list[int], list[int]]] = []
    for req in problem.requests:
        slot_ids = [
            sid for sid in req.candidate_slot_ids if sid in slots and slots[sid].capacity_left > 0
        ]
        vehicle_ids = [vid for vid in sorted(req.allowed_vehicle_ids) if vid in vehicle_index]
        if req.pin is not None:
            slot_ids = [sid for sid in slot_ids if sid == req.pin.slot_id]
            vehicle_ids = [vid for vid in vehicle_ids if vid == req.pin.vehicle_id]
        if not slot_ids:
            unserved.append(PUnserved(req.id, UnservedReason.NO_SLOT_IN_WINDOW))
        elif not vehicle_ids:
            unserved.append(_unserved_reason(req, UnservedReason.NO_ELIGIBLE_VEHICLE))
        else:
            modelled.append((req, slot_ids, vehicle_ids))

    if not modelled:
        return SolveResult(unserved=unserved)

    # Nodes: depots first (one per vehicle), then pickup/dropoff per alternative.
    node_loc: list[int] = [v.depot for v in problem.vehicles]
    node_service: list[int] = [0] * len(problem.vehicles)
    node_req: list[PRequest | None] = [None] * len(problem.vehicles)
    alts: list[_Alt] = []
    for req, slot_ids, _ in modelled:
        for sid in slot_ids:
            p = len(node_loc)
            node_loc += [req.home, slots[sid].facility]
            node_service += [req.boarding_min, req.boarding_min]
            node_req += [req, req]
            alts.append(_Alt(req, sid, p, p + 1))

    n_veh = len(problem.vehicles)
    starts = list(range(n_veh))
    manager = pywrapcp.RoutingIndexManager(len(node_loc), n_veh, starts, starts)
    routing = pywrapcp.RoutingModel(manager)
    solver = routing.solver()

    def travel(i: int, j: int) -> int:
        return dur[node_loc[manager.IndexToNode(i)]][node_loc[manager.IndexToNode(j)]]

    def transit(i: int, j: int) -> int:
        return travel(i, j) + node_service[manager.IndexToNode(i)]

    travel_cb = routing.RegisterTransitCallback(travel)
    transit_cb = routing.RegisterTransitCallback(transit)
    routing.SetArcCostEvaluatorOfAllVehicles(travel_cb)

    routing.AddDimension(transit_cb, HORIZON_MIN, HORIZON_MIN, False, "Time")
    time_dim = routing.GetDimensionOrDie("Time")
    time_dim.SetSpanCostCoefficientForAllVehicles(SPAN_COST)
    for i, v in enumerate(problem.vehicles):
        time_dim.CumulVar(routing.Start(i)).SetRange(v.shift_start_min, v.shift_end_min)
        time_dim.CumulVar(routing.End(i)).SetRange(v.shift_start_min, v.shift_end_min)

    # Capacity dimensions: seats, wheelchair places, stretcher places.
    def load_callback(k: int) -> Callable[[int], int]:
        sign = {a.pickup: 1 for a in alts} | {a.dropoff: -1 for a in alts}
        by_node = {a.pickup: demand(a.request)[k] for a in alts} | {
            a.dropoff: demand(a.request)[k] for a in alts
        }

        def cb(i: int) -> int:
            node = manager.IndexToNode(i)
            return sign.get(node, 0) * by_node.get(node, 0)

        return cb

    for k, name in enumerate(("Seats", "Wheelchair", "Stretcher")):
        cb_idx = routing.RegisterUnaryTransitCallback(load_callback(k))
        caps = [(v.seats, v.wheelchair_spots, v.stretcher_spots)[k] for v in problem.vehicles]
        routing.AddDimensionWithVehicleCapacity(cb_idx, 0, caps, True, name)

    # Per request: vehicle restriction, windows, disjunction, pairs.
    slot_dropoffs: dict[int, list[int]] = {}
    alts_by_req: dict[int, list[_Alt]] = {}
    for a in alts:
        alts_by_req.setdefault(a.request.id, []).append(a)
    allowed_by_req = {req.id: vids for req, _, vids in modelled}

    for req, _, _ in modelled:
        pinned = req.pin is not None
        allowed_idx = [vehicle_index[v] for v in allowed_by_req[req.id]] + [-1]
        pickups = []
        for a in alts_by_req[req.id]:
            p_idx = manager.NodeToIndex(a.pickup)
            d_idx = manager.NodeToIndex(a.dropoff)
            slot = slots[a.slot_id]
            routing.VehicleVar(p_idx).SetValues(allowed_idx)
            routing.VehicleVar(d_idx).SetValues(allowed_idx)
            solver.Add(routing.VehicleVar(p_idx) == routing.VehicleVar(d_idx))
            routing.AddPickupAndDelivery(p_idx, d_idx)
            solver.Add(routing.ActiveVar(p_idx) == routing.ActiveVar(d_idx))

            cum_p = time_dim.CumulVar(p_idx)
            cum_d = time_dim.CumulVar(d_idx)
            cum_d.SetRange(
                slot.start_min - params.max_early_arrival_min,
                slot.start_min - params.arrival_buffer_min,
            )
            if req.pin is not None and req.pin.pickup_min is not None:
                tol = params.pinned_time_tolerance_min
                cum_p.SetRange(req.pin.pickup_min - tol, req.pin.pickup_min + tol)
            # Pickup before dropoff and the ride limit, only enforced when the pair is active.
            ride = solver.ConditionalExpression(routing.ActiveVar(d_idx), cum_d - cum_p, 0)
            solver.Add(ride >= 0)
            max_ride = dur[req.home][slot.facility] + req.boarding_min + params.max_ride_extra_min
            solver.Add(ride <= max_ride)

            slot_dropoffs.setdefault(a.slot_id, []).append(d_idx)
            pickups.append(p_idx)
        penalty = (
            PINNED_DROP_PENALTY
            if pinned
            else DROP_PENALTY_BASE * 10 ** min(max(req.urgency_rank, 0), MAX_URGENCY_RANK)
        )
        routing.AddDisjunction(pickups, penalty, 1)
        # Dropoff nodes are only reachable together with their pickup (ActiveVar equality), so
        # they need no disjunction of their own beyond a zero-penalty one that allows dropping.
        for a in alts_by_req[req.id]:
            routing.AddDisjunction([manager.NodeToIndex(a.dropoff)], 0, 1)

    for sid, d_idxs in slot_dropoffs.items():
        solver.Add(sum(routing.ActiveVar(d) for d in d_idxs) <= slots[sid].capacity_left)

    search = pywrapcp.DefaultRoutingSearchParameters()
    search.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    )
    search.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search.time_limit.seconds = params.time_limit_s

    solution = routing.SolveWithParameters(search)
    if solution is None:
        logger.warning("planner: no solution for %d requests", len(modelled))
        unserved += [PUnserved(req.id, UnservedReason.SOLVER_TIMEOUT) for req, _, _ in modelled]
        return SolveResult(unserved=unserved)

    # Extract.
    assignments: list[PAssignment] = []
    routes: dict[int, list[PStop]] = {}
    served_ids: set[int] = set()
    for i, v in enumerate(problem.vehicles):
        index = routing.Start(i)
        if routing.IsEnd(solution.Value(routing.NextVar(index))):
            continue
        stops: list[PStop] = []
        while True:
            node = manager.IndexToNode(index)
            arrival = solution.Value(time_dim.CumulVar(index))
            if routing.IsStart(index):
                kind, rid = StopKind.DEPOT_START, None
            elif routing.IsEnd(index):
                kind, rid = StopKind.DEPOT_END, None
            else:
                req_here = node_req[node]
                assert req_here is not None
                rid = req_here.id
                is_pickup = any(a.pickup == node for a in alts_by_req[rid])
                kind = StopKind.PICKUP_HOME if is_pickup else StopKind.DROPOFF_FACILITY
            service = 0 if rid is None else node_service[node]
            location = v.depot if rid is None else node_loc[node]
            stops.append(PStop(v.id, kind, rid, location, arrival, arrival + service))
            if routing.IsEnd(index):
                break
            index = solution.Value(routing.NextVar(index))
        routes[v.id] = stops

    for a in alts:
        p_idx = manager.NodeToIndex(a.pickup)
        if solution.Value(routing.NextVar(p_idx)) == p_idx:
            continue  # inactive
        d_idx = manager.NodeToIndex(a.dropoff)
        veh = problem.vehicles[solution.Value(routing.VehicleVar(p_idx))]
        assignments.append(
            PAssignment(
                request_id=a.request.id,
                slot_id=a.slot_id,
                vehicle_id=veh.id,
                pickup_min=solution.Value(time_dim.CumulVar(p_idx)),
                facility_arrival_min=solution.Value(time_dim.CumulVar(d_idx)),
            )
        )
        served_ids.add(a.request.id)

    for req, _, _ in modelled:
        if req.id not in served_ids:
            unserved.append(_unserved_reason(req, UnservedReason.NO_VEHICLE_CAPACITY))
    return SolveResult(assignments=assignments, routes=routes, unserved=unserved)
