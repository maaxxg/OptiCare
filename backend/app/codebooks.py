from __future__ import annotations

import logging
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError

from app.config import get_settings
from app.models import Department, MobilityClass, UrgencyClass, VisitType

CODEBOOKS_RELATIVE_PATH = Path("domain") / "urgency_and_durations.yaml"

logger = logging.getLogger(__name__)


class CodebookError(Exception):
    """Codebook file is unusable, or a looked-up key is not in it."""


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
    path = yaml_path if yaml_path is not None else get_settings().data_dir / CODEBOOKS_RELATIVE_PATH
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        logger.error("Codebooks YAML cannot be read: %s (check DATA_DIR)", path)
        raise CodebookError(f"Cannot read codebooks YAML at {path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise CodebookError(f"Codebooks YAML at {path} must be a mapping")
    try:
        return Codebooks.model_validate(loaded)
    except ValidationError as exc:
        raise CodebookError(f"Invalid codebooks YAML at {path}: {exc}") from exc


@lru_cache
def get_codebooks() -> Codebooks:
    return load_codebooks_from_path()


def _coerce[E: StrEnum](enum_cls: type[E], value: str) -> E:
    try:
        return enum_cls(value)
    except ValueError as exc:
        raise CodebookError(f"Unknown {enum_cls.__name__}: {value!r}") from exc


def get_mobility_class_info(mobility: MobilityClass | str) -> MobilityClassEntry:
    key = _coerce(MobilityClass, mobility)
    for item in get_codebooks().mobility_classes:
        if item.key == key:
            return item
    raise CodebookError(f"Mobility class not in codebooks: {mobility!r}")


def get_boarding_time_min(mobility: MobilityClass | str) -> int:
    key = _coerce(MobilityClass, mobility)
    boarding = get_codebooks().boarding_time_min
    if key not in boarding:
        raise CodebookError(f"Boarding time not in codebooks: {mobility!r}")
    return boarding[key]


def get_urgency_info(urgency: UrgencyClass | str) -> UrgencyClassEntry:
    key = _coerce(UrgencyClass, urgency)
    for item in get_codebooks().urgency_classes:
        if item.key == key:
            return item
    raise CodebookError(f"Urgency class not in codebooks: {urgency!r}")


def get_urgency_max_shift_days(urgency: UrgencyClass | str) -> int:
    return get_urgency_info(urgency).max_shift_days


def get_visit_duration(
    department: Department | str, visit_type: VisitType | str
) -> VisitDurationEntry:
    dept = _coerce(Department, department)
    vtype = _coerce(VisitType, visit_type)
    for entry in get_codebooks().visit_durations:
        if entry.department == dept and entry.visit_type == vtype:
            return entry
    raise CodebookError(f"No visit duration for {dept.value}/{vtype.value} in codebooks")
