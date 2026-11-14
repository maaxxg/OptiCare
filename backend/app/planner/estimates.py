"""The single seam through which the planner gets visit duration and boarding time.

Calls the Predictor registry (`visit_duration`, `service_time`) with the YAML codebook as the
rule fallback (rule 12), so switching a slot to a trained model requires no planner changes.
A missing codebook entry raises `CodebookError` (via `PredictorInputError`); nothing is guessed.
"""

from app.models import Department, MobilityClass, VisitType
from app.plan_schemas import Estimate, EstimateSource
from app.predictors import get_predictor


def visit_duration(department: Department | str, visit_type: VisitType | str) -> Estimate:
    """Visit duration at p90 (used for the return window)."""
    dept = department.value if isinstance(department, Department) else str(department)
    vtype = visit_type.value if isinstance(visit_type, VisitType) else str(visit_type)
    predictor = get_predictor("visit_duration")
    pred = predictor.predict({"department": dept, "visit_type": vtype})
    minutes = round(pred.high if pred.high is not None else pred.value)
    return Estimate(
        minutes=minutes,
        source=EstimateSource(pred.source),
        version=predictor.version,
    )


def boarding_minutes(mobility_class: MobilityClass | str) -> int:
    mob = mobility_class.value if isinstance(mobility_class, MobilityClass) else str(mobility_class)
    pred = get_predictor("service_time").predict({"mobility_class": mob})
    return round(pred.value)
