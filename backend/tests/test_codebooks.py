from __future__ import annotations

from pathlib import Path

import pytest

from app.codebooks import (
    CODEBOOKS_RELATIVE_PATH,
    CodebookError,
    get_boarding_time_min,
    get_codebooks,
    get_mobility_class_info,
    get_urgency_info,
    get_urgency_max_shift_days,
    get_visit_duration,
    load_codebooks_from_path,
    time_of_day_for_hour,
)
from app.config import get_settings
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
    assert get_boarding_time_min("cane") == 5
    assert get_boarding_time_min("wheelchair") == 10
    assert get_boarding_time_min("stretcher") == 15
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


def test_visit_durations_exact_only() -> None:
    dialysis = get_visit_duration("dialysis", "dialysis_session")
    assert (dialysis.median_min, dialysis.p90_min) == (240, 270)

    cardio_fu = get_visit_duration(Department.CARDIOLOGY, VisitType.FOLLOW_UP)
    assert (cardio_fu.median_min, cardio_fu.p90_min) == (30, 50)

    # Radiology lists only procedure_test: no borrowing, no constant default.
    with pytest.raises(CodebookError):
        get_visit_duration("radiology", "follow_up")


def test_unknown_keys_raise() -> None:
    for call in (
        lambda: get_visit_duration("nonexistent", "first_visit"),
        lambda: get_visit_duration("cardiology", "nonexistent"),
        lambda: get_urgency_info("nonexistent"),
        lambda: get_mobility_class_info("nonexistent"),
        lambda: get_boarding_time_min("nonexistent"),
    ):
        with pytest.raises(CodebookError):
            call()


def test_missing_yaml_raises(tmp_path: Path) -> None:
    with pytest.raises(CodebookError):
        load_codebooks_from_path(tmp_path / "nope.yaml")


def test_data_dir_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / CODEBOOKS_RELATIVE_PATH
    target.parent.mkdir(parents=True)
    text = (get_settings().data_dir / CODEBOOKS_RELATIVE_PATH).read_text(encoding="utf-8")
    target.write_text(text.replace("Interna medicina", "Testna interna"), encoding="utf-8")

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        cb = load_codebooks_from_path()
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
    assert next(d.label for d in cb.departments if d.key == Department.INTERNAL_MEDICINE) == (
        "Testna interna"
    )

    # Empty DATA_DIR: explicit error, no fallback data.
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "empty"))
    get_settings.cache_clear()
    try:
        with pytest.raises(CodebookError):
            load_codebooks_from_path()
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_enums_match_yaml_keys() -> None:
    cb = get_codebooks()
    assert {m.key for m in cb.mobility_classes} == set(MobilityClass)
    assert {d.key for d in cb.departments} == set(Department)
    assert {v.key for v in cb.visit_types} == set(VisitType)
    assert {u.key for u in cb.urgency_classes} == set(UrgencyClass)
    assert set(cb.boarding_time_min) == set(MobilityClass)


def test_codebooks_endpoint_from_yaml() -> None:
    res = read_codebooks()
    assert len(res.visit_durations) == 22


def test_times_of_day_load_from_yaml() -> None:
    entries = get_codebooks().times_of_day
    assert [(e.key, e.label, e.before_hour) for e in entries] == [
        ("morning", "Prijepodne", 12),
        ("afternoon", "Poslijepodne", 24),
    ]
    assert time_of_day_for_hour(0) == "morning"
    assert time_of_day_for_hour(11) == "morning"
    assert time_of_day_for_hour(12) == "afternoon"
    assert time_of_day_for_hour(23) == "afternoon"
    assert {e.key: e.label for e in read_codebooks().times_of_day} == {
        "morning": "Prijepodne",
        "afternoon": "Poslijepodne",
    }


_TIMES_OF_DAY_BLOCK = (
    "times_of_day:\n"
    "  - key: morning\n    label: Prijepodne\n    before_hour: 12\n"
    "  - key: afternoon\n    label: Poslijepodne\n    before_hour: 24\n"
)


@pytest.mark.parametrize(
    "replacement",
    [
        # duplicate key
        _TIMES_OF_DAY_BLOCK.replace("key: afternoon", "key: morning"),
        # not strictly increasing
        _TIMES_OF_DAY_BLOCK.replace("before_hour: 24", "before_hour: 12"),
        # last entry does not end at 24
        _TIMES_OF_DAY_BLOCK.replace("before_hour: 24", "before_hour: 18"),
        # empty
        "times_of_day: []\n",
    ],
)
def test_invalid_times_of_day_raise(tmp_path: Path, replacement: str) -> None:
    text = (get_settings().data_dir / CODEBOOKS_RELATIVE_PATH).read_text(encoding="utf-8")
    assert _TIMES_OF_DAY_BLOCK in text
    path = tmp_path / "broken.yaml"
    path.write_text(text.replace(_TIMES_OF_DAY_BLOCK, replacement), encoding="utf-8")
    with pytest.raises(CodebookError):
        load_codebooks_from_path(path)


def test_broken_codebooks_fail_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    from app.main import StartupCheckError, app, lifespan

    def broken() -> None:
        raise CodebookError("broken")

    monkeypatch.setattr("app.main.get_codebooks", broken)

    async def run() -> None:
        async with lifespan(app):
            pass

    with pytest.raises(StartupCheckError, match="Codebooks are invalid"):
        asyncio.run(run())
