"""Bodovanje potrebe za podrškom (E3-T1; sadržaj YAML-a je E13-T3, KAN-89).

Učitava faktore i razine iz ``data/domain/scoring_factors.yaml``, izračunava
težinski zbroj za danog pacijenta i vraća ukupni bod, doprinos svakog faktora
i razinu usluge.

PRAVILO (CLAUDE.md, pravilo 1): bodovi i razine SAMO DODAJU pomoć. Nijedan
faktor, prag ni razina ne smije ukloniti, odbiti ni deprioritizirati pacijenta.
"""

from __future__ import annotations

import logging
import math
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml
from pydantic import BaseModel, Field, ValidationError, model_validator

from app.config import get_settings
from app.models import MobilityClass, PhoneType

SCORING_RELATIVE_PATH = Path("domain") / "scoring_factors.yaml"

logger = logging.getLogger(__name__)

ZAGREB = ZoneInfo("Europe/Zagreb")

KNOWN_FACTOR_KEYS = frozenset(
    {
        "mobility_class",
        "distance_to_destination",
        "age",
        "lives_alone",
        "missed_visits_last_year",
        "phone_type",
        "companion_available",
    }
)
_MAPPING_ENUMS: dict[str, set[str]] = {
    "mobility_class": {m.value for m in MobilityClass},
    "phone_type": {p.value for p in PhoneType},
}
_BOOLEAN_FACTORS = frozenset({"lives_alone", "companion_available"})
_BAND_FACTORS = frozenset({"age", "distance_to_destination", "missed_visits_last_year"})


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

    @model_validator(mode="after")
    def _check_single_kind(self) -> FactorConfig:
        is_boolean = self.if_true is not None or self.if_false is not None
        kinds = [self.bands is not None, self.mapping is not None, is_boolean]
        if sum(kinds) != 1:
            raise ValueError(
                f"factor '{self.key}' must define exactly one of bands, mapping, "
                "or if_true/if_false"
            )
        if self.bands is not None:
            self._check_bands(self.bands)
        elif self.mapping is not None:
            if not self.mapping:
                raise ValueError(f"factor '{self.key}': mapping is empty")
            if any(not 0.0 <= v <= 1.0 for v in self.mapping.values()):
                raise ValueError(f"factor '{self.key}': mapping values must be in [0, 1]")
        else:
            if self.if_true is None or self.if_false is None:
                raise ValueError(f"factor '{self.key}': both if_true and if_false are required")
            if not (0.0 <= self.if_true <= 1.0 and 0.0 <= self.if_false <= 1.0):
                raise ValueError(f"factor '{self.key}': if_true/if_false must be in [0, 1]")
        return self

    def _check_bands(self, bands: list[BandEntry]) -> None:
        if not bands:
            raise ValueError(f"factor '{self.key}': bands are empty")
        if bands[-1].max is not None:
            raise ValueError(f"factor '{self.key}': last band must have max null")
        maxes = [b.max for b in bands[:-1]]
        previous: float | None = None
        for m in maxes:
            if m is None or (previous is not None and m <= previous):
                raise ValueError(
                    f"factor '{self.key}': band max values must be numbers, strictly increasing"
                )
            previous = m


class LevelConfig(BaseModel):
    key: str
    label: str
    min_score: float
    max_score: float
    adds_help: list[str] = Field(default_factory=list)


class ScoringConfig(BaseModel):
    factors: list[FactorConfig]
    levels: list[LevelConfig]

    @model_validator(mode="after")
    def _check_config(self) -> ScoringConfig:
        self._check_factors()
        self._check_levels()
        return self

    def _check_factors(self) -> None:
        if not self.factors:
            raise ValueError("factors are empty")
        keys = [f.key for f in self.factors]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate factor keys")
        unknown = set(keys) - KNOWN_FACTOR_KEYS
        if unknown:
            raise ValueError(f"unknown factor keys: {sorted(unknown)}")
        total = sum(f.weight for f in self.factors)
        if not math.isclose(total, 1.0, abs_tol=1e-6):
            raise ValueError(f"factor weights must sum to 1.0, got {total}")
        for f in self.factors:
            expected = _MAPPING_ENUMS.get(f.key)
            if expected is not None and (f.mapping is None or set(f.mapping) != expected):
                raise ValueError(
                    f"factor '{f.key}': mapping keys must be exactly {sorted(expected)}"
                )
            if f.key in _BOOLEAN_FACTORS and (f.if_true is None or f.if_false is None):
                raise ValueError(f"factor '{f.key}' must be a boolean factor")
            if f.key in _BAND_FACTORS and f.bands is None:
                raise ValueError(f"factor '{f.key}' must be a band factor")

    def _check_levels(self) -> None:
        if not self.levels:
            raise ValueError("levels are empty")
        keys = [lv.key for lv in self.levels]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate level keys")
        for lv in self.levels:
            if lv.min_score >= lv.max_score:
                raise ValueError(f"level '{lv.key}': min_score must be below max_score")
        if self.levels[0].min_score != 0.0:
            raise ValueError("first level must start at min_score 0.0")
        for prev, nxt in zip(self.levels, self.levels[1:], strict=False):
            if nxt.min_score != prev.max_score:
                raise ValueError(f"levels '{prev.key}' and '{nxt.key}' are not contiguous")
        if self.levels[-1].max_score <= 1.0:
            raise ValueError("last level max_score must be above 1.0 to cover a score of 1.0")


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
    missing: bool = Field(
        default=False,
        description="Ulaz nedostaje ili je nevaljan; raw_value i weighted_value su tada 0",
    )


class ScoringResult(BaseModel):
    """Ukupni rezultat bodovanja za jednog pacijenta."""

    patient_id: int
    total_score: float = Field(
        ..., ge=0.0, le=1.0, description="Zbroj weighted_value poznatih faktora"
    )
    total_score_upper: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "total_score + najveći mogući doprinos faktora koji nedostaju; "
            "razina se bira prema ovoj vrijednosti"
        ),
    )
    missing_factors: list[str] = Field(
        default_factory=list,
        description="Ključevi faktora čiji ulaz nedostaje (redom iz konfiguracije)",
    )
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
    # Zadnji pojas je otvoren (max: null), što validacija konfiguracije jamči.
    return bands[-1].value


def _resolve_factor(factor: FactorConfig, raw_input: Any) -> float | None:
    """Vrati sirovu vrijednost faktora (0–1) ili None ako ulaz nedostaje/nije valjan.

    Nedostajući ulaz se nikad ne pogađa; pozivatelj ga označava kao ``missing``.
    """
    if raw_input is None:
        return None

    # Logički faktor: samo pravi bool, bez istinitosti ("false" nije bool)
    if factor.if_true is not None and factor.if_false is not None:
        if not isinstance(raw_input, bool):
            return None
        return factor.if_true if raw_input else factor.if_false

    # Diskretna tablica (mapping)
    if factor.mapping is not None:
        if not isinstance(raw_input, str):
            return None
        return factor.mapping.get(raw_input.lower())

    # Numerički pojasevi
    if factor.bands is not None:
        if isinstance(raw_input, bool) or not isinstance(raw_input, int | float):
            return None
        if not math.isfinite(raw_input) or raw_input < 0:
            return None
        return _resolve_bands(factor.bands, float(raw_input))

    return None


def _max_raw_value(factor: FactorConfig) -> float:
    """Najveća moguća sirova vrijednost faktora."""
    if factor.bands is not None:
        return max(b.value for b in factor.bands)
    if factor.mapping is not None:
        return max(factor.mapping.values())
    assert factor.if_true is not None and factor.if_false is not None
    return max(factor.if_true, factor.if_false)


def _determine_level(config: ScoringConfig, score: float) -> LevelConfig:
    """Vrati razinu usluge za dani ukupni bod."""
    for level in config.levels:
        if level.min_score <= score < level.max_score:
            return level
    raise ScoringConfigError(f"No scoring level covers score {score}")


def _patient_age(birth_year: int | None, reference_date: date | None = None) -> int | None:
    """Vrati dob pacijenta, ili None ako birth_year nedostaje ili je u budućnosti.

    Pohranjena je samo godina rođenja pa je dob = referentna godina − godina
    rođenja, tj. dob koju pacijent navršava u tekućoj kalendarskoj godini. To
    može biti do godinu dana više od točne dobi, pa se greška uvijek javlja u
    smjeru veće pomoći (pravilo 1). Zadani referentni datum je današnji datum
    u vremenskoj zoni Europe/Zagreb.
    """
    if birth_year is None or isinstance(birth_year, bool):
        return None
    ref = reference_date or datetime.now(ZAGREB).date()
    age = ref.year - birth_year
    return age if age >= 0 else None


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
    boduje.  Ulaz koji nedostaje (npr. ``distance_km``, ``birth_year``) ne
    pogađa se: faktor je označen ``missing`` i doprinosi 0 u ``total_score``,
    a razina se bira prema ``total_score_upper`` (poznati bodovi plus najveći
    mogući doprinos faktora koji nedostaju), pa nedostajući podatak nikad ne
    snižava razinu pomoći.
    """
    cfg = config or get_scoring_config()
    ref = reference_date or datetime.now(ZAGREB).date()
    age = _patient_age(birth_year, ref)

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

    assert set(inputs) == KNOWN_FACTOR_KEYS
    contributions: list[FactorContribution] = []
    missing_factors: list[str] = []
    total = 0.0
    upper_extra = 0.0

    for factor in cfg.factors:
        raw_input = inputs.get(factor.key)
        resolved = _resolve_factor(factor, raw_input)
        is_missing = resolved is None
        raw_value = 0.0 if resolved is None else resolved
        weighted = round(factor.weight * raw_value, 6)
        total += weighted
        if is_missing:
            missing_factors.append(factor.key)
            upper_extra += factor.weight * _max_raw_value(factor)
        contributions.append(
            FactorContribution(
                key=factor.key,
                label=factor.label,
                weight=factor.weight,
                raw_value=raw_value,
                weighted_value=weighted,
                rationale=factor.rationale,
                input_value=None if is_missing else raw_input,
                missing=is_missing,
            )
        )

    # Težine se validiraju na zbroj 1; min() štiti samo od float šuma.
    total = round(min(total, 1.0), 4)
    upper = round(min(total + upper_extra, 1.0), 4)
    level = _determine_level(cfg, upper)

    return ScoringResult(
        patient_id=patient_id,
        total_score=total,
        total_score_upper=upper,
        missing_factors=missing_factors,
        level_key=level.key,
        level_label=level.label,
        adds_help=level.adds_help,
        factors=contributions,
    )
