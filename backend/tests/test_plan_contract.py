"""GET /plan contract: shape, internal references, and no MBO in the response."""

from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.plan_schemas import PlanResponse, StopKind


def _get(day: str = "2026-11-16") -> dict:
    with TestClient(app) as client:
        response = client.get("/plan", params={"date": day})
    assert response.status_code == 200
    return response.json()


def test_plan_validates_and_uses_requested_date() -> None:
    body = _get()
    plan = PlanResponse.model_validate(body)
    assert plan.date == date(2026, 11, 16)
    assert all(a.slot.start_time.date() == plan.date for a in plan.assignments)
    assert all(a.slot.start_time.utcoffset() is not None for a in plan.assignments)


def test_plan_references_are_consistent() -> None:
    plan = PlanResponse.model_validate(_get())
    vehicle_ids = {v.id for v in plan.vehicles}
    facility_ids = {f.id for f in plan.facilities}
    assignment_ids = {a.id for a in plan.assignments}

    for a in plan.assignments:
        assert a.outbound.vehicle_id in vehicle_ids
        assert a.return_leg is None or a.return_leg.vehicle_id in vehicle_ids
        assert a.slot.facility_id in facility_ids
    for v in plan.vehicles:
        assert [s.seq for s in v.stops] == list(range(len(v.stops)))
        assert v.stops[0].kind == StopKind.DEPOT_START
        assert v.stops[-1].kind == StopKind.DEPOT_END
        for s in v.stops:
            assert s.arrival_time <= s.departure_time
            if s.kind in (StopKind.DEPOT_START, StopKind.DEPOT_END):
                assert s.assignment_id is None
            else:
                assert s.assignment_id in assignment_ids
    for u in plan.unserved:
        assert u.reason_text.strip()
        assert u.request_id not in {a.request_id for a in plan.assignments}


def test_plan_never_contains_mbo() -> None:
    assert "mbo" not in TestClient(app).get("/plan").text.lower()
