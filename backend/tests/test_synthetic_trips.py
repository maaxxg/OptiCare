from __future__ import annotations

import statistics
from datetime import date

from app.codebooks import get_visit_duration
from app.models import Department, MobilityClass, TripLog, VisitType
from app.schemas import TripLogRead
from app.synthetic_trips import generate_synthetic_trip_logs


def _boarding_minutes(row: TripLog) -> float:
    assert row.actual_arrival_at_door is not None
    assert row.actual_departure_from_door is not None
    return (row.actual_departure_from_door - row.actual_arrival_at_door).total_seconds() / 60.0


def _visit_minutes(row: TripLog) -> float:
    assert row.actual_check_in_at_facility is not None
    assert row.actual_check_out_from_facility is not None
    delta = row.actual_check_out_from_facility - row.actual_check_in_at_facility
    return delta.total_seconds() / 60.0


def test_default_generates_three_thousand_valid_rows() -> None:
    rows = generate_synthetic_trip_logs(end_date=date(2026, 11, 14))
    assert len(rows) == 3000

    for idx, row in enumerate(rows[:50], start=1):
        row.id = idx
        validated = TripLogRead.model_validate(row)
        assert validated.recorded_by == "synthetic"

    for row in rows:
        assert row.actual_arrival_at_door is not None
        assert row.actual_departure_from_door is not None
        assert row.actual_check_in_at_facility is not None
        assert row.actual_check_out_from_facility is not None
        assert row.actual_dropoff_at_home is not None
        assert (
            row.actual_arrival_at_door
            < row.actual_departure_from_door
            < row.actual_check_in_at_facility
            < row.actual_check_out_from_facility
            < row.actual_dropoff_at_home
        )


def test_visit_duration_distributions_match_codebooks() -> None:
    rows = generate_synthetic_trip_logs(count=3000, seed=42, end_date=date(2026, 11, 14))

    pairs_to_check = [
        (Department.DIALYSIS.value, VisitType.DIALYSIS_SESSION.value),
        (Department.INTERNAL_MEDICINE.value, VisitType.FOLLOW_UP.value),
        (Department.CARDIOLOGY.value, VisitType.FOLLOW_UP.value),
        (Department.RADIOLOGY.value, VisitType.PROCEDURE_TEST.value),
    ]
    for dept, vtype in pairs_to_check:
        durations = [
            _visit_minutes(r) for r in rows if r.department == dept and r.visit_type == vtype
        ]
        assert len(durations) >= 50
        expected_median = get_visit_duration(dept, vtype).median_min
        empirical_median = statistics.median(durations)
        # Allow +/- 20% tolerance (including the small age >= 75 multiplier)
        assert expected_median * 0.80 <= empirical_median <= expected_median * 1.25


def test_boarding_time_increases_with_mobility_and_stairs() -> None:
    rows = generate_synthetic_trip_logs(count=3000, seed=42, end_date=date(2026, 11, 14))

    ground_medians = {
        mob.value: statistics.median(
            [_boarding_minutes(r) for r in rows if r.mobility_class == mob.value and r.floor == 0]
        )
        for mob in MobilityClass
    }
    assert (
        ground_medians["walks"]
        < ground_medians["cane"]
        < ground_medians["wheelchair"]
        < ground_medians["stretcher"]
    )

    # Upper floors without elevator must take longer than ground floor for wheelchair/stretcher
    for mob_key in (MobilityClass.WHEELCHAIR.value, MobilityClass.STRETCHER.value):
        stairs_times = [
            _boarding_minutes(r)
            for r in rows
            if r.mobility_class == mob_key and (r.floor or 0) >= 2 and not r.elevator
        ]
        assert stairs_times
        assert statistics.median(stairs_times) > ground_medians[mob_key] + 3.0
