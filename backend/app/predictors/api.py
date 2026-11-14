"""FastAPI krajnje točke za prediktore: `POST /predict/{slot}` i `GET /models` (E4-T1)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException, status

from app.predictors.base import (
    Prediction,
    PredictorExecutionError,
    PredictorInputError,
    PredictorNotConfiguredError,
)
from app.predictors.registry import (
    KNOWN_SLOTS,
    ModelSlotStatus,
    get_predictor_registry,
)

router = APIRouter(tags=["predictors"])


@router.get("/models", response_model=list[ModelSlotStatus])
def list_models_endpoint() -> list[ModelSlotStatus]:
    """Aktivna implementacija, verzija i izvor po mjestu prediktora."""
    return get_predictor_registry().list_models()


@router.post("/predict/{slot}", response_model=Prediction)
def predict_slot_endpoint(
    slot: str,
    features: Annotated[dict[str, Any], Body(...)],
) -> Prediction:
    """Izračunaj predikciju registriranog prediktora za traženo mjesto."""
    if slot not in KNOWN_SLOTS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nepoznato mjesto prediktora: '{slot}'.",
        )

    registry = get_predictor_registry()
    try:
        predictor = registry.get_predictor(slot)
    except PredictorNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prediktor za mjesto '{slot}' još nije postavljen.",
        ) from exc

    try:
        return predictor.predict(features)
    except PredictorInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except PredictorExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
