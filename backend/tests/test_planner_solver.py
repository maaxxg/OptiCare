"""Solver and output-check tests (E5-T2, E5-T3, E5-T9 minimum). DB-free, hand-built problems.

Locations: 0 depot, 1 home A, 2 home B, 3 facility, 4 far depot. Travel is 10 min between any two
distinct near locations; location 4 is 100 min from everything.
"""

import dataclasses
import random
import time
from datetime import date

import pytest

from app.models import MobilityClass as M
from app.models import TransportEntitlement as E
from app.models import VehicleProviderType as P
from app.plan_schemas import Estimate, EstimateSource, StopKind, UnservedReason
from app.planner.check import PlanCheckError, check_solution
from app.planner.eligibility import allowed_vehicles
from app.planner.problem import (
    Pin,
    PlannerParams,
    PlanProblem,
    PRequest,
    PSlot,
    PVehicle,
    SolveResult,
)
from app.planner.solver import solve

BOARDING = 5


def params(**kw) -> PlannerParams:
    base = dict(
        time_limit_s=1,
        arrival_buffer_min=15,
        max_early_arrival_min=60,
        max_ride_extra_min=45,
        max_return_wait_min=60,
        pinned_time_tolerance_min=0,
    )
    return PlannerParams(**{**base, **kw})


def matrix(n=5, far=4) -> list[list[int]]:
    def d(a, b):
        if a == b:
            return 0
        return 100 if far in (a, b) else 10

    return [[d(a, b) for b in range(n)] for a in range(n)]


def veh(id_, ptype=P.RED_CROSS, seats=4, wc=0, st=0, start=360, end=960, depot=0):
    return PVehicle(id_, ptype, seats, wc, st, start, end, depot)


def req(
    id_,
    fleet,
    slots=(1,),
    mobility=M.WALKS,
    ent=E.NONE,
    home=1,
    urgency=0,
    level="low",
    pin=None,
    companion=False,
):
    return PRequest(
        id=id_,
        patient_id=id_,
        home=home,
        facility=3,
        mobility_class=mobility,
        companion=companion,
        transport_entitlement=ent,
        support_level=level,
        urgency_rank=urgency,
        boarding_min=BOARDING,
        visit_duration=Estimate(minutes=30, source=EstimateSource.RULES, version="t"),
        candidate_slot_ids=tuple(slots),
        allowed_vehicle_ids=allowed_vehicles(
            mobility_class=mobility,
            transport_entitlement=ent,
            support_level=level,
            companion=companion,
            vehicles=fleet,
        ),
        pin=pin,
    )


def problem(vehicles, slots, requests, **kw) -> PlanProblem:
    return PlanProblem(
        day=date(2026, 11, 16),
        durations_min=matrix(),
        distances_m=[[0.0] * 5 for _ in range(5)],
        vehicles=vehicles,
        slots=slots,
        requests=requests,
        params=params(**kw),
    )


def reasons(result: SolveResult) -> dict[int, UnservedReason]:
    return {u.request_id: u.reason for u in result.unserved}


def test_two_patients_one_vehicle_hand_checkable():
    fleet = [veh(1)]
    slot = PSlot(1, 3, 600, 5)  # arrival window [540, 585]
    p = problem(fleet, [slot], [req(1, fleet, home=1), req(2, fleet, home=2)])
    result = solve(p)
    assert not result.unserved and len(result.assignments) == 2
    kinds = [s.kind for s in result.routes[1]]
    assert kinds == [
        StopKind.DEPOT_START,
        StopKind.PICKUP_HOME,
        StopKind.PICKUP_HOME,
        StopKind.DROPOFF_FACILITY,
        StopKind.DROPOFF_FACILITY,
        StopKind.DEPOT_END,
    ]
    first, second, drop1, drop2 = result.routes[1][1:5]
    # Board 5 min, drive 10 min to the next stop.
    assert second.arrival_min >= first.arrival_min + BOARDING + 10
    assert drop1.arrival_min >= second.arrival_min + BOARDING + 10
    assert drop2.arrival_min >= drop1.arrival_min + BOARDING  # same place, no drive
    assert 540 <= drop1.arrival_min and drop2.arrival_min <= 585
    assert {a.slot_id for a in result.assignments} == {1}


def test_capacity_one_wheelchair_spot_urgent_served():
    fleet = [veh(1, P.SANITETSKI, seats=2, wc=1)]
    slot = PSlot(1, 3, 600, 5)
    reqs = [
        req(1, fleet, mobility=M.WHEELCHAIR, ent=E.SANITETSKI, home=1, urgency=0),
        req(2, fleet, mobility=M.WHEELCHAIR, ent=E.SANITETSKI, home=2, urgency=2),
    ]
    # Window [570, 585]: a second trip (back, board, drive) does not fit in 15 minutes.
    result = solve(problem(fleet, [slot], reqs, max_early_arrival_min=30))
    assert [a.request_id for a in result.assignments] == [2]
    assert reasons(result) == {1: UnservedReason.NO_VEHICLE_CAPACITY}


def test_rule_7_sanitetski_never_for_non_entitled():
    fleet = [veh(1, P.SANITETSKI, seats=2, wc=1)]
    slot = PSlot(1, 3, 600, 5)
    reqs = [
        req(1, fleet, mobility=M.WALKS, ent=E.NONE),
        req(2, fleet, mobility=M.WHEELCHAIR, ent=E.NONE, home=2),
    ]
    result = solve(problem(fleet, [slot], reqs))
    assert result.assignments == [] and result.routes == {}
    assert reasons(result) == {
        1: UnservedReason.NO_ELIGIBLE_VEHICLE,
        2: UnservedReason.SANITETSKI_ORDER_NEEDED,
    }


def test_no_candidate_slot_is_reported_and_not_overridden():
    fleet = [veh(1, P.SANITETSKI, seats=2, wc=1)]
    reqs = [req(1, fleet, slots=(), mobility=M.WHEELCHAIR, ent=E.NONE)]
    result = solve(problem(fleet, [PSlot(1, 3, 600, 5)], reqs))
    assert reasons(result) == {1: UnservedReason.NO_SLOT_IN_WINDOW}


def test_slot_choice_skips_unreachable_earlier_slot():
    fleet = [veh(1, start=480)]
    slots = [PSlot(1, 3, 400, 5), PSlot(2, 3, 600, 5)]  # slot 1 window ends 385, before the shift
    result = solve(problem(fleet, slots, [req(1, fleet, slots=(1, 2))]))
    assert [(a.request_id, a.slot_id) for a in result.assignments] == [(1, 2)]


def test_slot_capacity_left_is_respected():
    fleet = [veh(1)]
    reqs = [req(1, fleet, slots=(1,), home=1), req(2, fleet, slots=(1,), home=2)]
    result = solve(problem(fleet, [PSlot(1, 3, 600, 1)], reqs))
    assert len(result.assignments) == 1
    assert list(reasons(result).values()) == [UnservedReason.NO_VEHICLE_CAPACITY]

    # With a second slot of capacity 1 both are served, on different slots.
    reqs = [req(1, fleet, slots=(1, 2), home=1), req(2, fleet, slots=(1, 2), home=2)]
    result = solve(problem(fleet, [PSlot(1, 3, 600, 1), PSlot(2, 3, 700, 1)], reqs))
    assert sorted(a.slot_id for a in result.assignments) == [1, 2]


def test_pin_keeps_slot_and_vehicle_although_other_is_cheaper():
    fleet = [veh(1, depot=0), veh(2, depot=4)]  # vehicle 2 starts 100 min away
    slots = [PSlot(1, 3, 600, 5), PSlot(2, 3, 700, 5)]
    pin = Pin(slot_id=2, vehicle_id=2)
    result = solve(problem(fleet, slots, [req(1, fleet, slots=(1, 2), pin=pin)]))
    (a,) = result.assignments
    assert (a.slot_id, a.vehicle_id) == (2, 2)


def test_pinned_pickup_time_is_kept():
    fleet = [veh(1)]
    pin = Pin(slot_id=1, vehicle_id=1, pickup_min=530)
    result = solve(problem(fleet, [PSlot(1, 3, 600, 5)], [req(1, fleet, pin=pin)]))
    (a,) = result.assignments
    assert a.pickup_min == 530


def test_check_catches_corrupted_results():
    fleet = [veh(1, seats=2)]
    p = problem(fleet, [PSlot(1, 3, 600, 5)], [req(1, fleet, home=1), req(2, fleet, home=2)])
    result = solve(p)
    assert check_solution(p, result) == []

    # Over capacity: the same route on a one-seat vehicle.
    small = dataclasses.replace(p, vehicles=[veh(1, seats=1)])
    assert any("capacity" in v for v in check_solution(small, result))

    # Wrong vehicle type (rule 7): same route on a sanitetski vehicle, patients not entitled.
    sanitetski = dataclasses.replace(p, vehicles=[veh(1, P.SANITETSKI, seats=2)])
    assert any("sanitetski" in v for v in check_solution(sanitetski, result))

    # Served and unserved at once, and a vehicle that is not allowed.
    a = result.assignments[0]
    bad = SolveResult(
        assignments=[*result.assignments, dataclasses.replace(a, vehicle_id=9)],
        routes=result.routes,
        unserved=[],
    )
    assert check_solution(p, bad)
    assert check_solution(p, SolveResult())  # requests missing from the result


def test_solve_raises_when_check_fails(monkeypatch):
    fleet = [veh(1)]
    p = problem(fleet, [PSlot(1, 3, 600, 5)], [req(1, fleet)])
    monkeypatch.setattr("app.planner.solver.check_solution", lambda *_: ["forced"])
    with pytest.raises(PlanCheckError):
        solve(p)


def test_demo_size_problem_finishes_in_time():
    rng = random.Random(7)
    n_loc = 1 + 8 + 15 + 2  # depot, vehicle bases, homes, facilities
    pts = [(rng.uniform(0, 60), rng.uniform(0, 60)) for _ in range(n_loc)]
    dur = [[round(abs(a[0] - b[0]) + abs(a[1] - b[1])) for b in pts] for a in pts]
    fleet = [
        veh(i + 1, P.RED_CROSS if i % 2 else P.TAXI, seats=4, wc=1 if i % 2 else 0, depot=1 + i)
        for i in range(8)
    ]
    facilities = [n_loc - 2, n_loc - 1]
    slots = [PSlot(s + 1, facilities[s % 2], 540 + 45 * s, 3) for s in range(8)]
    reqs = []
    for i in range(15):
        r = req(
            i + 1,
            fleet,
            slots=tuple(rng.sample(range(1, 9), 4)),
            mobility=M.WHEELCHAIR if i % 5 == 0 else M.WALKS,
            home=9 + i,
            urgency=i % 3,
        )
        reqs.append(dataclasses.replace(r, facility=facilities[0]))
    p = PlanProblem(
        date(2026, 11, 16), dur, [[0.0] * n_loc] * n_loc, fleet, slots, reqs, params(time_limit_s=2)
    )
    started = time.monotonic()
    result = solve(p)  # also runs check_solution
    assert time.monotonic() - started < 4 + 1
    assert len(result.assignments) + len(result.unserved) == 15
    assert result.assignments


def test_pin_to_vehicle_not_in_problem_is_unserved_not_a_crash():
    fleet = [veh(1)]
    pin = Pin(slot_id=1, vehicle_id=99, return_vehicle_id=98)  # e.g. an inactive vehicle
    result = solve(problem(fleet, [PSlot(1, 3, 600, 5)], [req(1, fleet, pin=pin)]))
    assert result.assignments == []
    assert reasons(result) == {1: UnservedReason.NO_ELIGIBLE_VEHICLE}


def test_check_catches_corrupted_stop_data():
    fleet = [veh(1)]
    p = problem(fleet, [PSlot(1, 3, 600, 5)], [req(1, fleet)])
    result = solve(p)
    stops = result.routes[1]
    for idx, change in ((1, {"departure_min": stops[1].arrival_min}), (1, {"location": 2})):
        routes = {1: [*stops[:idx], dataclasses.replace(stops[idx], **change), *stops[idx + 1 :]]}
        bad = dataclasses.replace(result, routes=routes)
        assert check_solution(p, bad), change
