"""Bodovanje potrebe za podrškom (E13-T3, KAN-89).

Učitava faktore i razine iz ``data/domain/scoring_factors.yaml``, izračunava
težinski zbroj za danog pacijenta i vraća ukupni bod, doprinos svakog faktora
i razinu usluge.

PRAVILO (CLAUDE.md, pravilo 1): bodovi i razine SAMO DODAJU pomoć. Nijedan
faktor, prag ni razina ne smije ukloniti, odbiti ni deprioritizirati pacijenta.
"""

from __future__ import annotations

import logging
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError

from app.config import get_settings

SCORING_RELATIVE_PATH = Path("domain") / "scoring_factors.yaml"

logger = logging.getLogger(__name__)


class ScoringConfigError(Exception):
    """Konfiguracijska datoteka s faktorima ne može se pročitati ili je nevaljana."""


# ---------------------------------------------------------------------------
# Pydantic modeli za konfiguraciju (scoring_factors.yaml)
# ---------------------------------------------------------------------------


class BandEntry(BaseModel):
    max: float | None = None
    value: float = Field(..., ge=0.0, le=1.0)


class FactorConfig(BaseModel):
    key: str
    label: str
    weight: float = Field(..., ge=0.0, le=1.0)
    rationale: str = ""
    # Numerički pojasevi
    bands: list[BandEntry] | None = None
    unit: str | None = None
    # Diskretne vrijednosti (pokretljivost, vrsta telefona)
    mapping: dict[str, float] | None = None
    # Logički faktor
    if_true: float | None = None
    if_false: float | None = None


class LevelConfig(BaseModel):
    key: str
    label: str
    min_score: float
    max_score: float
    adds_help: list[str] = Field(default_factory=list)


class ScoringConfig(BaseModel):
    factors: list[FactorConfig]
    levels: list[LevelConfig]


# ---------------------------------------------------------------------------
# Učitavanje konfiguracije
# ---------------------------------------------------------------------------


def load_scoring_config(yaml_path: Path | None = None) -> ScoringConfig:
    path = yaml_path or (get_settings().data_dir / SCORING_RELATIVE_PATH)
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        logger.error("Scoring YAML ne može se pročitati: %s", path)
        raise ScoringConfigError(f"Cannot read scoring YAML at {path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ScoringConfigError(f"Scoring YAML at {path} must be a mapping")
    try:
        return ScoringConfig.model_validate(loaded)
    except ValidationError as exc:
        raise ScoringConfigError(f"Invalid scoring YAML at {path}: {exc}") from exc


@lru_cache
def get_scoring_config() -> ScoringConfig:
    return load_scoring_config()


# ---------------------------------------------------------------------------
# Rezultat bodovanja
# ---------------------------------------------------------------------------


class FactorContribution(BaseModel):
    """Doprinos jednog faktora ukupnom bodu."""

    key: str
    label: str
    weight: float
    raw_value: float = Field(..., description="Sirova vrijednost faktora (0–1)")
    weighted_value: float = Field(..., description="weight × raw_value")
    rationale: str = ""
    input_value: Any = Field(
        default=None,
        description="Ulazna vrijednost iz podataka pacijenta (za transparentnost)",
    )


class ScoringResult(BaseModel):
    """Ukupni rezultat bodovanja za jednog pacijenta."""

    patient_id: int
    total_score: float = Field(..., ge=0.0, le=1.0, description="Zbroj svih weighted_value")
    level_key: str
    level_label: str
    adds_help: list[str] = Field(default_factory=list)
    factors: list[FactorContribution]


# ---------------------------------------------------------------------------
# Logika izračuna
# ---------------------------------------------------------------------------


def _resolve_bands(bands: list[BandEntry], value: float) -> float:
    """Vrati vrijednost iz pojasa za danu numeričku veličinu."""
    for band in bands:
        if band.max is not None and value < band.max:
            return band.value
    # Ako smo prošli sve pojaseve (last band.max je None ili value >= svi max),
    # vrati zadnji pojas.
    return bands[-1].value


def _resolve_factor(factor: FactorConfig, raw_input: Any) -> float:
    """Vrati sirovu vrijednost faktora (0–1) za danu ulaznu vrijednost."""
    if raw_input is None:
        return 0.0

    # Logički faktor
    if factor.if_true is not None and factor.if_false is not None:
        return factor.if_true if raw_input else factor.if_false

    # Diskretna tablica (mapping)
    if factor.mapping is not None:
        str_val = str(raw_input).lower()
        return factor.mapping.get(str_val, 0.0)

    # Numerički pojasevi
    if factor.bands is not None:
        try:
            numeric = float(raw_input)
        except (TypeError, ValueError):
            return 0.0
        return _resolve_bands(factor.bands, numeric)

    return 0.0


def _determine_level(config: ScoringConfig, score: float) -> LevelConfig:
    """Vrati razinu usluge za dani ukupni bod."""
    for level in config.levels:
        if level.min_score <= score < level.max_score:
            return level
    # Fallback: zadnja razina ako nema podudaranja (ne bi se smjelo desiti)
    return config.levels[-1]


def _patient_age(birth_year: int | None, reference_date: date | None = None) -> int | None:
    """Vrati dob pacijenta u cijelim godinama, ili None ako birth_year nedostaje."""
    if birth_year is None:
        return None
    ref = reference_date or date.today()
    return ref.year - birth_year


def compute_score(
    *,
    patient_id: int,
    mobility_class: str,
    distance_km: float | None,
    birth_year: int | None,
    lives_alone: bool,
    missed_visits_last_year: int,
    phone_type: str,
    companion_available: bool,
    config: ScoringConfig | None = None,
    reference_date: date | None = None,
) -> ScoringResult:
    """Izračunaj bodove potrebne za podršku za jednog pacijenta.

    Parametri odgovaraju stupcima u tablici ``patients`` i zahtjevu koji se
    boduje.  ``distance_km`` dolazi iz adaptera za rute; ako nedostaje, faktor
    udaljenosti doprinosi 0.
    """
    cfg = config or get_scoring_config()
    age = _patient_age(birth_year, reference_date)

    # Mapiranje ključeva faktora → ulaznih vrijednosti pacijenta
    inputs: dict[str, Any] = {
        "mobility_class": mobility_class,
        "distance_to_destination": distance_km,
        "age": age,
        "lives_alone": lives_alone,
        "missed_visits_last_year": missed_visits_last_year,
        "phone_type": phone_type,
        "companion_available": companion_available,
    }

    contributions: list[FactorContribution] = []
    total = 0.0

    for factor in cfg.factors:
        raw_input = inputs.get(factor.key)
        raw_value = _resolve_factor(factor, raw_input)
        weighted = round(factor.weight * raw_value, 6)
        total += weighted
        contributions.append(
            FactorContribution(
                key=factor.key,
                label=factor.label,
                weight=factor.weight,
                raw_value=raw_value,
                weighted_value=weighted,
                rationale=factor.rationale,
                input_value=raw_input,
            )
        )

    total = round(min(total, 1.0), 4)
    level = _determine_level(cfg, total)

    return ScoringResult(
        patient_id=patient_id,
        total_score=total,
        level_key=level.key,
        level_label=level.label,
        adds_help=level.adds_help,
        factors=contributions,
    )
