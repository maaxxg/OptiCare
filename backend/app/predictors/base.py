"""Sučelje prediktora i izlazni model prema ARHITEKTURA §7 (E4-T1, KAN-28)."""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from app.adapters.types import AdapterError
from app.codebooks import CodebookError

PredictionSource = Literal["rules", "model"]


class PredictorError(Exception):
    """Bazna greška sloja prediktora."""


class PredictorConfigError(PredictorError):
    """Konfiguracijska datoteka prediktora je neispravna ili sadrži nepoznato mjesto/pravilo."""


class PredictorNotConfiguredError(PredictorError):
    """Mjesto postoji u registru, ali još nema aktivnu implementaciju (npr. demand do E4-T7)."""


class PredictorInputError(PredictorError, CodebookError, ValueError):
    """Ulazna značajka nedostaje ili nije valjana prema šifrarniku."""


class MissingFeatureError(PredictorInputError, KeyError):
    """Nedostaje obvezna ulazna značajka za izračun predikcije."""


class PredictorExecutionError(PredictorError, AdapterError):
    """Izračun predikcije nije uspio zbog greške vanjskog adaptera (npr. rute)."""


class Prediction(BaseModel):
    """Rezultat predikcije prema ARHITEKTURA §7."""

    value: float
    low: float | None = None
    high: float | None = None
    explanation: dict[str, float] = Field(default_factory=dict)
    source: PredictionSource


@runtime_checkable
class Predictor(Protocol):
    """Zajedničko sučelje za pravila i istrenirane ML modele (ARHITEKTURA §7)."""

    name: str
    version: str

    def predict(self, features: dict[str, Any]) -> Prediction: ...
