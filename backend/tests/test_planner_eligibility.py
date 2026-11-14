from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.config import Settings
from app.models import MobilityClass as M
from app.models import TransportEntitlement as E
from app.models import VehicleProviderType as P
from app.planner.eligibility import allowed_vehicles, needs_sanitetski_order
from app.planner.problem import PlannerParams, PVehicle, from_minutes, to_minutes


def veh(id_, ptype, seats=4, wc=0, st=0):
    return PVehicle(id_, ptype, seats, wc, st, 360, 960, 0)


FLEET = [
    veh(1, P.SANITETSKI, seats=2, wc=1, st=1),
    veh(2, P.RED_CROSS, seats=4, wc=1),
    veh(3, P.TAXI, seats=3),
    veh(4, P.PATIENT_DRIVER, seats=3),
]


def allowed(mobility=M.WALKS, ent=E.NONE, level="low", companion=False, fleet=FLEET):
    return allowed_vehicles(
        mobility_class=mobility,
        transport_entitlement=ent,
        support_level=level,
        companion=companion,
        vehicles=fleet,
    )


def test_wheelchair_without_entitlement_never_sanitetski():
    assert allowed(M.WHEELCHAIR, E.NONE) == {2}
    assert allowed(M.WHEELCHAIR, E.TRAVEL_ORDER) == {2}
    assert needs_sanitetski_order(M.WHEELCHAIR, E.NONE)
    assert not needs_sanitetski_order(M.WHEELCHAIR, E.SANITETSKI)
    assert not needs_sanitetski_order(M.WALKS, E.NONE)


def test_immobile_without_entitlement_and_only_sanitetski_is_empty():
    assert allowed(M.STRETCHER, E.NONE) == frozenset()
    assert allowed(M.WHEELCHAIR, E.NONE, fleet=FLEET[:1]) == frozenset()


def test_mobile_without_entitlement_never_sanitetski_even_if_only_vehicle():
    assert allowed(M.WALKS, E.NONE, fleet=FLEET[:1]) == frozenset()
    assert allowed(M.CANE, E.TRAVEL_ORDER) == {2, 3}


def test_entitled_gets_only_sanitetski():
    assert allowed(M.WHEELCHAIR, E.SANITETSKI) == {1}
    assert allowed(M.STRETCHER, E.SANITETSKI) == {1}
    assert allowed(M.WALKS, E.SANITETSKI) == {1}


def test_companion_needs_free_seat():
    fleet = [veh(1, P.TAXI, seats=0, wc=1), veh(2, P.RED_CROSS, seats=1, wc=1)]
    assert allowed(M.WHEELCHAIR, companion=False, fleet=fleet) == {1, 2}
    assert allowed(M.WHEELCHAIR, companion=True, fleet=fleet) == {2}


def test_high_support_never_patient_driver_and_not_emptied_by_it():
    fleet = [veh(1, P.PATIENT_DRIVER), veh(2, P.VOLUNTEER)]
    assert allowed(level="high", fleet=fleet) == {2}
    assert allowed(level="low", fleet=fleet) == {2}
    assert allowed(level="high", fleet=fleet[:1]) == frozenset()


def test_minutes_round_trip_in_zagreb():
    day = date(2026, 11, 14)
    dt = from_minutes(day, 8 * 60 + 30)
    assert dt == datetime(2026, 11, 14, 8, 30, tzinfo=ZoneInfo("Europe/Zagreb"))
    assert to_minutes(day, dt) == 510
    utc = dt.astimezone(ZoneInfo("UTC"))
    assert to_minutes(day, utc) == 510


def test_params_from_settings_defaults():
    p = PlannerParams.from_settings()
    assert p.time_limit_s >= 1
    s = Settings()
    assert p.max_ride_extra_min == s.planner_max_ride_extra_min
