from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from app.models import Department, MobilityClass, UrgencyClass, VisitType

# Repo root when running locally: backend/app/codebooks.py -> parents[2]
_DEFAULT_YAML_CANDIDATES = (
    Path(__file__).resolve().parents[2] / "data" / "domain" / "urgency_and_durations.yaml",
    Path("/data/domain/urgency_and_durations.yaml"),
)

_FALLBACK_CODEBOOKS_DATA: dict[str, Any] = {
    "mobility_classes": [
        {"key": "walks", "label": "Hoda", "boarding_time_min": 3},
        {"key": "cane", "label": "Štap", "boarding_time_min": 5},
        {"key": "wheelchair", "label": "Kolica", "boarding_time_min": 10},
        {"key": "stretcher", "label": "Nosila", "boarding_time_min": 15},
    ],
    "departments": [
        {"key": "internal_medicine", "label": "Interna medicina"},
        {"key": "cardiology", "label": "Kardiologija"},
        {"key": "ophthalmology", "label": "Oftalmologija"},
        {"key": "orthopaedics", "label": "Ortopedija"},
        {"key": "neurology", "label": "Neurologija"},
        {"key": "radiology", "label": "Radiologija"},
        {"key": "oncology", "label": "Onkologija"},
        {"key": "dialysis", "label": "Dijaliza"},
    ],
    "visit_types": [
        {"key": "first_visit", "label": "Prvi pregled"},
        {"key": "follow_up", "label": "Kontrolni pregled"},
        {"key": "procedure_test", "label": "Zahvat ili pretraga"},
        {"key": "dialysis_session", "label": "Dijaliza (seansa)"},
    ],
    "urgency_classes": [
        {
            "key": "fixed",
            "label": "Ne smije se pomaknuti",
            "max_shift_days": 0,
            "unserved_penalty_rank": 4,
        },
        {
            "key": "within_few_days",
            "label": "U roku od nekoliko dana",
            "max_shift_days": 3,
            "unserved_penalty_rank": 3,
        },
        {
            "key": "within_week",
            "label": "U roku od tjedan dana",
            "max_shift_days": 7,
            "unserved_penalty_rank": 2,
        },
        {
            "key": "within_month",
            "label": "U roku od mjesec dana",
            "max_shift_days": 30,
            "unserved_penalty_rank": 1,
        },
    ],
    "visit_durations": [
        {
            "department": "internal_medicine",
            "visit_type": "first_visit",
            "median_min": 45,
            "p90_min": 75,
        },
        {
            "department": "internal_medicine",
            "visit_type": "follow_up",
            "median_min": 25,
            "p90_min": 45,
        },
        {
            "department": "internal_medicine",
            "visit_type": "procedure_test",
            "median_min": 60,
            "p90_min": 100,
        },
        {"department": "cardiology", "visit_type": "first_visit", "median_min": 50, "p90_min": 80},
        {"department": "cardiology", "visit_type": "follow_up", "median_min": 30, "p90_min": 50},
        {
            "department": "cardiology",
            "visit_type": "procedure_test",
            "median_min": 70,
            "p90_min": 120,
        },
        {
            "department": "ophthalmology",
            "visit_type": "first_visit",
            "median_min": 45,
            "p90_min": 80,
        },
        {"department": "ophthalmology", "visit_type": "follow_up", "median_min": 25, "p90_min": 45},
        {
            "department": "ophthalmology",
            "visit_type": "procedure_test",
            "median_min": 60,
            "p90_min": 100,
        },
        {
            "department": "orthopaedics",
            "visit_type": "first_visit",
            "median_min": 40,
            "p90_min": 70,
        },
        {"department": "orthopaedics", "visit_type": "follow_up", "median_min": 25, "p90_min": 45},
        {
            "department": "orthopaedics",
            "visit_type": "procedure_test",
            "median_min": 75,
            "p90_min": 120,
        },
        {"department": "neurology", "visit_type": "first_visit", "median_min": 50, "p90_min": 85},
        {"department": "neurology", "visit_type": "follow_up", "median_min": 30, "p90_min": 50},
        {
            "department": "neurology",
            "visit_type": "procedure_test",
            "median_min": 70,
            "p90_min": 120,
        },
        {
            "department": "radiology",
            "visit_type": "procedure_test",
            "median_min": 40,
            "p90_min": 75,
        },
        {"department": "oncology", "visit_type": "first_visit", "median_min": 60, "p90_min": 100},
        {"department": "oncology", "visit_type": "follow_up", "median_min": 40, "p90_min": 70},
        {
            "department": "oncology",
            "visit_type": "procedure_test",
            "median_min": 120,
            "p90_min": 200,
        },
        {
            "department": "dialysis",
            "visit_type": "dialysis_session",
            "median_min": 240,
            "p90_min": 270,
        },
    ],
    "boarding_time_min": {
        "walks": 3,
        "cane": 5,
        "wheelchair": 10,
        "stretcher": 15,
    },
}


class MobilityClassEntry(BaseModel):
    key: MobilityClass
    label: str
    boarding_time_min: int = Field(..., ge=1)


class DepartmentEntry(BaseModel):
    key: Department
    label: str


class VisitTypeEntry(BaseModel):
    key: VisitType
    label: str


class UrgencyClassEntry(BaseModel):
    key: UrgencyClass
    label: str
    max_shift_days: int = Field(..., ge=0)
    unserved_penalty_rank: int = Field(..., ge=1)


class VisitDurationEntry(BaseModel):
    department: Department
    visit_type: VisitType
    median_min: int = Field(..., ge=1)
    p90_min: int = Field(..., ge=1)


class Codebooks(BaseModel):
    mobility_classes: list[MobilityClassEntry]
    departments: list[DepartmentEntry]
    visit_types: list[VisitTypeEntry]
    urgency_classes: list[UrgencyClassEntry]
    visit_durations: list[VisitDurationEntry]
    boarding_time_min: dict[MobilityClass, int]


def load_codebooks_from_path(yaml_path: Path | None = None) -> Codebooks:
    raw: dict[str, Any] | None = None
    candidates = (yaml_path,) if yaml_path is not None else _DEFAULT_YAML_CANDIDATES
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            loaded = yaml.safe_load(candidate.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                raw = loaded
                break

    if raw is None:
        raw = dict(_FALLBACK_CODEBOOKS_DATA)
    else:
        raw = dict(raw)
        if "mobility_classes" not in raw:
            boarding = raw.get("boarding_time_min", _FALLBACK_CODEBOOKS_DATA["boarding_time_min"])
            raw["mobility_classes"] = [
                {"key": "walks", "label": "Hoda", "boarding_time_min": boarding.get("walks", 3)},
                {"key": "cane", "label": "Štap", "boarding_time_min": boarding.get("cane", 5)},
                {
                    "key": "wheelchair",
                    "label": "Kolica",
                    "boarding_time_min": boarding.get("wheelchair", 10),
                },
                {
                    "key": "stretcher",
                    "label": "Nosila",
                    "boarding_time_min": boarding.get("stretcher", 15),
                },
            ]

    return Codebooks.model_validate(raw)


@lru_cache
def get_codebooks() -> Codebooks:
    return load_codebooks_from_path()


def get_mobility_class_info(mobility: MobilityClass | str) -> MobilityClassEntry:
    mob_enum = MobilityClass(mobility)
    for item in get_codebooks().mobility_classes:
        if item.key == mob_enum:
            return item
    raise KeyError(f"Unknown mobility class: {mobility!r}")


def get_boarding_time_min(mobility: MobilityClass | str) -> int:
    mob_enum = MobilityClass(mobility)
    cb = get_codebooks()
    if mob_enum in cb.boarding_time_min:
        return cb.boarding_time_min[mob_enum]
    return get_mobility_class_info(mob_enum).boarding_time_min


def get_urgency_info(urgency: UrgencyClass | str) -> UrgencyClassEntry:
    urg_enum = UrgencyClass(urgency)
    for item in get_codebooks().urgency_classes:
        if item.key == urg_enum:
            return item
    raise KeyError(f"Unknown urgency class: {urgency!r}")


def get_urgency_max_shift_days(urgency: UrgencyClass | str) -> int:
    return get_urgency_info(urgency).max_shift_days


def get_visit_duration(
    department: Department | str, visit_type: VisitType | str
) -> VisitDurationEntry:
    dept_enum = Department(department)
    vtype_enum = VisitType(visit_type)
    cb = get_codebooks()

    for entry in cb.visit_durations:
        if entry.department == dept_enum and entry.visit_type == vtype_enum:
            return entry

    # Fallback to first matching department entry if an unusual visit_type is requested
    for entry in cb.visit_durations:
        if entry.department == dept_enum:
            return VisitDurationEntry(
                department=dept_enum,
                visit_type=vtype_enum,
                median_min=entry.median_min,
                p90_min=entry.p90_min,
            )

    return VisitDurationEntry(
        department=dept_enum,
        visit_type=vtype_enum,
        median_min=45,
        p90_min=75,
    )
