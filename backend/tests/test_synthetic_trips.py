from __future__ import annotations

import statistics
from datetime import date
from pathlib import Path

import pytest

from app.codebooks import get_visit_duration
from app.config import get_settings
from app.models import Department, MobilityClass, TripLog, VisitType
from app.schemas import TripLogRead
from app.synthetic_trips import (
    SYNTHETIC_TRIPS_PATH,
    SyntheticTripParamsError,
    generate_synthetic_trip_logs,
    load_synthetic_trip_params,
)


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
        # Asymmetric tolerance (-20% / +25%): log-normal samples are right-skewed.
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


def test_only_external_departments_use_external_band() -> None:
    rows = generate_synthetic_trip_logs(count=3000, seed=42, end_date=date(2026, 11, 14))
    drive = load_synthetic_trip_params().drive
    max_regional = max(b.max for b in drive.distance_bands_km.values())

    oncology = [r for r in rows if r.department == Department.ONCOLOGY.value]
    others = [r for r in rows if r.department != Department.ONCOLOGY.value]
    assert oncology and others
    assert all(r.distance_km is not None for r in rows)
    assert all(
        drive.external_band_km.min <= (r.distance_km or 0.0) <= drive.external_band_km.max
        for r in oncology
    )
    assert all((r.distance_km or 0.0) <= max_regional for r in others)
    assert all(not r.elevator for r in rows if r.floor == 0)


def test_timestamps_are_aware_utc() -> None:
    rows = generate_synthetic_trip_logs(count=200, seed=1, end_date=date(2026, 11, 14))
    for r in rows:
        assert r.actual_arrival_at_door is not None
        assert r.actual_arrival_at_door.utcoffset() is not None
        assert r.actual_arrival_at_door.utcoffset().total_seconds() == 0  # type: ignore[union-attr]


def test_invalid_params_yaml_raises_domain_error(tmp_path: Path) -> None:
    target = tmp_path / SYNTHETIC_TRIPS_PATH
    target.parent.mkdir(parents=True)
    source = (get_settings().data_dir / SYNTHETIC_TRIPS_PATH).read_text(encoding="utf-8")
    target.write_text(
        source.replace("mean_speed_kmh: 55.0", "mean_speed_kmh: -1"), encoding="utf-8"
    )
    with pytest.raises(SyntheticTripParamsError):
        generate_synthetic_trip_logs(count=1, data_dir=tmp_path)
