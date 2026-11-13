from __future__ import annotations

from pathlib import Path

from app.codebooks import (
    get_boarding_time_min,
    get_codebooks,
    get_mobility_class_info,
    get_urgency_info,
    get_urgency_max_shift_days,
    get_visit_duration,
    load_codebooks_from_path,
)
from app.main import read_codebooks
from app.models import Department, MobilityClass, UrgencyClass, VisitType


def test_mobility_classes_and_boarding_times() -> None:
    cb = get_codebooks()
    keys = [m.key for m in cb.mobility_classes]
    assert keys == [
        MobilityClass.WALKS,
        MobilityClass.CANE,
        MobilityClass.WHEELCHAIR,
        MobilityClass.STRETCHER,
    ]
    assert get_boarding_time_min("walks") == 3
    assert get_boarding_time_min("štap") == 5
    assert get_boarding_time_min("kolica") == 10
    assert get_boarding_time_min("nosila") == 15
    assert get_mobility_class_info("cane").label == "Štap"


def test_departments_and_visit_types() -> None:
    cb = get_codebooks()
    dept_keys = {d.key for d in cb.departments}
    assert dept_keys == set(Department)

    vtype_keys = {v.key for v in cb.visit_types}
    assert vtype_keys == set(VisitType)


def test_urgency_classes_and_deadlines() -> None:
    assert get_urgency_max_shift_days(UrgencyClass.FIXED) == 0
    assert get_urgency_max_shift_days(UrgencyClass.WITHIN_FEW_DAYS) == 3
    assert get_urgency_max_shift_days(UrgencyClass.WITHIN_WEEK) == 7
    assert get_urgency_max_shift_days(UrgencyClass.WITHIN_MONTH) == 30

    fixed_info = get_urgency_info("fixed")
    month_info = get_urgency_info("within_month")
    assert fixed_info.unserved_penalty_rank > month_info.unserved_penalty_rank


def test_visit_durations_and_fallback() -> None:
    dialysis = get_visit_duration("dialysis", "dialysis_session")
    assert dialysis.median_min == 240
    assert dialysis.p90_min == 270

    cardio_fu = get_visit_duration(Department.CARDIOLOGY, VisitType.FOLLOW_UP)
    assert cardio_fu.median_min == 30
    assert cardio_fu.p90_min == 50

    # Radiology only lists procedure_test in YAML; fallback for follow_up should still return 40/75
    rad_fallback = get_visit_duration("radiology", "follow_up")
    assert rad_fallback.median_min == 40
    assert rad_fallback.p90_min == 75


def test_fallback_when_yaml_missing_and_endpoint() -> None:
    cb_fallback = load_codebooks_from_path(Path("/nonexistent/urgency_and_durations.yaml"))
    assert len(cb_fallback.departments) == 8
    assert len(cb_fallback.mobility_classes) == 4

    endpoint_res = read_codebooks()
    assert len(endpoint_res.visit_durations) == 20
