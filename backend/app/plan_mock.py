"""Fixed example plan for `GET /plan` until the planner (E5) exists.

Lets the dashboard (E9) be built against the real contract (`plan_schemas.py`).
Names, places and vehicles follow the synthetic seed (`seed.py`, patient_profiles.yaml);
ids follow seed insertion order but are not guaranteed to match a seeded database.
"""

from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from app.models import (
    AssignmentStatus,
    Department,
    MobilityClass,
    TransportEntitlement,
    UrgencyClass,
    VehicleProviderType,
    VisitType,
)
from app.plan_schemas import (
    Estimate,
    EstimateSource,
    OutboundLeg,
    PlanAssignment,
    PlanFacility,
    PlanMetrics,
    PlanPatient,
    PlanResponse,
    PlanSlot,
    PlanSource,
    PlanVehicle,
    ReturnLeg,
    RouteStop,
    StopKind,
    UnservedReason,
    UnservedRequest,
)
from app.schemas import GeoPoint

ZAGREB = ZoneInfo("Europe/Zagreb")

OB_GOSPIC = GeoPoint(lat=44.5435, lon=15.36214)
GOSPIC = GeoPoint(lat=44.5464, lon=15.37542)
OTOCAC = GeoPoint(lat=44.8688, lon=15.23587)
SENJ = GeoPoint(lat=44.99015, lon=14.90212)
PERUSIC = GeoPoint(lat=44.65002, lon=15.38326)
DONJI_KOSINJ = GeoPoint(lat=44.75986, lon=15.24962)
UDBINA = GeoPoint(lat=44.53175, lon=15.76652)

FACILITY_ID = 1


def build_mock_plan(plan_date: date, now: datetime | None = None) -> PlanResponse:
    def at(hh: int, mm: int) -> datetime:
        return datetime.combine(plan_date, time(hh, mm), tzinfo=ZAGREB)

    ivan = PlanPatient(
        id=2,
        first_name="Ivan",
        last_name="Kovačević",
        phone="+385 00 000 0002",
        settlement="Otočac",
        municipality="Otočac",
        location=OTOCAC,
        mobility_class=MobilityClass.WHEELCHAIR,
        transport_entitlement=TransportEntitlement.SANITETSKI,
        support_level="high",
    )
    ana = PlanPatient(
        id=3,
        first_name="Ana",
        last_name="Babić",
        phone="+385 00 000 0003",
        settlement="Senj",
        municipality="Senj",
        location=SENJ,
        mobility_class=MobilityClass.STRETCHER,
        transport_entitlement=TransportEntitlement.SANITETSKI,
        support_level="high",
    )
    stjepan = PlanPatient(
        id=5,
        first_name="Stjepan",
        last_name="Perković",
        phone="+385 00 000 0005",
        settlement="Perušić",
        municipality="Perušić",
        location=PERUSIC,
        mobility_class=MobilityClass.WALKS,
        transport_entitlement=TransportEntitlement.NONE,
        support_level="low",
    )
    katica = PlanPatient(
        id=6,
        first_name="Katica",
        last_name="Starčević",
        phone="+385 00 000 0006",
        settlement="Donji Kosinj",
        municipality="Perušić",
        location=DONJI_KOSINJ,
        mobility_class=MobilityClass.WALKS,
        transport_entitlement=TransportEntitlement.NONE,
        support_level="medium",
    )
    marija = PlanPatient(
        id=1,
        first_name="Marija",
        last_name="Marijević",
        phone="+385 00 000 0001",
        settlement="Udbina",
        municipality="Udbina",
        location=UDBINA,
        mobility_class=MobilityClass.CANE,
        transport_entitlement=TransportEntitlement.NONE,
        support_level="medium",
    )
    nikola = PlanPatient(
        id=10,
        first_name="Nikola",
        last_name="Vukelić",
        phone="+385 00 000 0010",
        settlement="Novalja",
        municipality="Novalja",
        location=None,
        mobility_class=MobilityClass.CANE,
        transport_entitlement=TransportEntitlement.NONE,
        support_level="medium",
    )

    sanitet, red_cross = 3, 7
    assignments = [
        PlanAssignment(
            id=1,
            request_id=2,
            status=AssignmentStatus.CONFIRMED,
            is_locked=False,
            patient=ivan,
            slot=PlanSlot(
                id=6,
                facility_id=FACILITY_ID,
                department=Department.CARDIOLOGY,
                start_time=at(9, 30),
                end_time=at(10, 0),
            ),
            visit_type=VisitType.FOLLOW_UP,
            urgency_class=UrgencyClass.WITHIN_WEEK,
            outbound=OutboundLeg(
                vehicle_id=sanitet, pickup_time=at(8, 30), facility_arrival_time=at(9, 20)
            ),
            return_leg=ReturnLeg(
                vehicle_id=sanitet, pickup_time=at(11, 15), home_dropoff_time=at(12, 15)
            ),
            visit_duration=Estimate(minutes=30, source=EstimateSource.RULES),
        ),
        PlanAssignment(
            id=2,
            request_id=3,
            status=AssignmentStatus.PROPOSED,
            is_locked=False,
            patient=ana,
            slot=PlanSlot(
                id=2,
                facility_id=FACILITY_ID,
                department=Department.INTERNAL_MEDICINE,
                start_time=at(10, 0),
                end_time=at(10, 45),
            ),
            visit_type=VisitType.FIRST_VISIT,
            urgency_class=UrgencyClass.WITHIN_FEW_DAYS,
            outbound=OutboundLeg(
                vehicle_id=sanitet, pickup_time=at(7, 30), facility_arrival_time=at(9, 25)
            ),
            return_leg=ReturnLeg(
                vehicle_id=sanitet, pickup_time=at(11, 20), home_dropoff_time=at(13, 10)
            ),
            visit_duration=Estimate(
                minutes=55, source=EstimateSource.MODEL, version="visit_duration-0.1"
            ),
        ),
        PlanAssignment(
            id=3,
            request_id=6,
            status=AssignmentStatus.MODIFIED,
            is_locked=True,
            patient=katica,
            slot=PlanSlot(
                id=10,
                facility_id=FACILITY_ID,
                department=Department.OPHTHALMOLOGY,
                start_time=at(9, 30),
                end_time=at(10, 0),
            ),
            visit_type=VisitType.FOLLOW_UP,
            urgency_class=UrgencyClass.WITHIN_MONTH,
            outbound=OutboundLeg(
                vehicle_id=red_cross, pickup_time=at(8, 5), facility_arrival_time=at(8, 55)
            ),
            return_leg=ReturnLeg(
                vehicle_id=red_cross, pickup_time=at(11, 30), home_dropoff_time=at(12, 30)
            ),
            visit_duration=Estimate(minutes=30, source=EstimateSource.RULES),
        ),
        PlanAssignment(
            id=4,
            request_id=5,
            status=AssignmentStatus.PROPOSED,
            is_locked=False,
            patient=stjepan,
            slot=PlanSlot(
                id=14,
                facility_id=FACILITY_ID,
                department=Department.ORTHOPAEDICS,
                start_time=at(10, 30),
                end_time=at(11, 0),
            ),
            visit_type=VisitType.FOLLOW_UP,
            urgency_class=UrgencyClass.WITHIN_MONTH,
            outbound=OutboundLeg(
                vehicle_id=red_cross, pickup_time=at(8, 30), facility_arrival_time=at(8, 58)
            ),
            return_leg=ReturnLeg(
                vehicle_id=red_cross, pickup_time=at(11, 35), home_dropoff_time=at(12, 0)
            ),
            visit_duration=Estimate(minutes=30, source=EstimateSource.RULES),
        ),
    ]

    def stop(
        seq: int,
        kind: StopKind,
        loc: GeoPoint,
        label: str,
        arrive: datetime,
        depart: datetime,
        assignment_id: int | None = None,
    ) -> RouteStop:
        at_facility = kind in (StopKind.DROPOFF_FACILITY, StopKind.PICKUP_FACILITY)
        return RouteStop(
            seq=seq,
            kind=kind,
            assignment_id=assignment_id,
            facility_id=FACILITY_ID if at_facility else None,
            location=loc,
            label=label,
            arrival_time=arrive,
            departure_time=depart,
        )

    ob = "Opća bolnica Gospić"
    vehicles = [
        PlanVehicle(
            id=sanitet,
            key="sanitet_otocac_1",
            name="Sanitet Otočac 1",
            provider_type=VehicleProviderType.SANITETSKI,
            seats=3,
            wheelchair_spots=1,
            stretcher_spots=1,
            shift_start=time(6, 30),
            shift_end=time(16, 30),
            base_settlement="Otočac",
            base_location=OTOCAC,
            driver_name="Goran Barković",
            driver_phone="+385 00 100 0003",
            stops=[
                stop(0, StopKind.DEPOT_START, OTOCAC, "Otočac", at(6, 45), at(6, 45)),
                stop(1, StopKind.PICKUP_HOME, SENJ, "Senj", at(7, 30), at(7, 45), 2),
                stop(2, StopKind.PICKUP_HOME, OTOCAC, "Otočac", at(8, 30), at(8, 40), 1),
                stop(3, StopKind.DROPOFF_FACILITY, OB_GOSPIC, ob, at(9, 20), at(9, 25), 1),
                stop(4, StopKind.DROPOFF_FACILITY, OB_GOSPIC, ob, at(9, 25), at(9, 35), 2),
                stop(5, StopKind.PICKUP_FACILITY, OB_GOSPIC, ob, at(11, 15), at(11, 20), 1),
                stop(6, StopKind.PICKUP_FACILITY, OB_GOSPIC, ob, at(11, 20), at(11, 30), 2),
                stop(7, StopKind.DROPOFF_HOME, OTOCAC, "Otočac", at(12, 15), at(12, 25), 1),
                stop(8, StopKind.DROPOFF_HOME, SENJ, "Senj", at(13, 10), at(13, 25), 2),
                stop(9, StopKind.DEPOT_END, OTOCAC, "Otočac", at(14, 10), at(14, 10)),
            ],
            total_km=236.0,
            total_minutes=445,
        ),
        PlanVehicle(
            id=red_cross,
            key="crveni_kriz_gospic_1",
            name="Crveni križ Gospić, kombi",
            provider_type=VehicleProviderType.RED_CROSS,
            seats=5,
            wheelchair_spots=1,
            stretcher_spots=0,
            shift_start=time(7, 0),
            shift_end=time(15, 30),
            base_settlement="Gospić",
            base_location=GOSPIC,
            driver_name="Tomislav Starčević",
            driver_phone="+385 00 100 0007",
            stops=[
                stop(0, StopKind.DEPOT_START, GOSPIC, "Gospić", at(7, 20), at(7, 20)),
                stop(1, StopKind.PICKUP_HOME, DONJI_KOSINJ, "Donji Kosinj", at(8, 5), at(8, 10), 3),
                stop(2, StopKind.PICKUP_HOME, PERUSIC, "Perušić", at(8, 30), at(8, 35), 4),
                stop(3, StopKind.DROPOFF_FACILITY, OB_GOSPIC, ob, at(8, 55), at(8, 58), 3),
                stop(4, StopKind.DROPOFF_FACILITY, OB_GOSPIC, ob, at(8, 58), at(9, 0), 4),
                stop(5, StopKind.PICKUP_FACILITY, OB_GOSPIC, ob, at(11, 30), at(11, 33), 3),
                stop(6, StopKind.PICKUP_FACILITY, OB_GOSPIC, ob, at(11, 35), at(11, 38), 4),
                stop(7, StopKind.DROPOFF_HOME, PERUSIC, "Perušić", at(12, 0), at(12, 5), 4),
                stop(
                    8,
                    StopKind.DROPOFF_HOME,
                    DONJI_KOSINJ,
                    "Donji Kosinj",
                    at(12, 30),
                    at(12, 35),
                    3,
                ),
                stop(9, StopKind.DEPOT_END, GOSPIC, "Gospić", at(13, 20), at(13, 20)),
            ],
            total_km=148.5,
            total_minutes=360,
        ),
    ]

    unserved = [
        UnservedRequest(
            request_id=1,
            patient=marija,
            facility_id=FACILITY_ID,
            department=Department.NEUROLOGY,
            visit_type=VisitType.FIRST_VISIT,
            urgency_class=UrgencyClass.WITHIN_WEEK,
            earliest_date=plan_date,
            latest_date=plan_date,
            reason=UnservedReason.NO_VEHICLE_CAPACITY,
            reason_text="Nijedno vozilo u smjeni nema slobodno mjesto za taj dan.",
        ),
        UnservedRequest(
            request_id=10,
            patient=nikola,
            facility_id=FACILITY_ID,
            department=Department.CARDIOLOGY,
            visit_type=VisitType.FOLLOW_UP,
            urgency_class=UrgencyClass.WITHIN_MONTH,
            earliest_date=plan_date,
            latest_date=plan_date,
            reason=UnservedReason.LOCATION_MISSING,
            reason_text=(
                "Adresa pacijenta nije potvrđena na karti. "
                "Potvrdite lokaciju i ponovno pokrenite planiranje."
            ),
        ),
    ]

    return PlanResponse(
        date=plan_date,
        source=PlanSource.MOCK,
        generated_at=now or datetime.now(ZAGREB),
        facilities=[
            PlanFacility(
                id=FACILITY_ID,
                key="ob_gospic",
                name=ob,
                address="Kaniška ulica 111, 53000 Gospić",
                location=OB_GOSPIC,
            )
        ],
        vehicles=vehicles,
        assignments=assignments,
        unserved=unserved,
        metrics=PlanMetrics(
            served=len(assignments),
            unserved=len(unserved),
            vehicles_used=len(vehicles),
            planned_trips=len(vehicles),
            baseline_trips=len(assignments),
            total_km=384.5,
            baseline_km=612.0,
        ),
    )
