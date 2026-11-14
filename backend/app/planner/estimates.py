"""The single seam through which the planner gets visit duration and boarding time.

Today the body is the rule (YAML codebooks). When E4-T1/T2 land, these functions call the
Predictor registry (`visit_duration`, `service_time`) with the codebook as the rule fallback
(rule 12), and the planner does not change. A missing codebook entry raises `CodebookError`;
nothing is guessed.
"""

from app.codebooks import get_boarding_time_min, get_visit_duration
from app.models import Department, MobilityClass, VisitType
from app.plan_schemas import Estimate, EstimateSource


def visit_duration(department: Department | str, visit_type: VisitType | str) -> Estimate:
    """Visit duration at p90 (used for the return window)."""
    entry = get_visit_duration(department, visit_type)
    return Estimate(minutes=entry.p90_min, source=EstimateSource.RULES, version="codebook")


def boarding_minutes(mobility_class: MobilityClass | str) -> int:
    return get_boarding_time_min(mobility_class)
