"""`GET /plan?date=`: the day's plan for the dispatch dashboard (E9).

Returns the fixed mock from `plan_mock.py` until the planner (E5-T6) is wired in.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query

from app.plan_mock import build_mock_plan
from app.plan_schemas import PlanResponse

ZAGREB = ZoneInfo("Europe/Zagreb")

router = APIRouter(tags=["plan"])


@router.get("/plan", response_model=PlanResponse)
def get_plan(
    plan_date: Annotated[date | None, Query(alias="date", description="Default: tomorrow")] = None,
) -> PlanResponse:
    day = plan_date or (datetime.now(ZAGREB).date() + timedelta(days=1))
    return build_mock_plan(day)
