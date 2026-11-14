"""Opt-in DB tests for loading one day's planner input (E5-T1), on the synthetic seed."""

from __future__ import annotations

import os
from collections.abc import Generator
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.adapters.routing import MockRoutingClient
from app.db import SessionLocal
from app.models import (
    Assignment,
    AssignmentStatus,
    Patient,
    TransportEntitlement,
    VehicleProviderType,
    VisitRequest,
)
from app.plan_schemas import UnservedReason
from app.planner.inputs import LoadedProblem, load_problem
from app.planner.problem import ZAGREB, PlannerParams
from app.seed import seed_database

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="DB tests are opt-in: set RUN_DB_TESTS=1 and start the db service",
)

PARAMS = PlannerParams(
    time_limit_s=5,
    arrival_buffer_min=15,
    max_early_arrival_min=60,
    max_ride_extra_min=45,
    max_return_wait_min=60,
    pinned_time_tolerance_min=0,
)


@pytest.fixture
def db(migrated: None) -> Generator[Session, None, None]:
    with SessionLocal() as session:
        seed_database(session)
        yield session


def _load(db: Session) -> tuple[LoadedProblem, date]:
    today = datetime.now(ZAGREB).date()
    day = today + timedelta(days=1)
    return load_problem(db, day, MockRoutingClient(), PARAMS), day


def test_day_selection_candidates_and_eligibility(db: Session) -> None:
    loaded, day = _load(db)
    problem = loaded.problem
    assert problem.requests
    day_slot_ids = {s.id for s in problem.slots}
    own_car_ids = set(db.scalars(select(Patient.id).where(Patient.own_car.is_(True))))
    assert own_car_ids

    in_problem = {r.id for r in problem.requests}
    for r in problem.requests:
        assert r.patient_id not in own_car_ids
        assert r.candidate_slot_ids
        assert set(r.candidate_slot_ids) <= day_slot_ids
        # Rule 7: a sanitetski vehicle only for entitled patients.
        sanitetski = {
            v.id for v in problem.vehicles if v.provider_type == VehicleProviderType.SANITETSKI
        }
        if r.transport_entitlement != TransportEntitlement.SANITETSKI:
            assert not (r.allowed_vehicle_ids & sanitetski)
    assert not (in_problem & {u.request_id for u in loaded.unserved})
    n = len(problem.durations_min)
    assert all(len(row) == n for row in problem.durations_min)
    assert len(loaded.locations) == n


def test_no_candidates_and_missing_location_are_unserved(db: Session) -> None:
    loaded, _ = _load(db)
    victim, *others = loaded.problem.requests
    no_slots = others[0]
    db.execute(
        update(VisitRequest)
        .where(VisitRequest.id == no_slots.id)
        .values(earliest_date=datetime.now(ZAGREB).date())
    )
    request = db.get(VisitRequest, no_slots.id)
    assert request is not None
    request.candidate_slots = []
    patient = db.get(Patient, victim.patient_id)
    assert patient is not None
    patient.location = None
    db.commit()

    again, _ = _load(db)
    reasons = {u.request_id: u.reason for u in again.unserved}
    assert reasons[no_slots.id] == UnservedReason.NO_SLOT_IN_WINDOW
    assert reasons[victim.id] == UnservedReason.LOCATION_MISSING
    assert {r.id for r in again.problem.requests}.isdisjoint(reasons)


def test_locked_and_confirmed_assignments_become_pins(db: Session) -> None:
    loaded, day = _load(db)
    problem = loaded.problem
    locked, confirmed, proposed = problem.requests[:3]
    vehicle = problem.vehicles[0]

    def add(req_id: int, status: AssignmentStatus, is_locked: bool) -> None:
        slot_id = next(r for r in problem.requests if r.id == req_id).candidate_slot_ids[0]
        db.add(
            Assignment(
                request_id=req_id,
                slot_id=slot_id,
                vehicle_id=vehicle.id,
                pickup_time=datetime.combine(day, datetime.min.time(), tzinfo=ZAGREB).replace(
                    hour=7, minute=30
                ),
                status=status.value,
                is_locked=is_locked,
            )
        )

    add(locked.id, AssignmentStatus.PROPOSED, True)
    add(confirmed.id, AssignmentStatus.CONFIRMED, False)
    add(proposed.id, AssignmentStatus.PROPOSED, False)
    db.commit()

    again, _ = _load(db)
    by_id = {r.id: r for r in again.problem.requests}
    locked_pin, confirmed_pin = by_id[locked.id].pin, by_id[confirmed.id].pin
    assert locked_pin is not None
    assert locked_pin.pickup_min is None
    assert confirmed_pin is not None
    assert confirmed_pin.pickup_min == 7 * 60 + 30
    assert confirmed_pin.vehicle_id == vehicle.id
    # Unpinned proposals are ignored (replaced later by persistence).
    assert by_id[proposed.id].pin is None
