"""Registar prediktora s povratkom na zadano pravilo (E4-T1, KAN-28)."""

from __future__ import annotations

import logging
import math
import pickle
import re
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from app.config import REPO_ROOT, get_settings
from app.predictors.base import (
    Prediction,
    PredictionSource,
    Predictor,
    PredictorConfigError,
    PredictorNotConfiguredError,
)
from app.predictors.rules import (
    ServiceTimeRule,
    SupportNeedRule,
    TravelTimeRule,
    VisitDurationRule,
)

logger = logging.getLogger(__name__)

PREDICTORS_RELATIVE_PATH = Path("domain") / "predictors.yaml"

KNOWN_SLOTS: tuple[str, ...] = (
    "visit_duration",
    "service_time",
    "support_need",
    "travel_time",
    "demand",
)

UNSET_TOKENS = frozenset({"", "unset", "none", "null", "nije postavljeno"})

DEFAULT_RULE_FACTORIES: dict[str, Callable[[], Predictor]] = {
    "visit_duration": VisitDurationRule,
    "service_time": ServiceTimeRule,
    "support_need": SupportNeedRule,
    "travel_time": TravelTimeRule,
}

_VERSION_FROM_PATH_RE = re.compile(r"-([0-9]+(?:\.[0-9]+)*)\.[a-zA-Z0-9]+$")


class SlotRange(BaseModel):
    """Dopušteni raspon vrijednosti predikcije za jedno mjesto."""

    model_config = ConfigDict(extra="forbid")

    min: float
    max: float
    unit: str = ""

    @model_validator(mode="after")
    def _check_bounds(self) -> SlotRange:
        if (
            isinstance(self.min, bool)
            or isinstance(self.max, bool)
            or not (math.isfinite(self.min) and math.isfinite(self.max))
        ):
            raise ValueError("granice raspona min i max moraju biti konačni brojevi")
        if self.min >= self.max:
            raise ValueError(f"min ({self.min}) mora biti strogo manji od max ({self.max})")
        return self


class PredictorsConfig(BaseModel):
    """Konfiguracija registra prediktora iz `data/domain/predictors.yaml`."""

    model_config = ConfigDict(extra="forbid")

    slots: dict[str, str | None]
    ranges: dict[str, SlotRange]

    @model_validator(mode="after")
    def _validate_slots_and_ranges(self) -> PredictorsConfig:
        known = set(KNOWN_SLOTS)

        unknown_slots = set(self.slots) - known
        if unknown_slots:
            raise ValueError(f"nepoznata mjesta u 'slots': {sorted(unknown_slots)}")

        missing_slots = known - set(self.slots)
        if missing_slots:
            raise ValueError(f"nedostaju mjesta u 'slots': {sorted(missing_slots)}")

        unknown_ranges = set(self.ranges) - known
        if unknown_ranges:
            raise ValueError(f"nepoznata mjesta u 'ranges': {sorted(unknown_ranges)}")

        missing_ranges = known - set(self.ranges)
        if missing_ranges:
            raise ValueError(f"nedostaju mjesta u 'ranges': {sorted(missing_ranges)}")

        for slot, raw_spec in self.slots.items():
            spec = (raw_spec or "").strip()
            if spec.lower() in UNSET_TOKENS:
                if slot in DEFAULT_RULE_FACTORIES:
                    raise ValueError(f"mjesto '{slot}' mora imati postavljeno pravilo ili model")
                continue

            if spec == "rules":
                if slot not in DEFAULT_RULE_FACTORIES:
                    raise ValueError(
                        f"nepostojeće pravilo za mjesto '{slot}': pravilo još nije implementirano"
                    )
                continue

            if spec.startswith("model:"):
                model_path = spec.removeprefix("model:").strip()
                if not model_path:
                    raise ValueError(f"mjesto '{slot}' ima praznu putanju modela u '{spec}'")
                if slot not in DEFAULT_RULE_FACTORIES:
                    raise ValueError(
                        f"mjesto '{slot}' nema rezervno pravilo pa ne može koristiti model"
                    )
                continue

            raise ValueError(
                f"nepostojeće pravilo ili nepoznata implementacija za mjesto '{slot}': {spec!r}"
            )

        return self


class ModelSlotStatus(BaseModel):
    """Stanje pojedinog mjesta u registru za `GET /models`."""

    slot: str
    implementation: str
    version: str | None = None
    source: PredictionSource | None = None
    fallback_active: bool = False


def _infer_version_from_path(path_str: str) -> str:
    match = _VERSION_FROM_PATH_RE.search(path_str)
    return match.group(1) if match else "unknown"


def _resolve_model_path(raw_path: str, base_dir: Path | None = None) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    search_roots: list[Path] = []
    if base_dir is not None:
        search_roots.append(base_dir)
    search_roots.extend([get_settings().data_dir, REPO_ROOT / "ml", REPO_ROOT])
    for root in search_roots:
        resolved = root / candidate
        if resolved.exists():
            return resolved
    return (base_dir or REPO_ROOT) / candidate


def _load_model_from_disk(path: Path) -> Predictor:
    try:
        import joblib  # type: ignore[import-not-found]

        loaded = joblib.load(path)
    except ImportError:
        loaded = pickle.loads(path.read_bytes())

    if not hasattr(loaded, "predict") or not callable(loaded.predict):
        raise TypeError(f"učitani objekt iz {path.name} nema metodu predict()")
    return loaded  # type: ignore[no-any-return]


def _is_valid_number(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, int | float)
        and math.isfinite(float(value))
    )


class FallbackPredictor:
    """Omotač oko prediktora koji pri svakoj grešci ili izlazu izvan raspona zove pravilo.

    Nikad ne zapisuje ulazne značajke (`features`) u log jer mogu sadržavati osobne podatke.
    """

    def __init__(
        self,
        *,
        slot: str,
        rule: Predictor,
        slot_range: SlotRange,
        configured_spec: str = "rules",
        model: Predictor | None = None,
        load_error: str | None = None,
        configured_version: str | None = None,
    ) -> None:
        self.slot = slot
        self._rule = rule
        self.slot_range = slot_range
        self.configured_spec = configured_spec
        self._model = model
        self._load_error = load_error
        self._configured_version = configured_version or (
            getattr(model, "version", None) if model is not None else rule.version
        )
        self.fallback_active: bool = load_error is not None

    @property
    def name(self) -> str:
        if self._model is not None and not self.fallback_active:
            return str(getattr(self._model, "name", self.configured_spec))
        return self._rule.name

    @property
    def version(self) -> str:
        if self._model is not None and not self.fallback_active:
            return str(getattr(self._model, "version", self._configured_version))
        return self._rule.version

    @property
    def source(self) -> PredictionSource:
        if self._model is not None and not self.fallback_active:
            return "model"
        return "rules"

    def _warn_fallback(self, reason: str, version: str) -> None:
        self.fallback_active = True
        logger.disabled = False
        # Pravilo 12: bilježi (slot, razlog, verzija); nikad ne zapisuje ulazne značajke.
        logger.warning(
            "Povratak prediktora na pravilo: slot=%s razlog=%s verzija=%s",
            self.slot,
            reason,
            version,
        )

    def _validate_prediction_bounds(self, pred: Prediction) -> str | None:
        if not _is_valid_number(pred.value):
            return "nan_or_infinite_value"
        val = float(pred.value)
        if val < self.slot_range.min or val > self.slot_range.max:
            return f"value_out_of_range[{self.slot_range.min},{self.slot_range.max}]"

        if pred.low is not None:
            if not _is_valid_number(pred.low):
                return "nan_or_infinite_low"
            low_val = float(pred.low)
            if low_val < self.slot_range.min or low_val > val:
                return "low_out_of_range"

        if pred.high is not None:
            if not _is_valid_number(pred.high):
                return "nan_or_infinite_high"
            high_val = float(pred.high)
            if high_val < val or high_val > self.slot_range.max:
                return f"high_out_of_range[{self.slot_range.min},{self.slot_range.max}]"

        return None

    def predict(self, features: dict[str, Any]) -> Prediction:
        if self.configured_spec == "rules":
            return self._rule.predict(features)

        if self._model is None:
            self._warn_fallback(
                self._load_error or "model_not_loaded",
                str(self._configured_version),
            )
            return self._rule.predict(features)

        model_version = str(getattr(self._model, "version", self._configured_version))
        try:
            pred = self._model.predict(features)
        except Exception as exc:
            self._warn_fallback(f"model_exception:{type(exc).__name__}", model_version)
            return self._rule.predict(features)

        if not isinstance(pred, Prediction):
            try:
                pred = Prediction.model_validate(pred)
            except ValidationError:
                self._warn_fallback("invalid_prediction_schema", model_version)
                return self._rule.predict(features)

        bound_error = self._validate_prediction_bounds(pred)
        if bound_error is not None:
            self._warn_fallback(bound_error, model_version)
            return self._rule.predict(features)

        if pred.source != "model":
            pred = pred.model_copy(update={"source": "model"})
        return pred


def load_predictors_config(yaml_path: Path | None = None) -> PredictorsConfig:
    """Učitaj i validiraj `predictors.yaml`. Baca `PredictorConfigError` ako je neispravan."""
    path = (
        yaml_path if yaml_path is not None else get_settings().data_dir / PREDICTORS_RELATIVE_PATH
    )
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        logger.error("Predictors YAML ne može se pročitati: %s", path)
        raise PredictorConfigError(f"Cannot read predictors YAML at {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise PredictorConfigError(f"Predictors YAML at {path} must be a mapping")

    try:
        return PredictorsConfig.model_validate(raw)
    except ValidationError as exc:
        raise PredictorConfigError(f"Invalid predictors YAML at {path}: {exc}") from exc


class PredictorRegistry:
    """Registar aktivnih prediktora po mjestu (`visit_duration`, `service_time`, ...)."""

    def __init__(
        self,
        config: PredictorsConfig,
        *,
        base_dir: Path | None = None,
        rule_factories: dict[str, Callable[[], Predictor]] | None = None,
        models_override: dict[str, Predictor] | None = None,
    ) -> None:
        self.config = config
        self._base_dir = base_dir
        self._rule_factories = (
            dict(rule_factories) if rule_factories is not None else dict(DEFAULT_RULE_FACTORIES)
        )
        self._models_override = dict(models_override) if models_override is not None else {}
        self._predictors: dict[str, FallbackPredictor | None] = {}
        self._initialize()

    def _initialize(self) -> None:
        for slot in KNOWN_SLOTS:
            raw_spec = (self.config.slots.get(slot) or "").strip()
            if raw_spec.lower() in UNSET_TOKENS:
                self._predictors[slot] = None
                continue

            rule_factory = self._rule_factories.get(slot)
            if rule_factory is None:
                raise PredictorConfigError(f"Nepostojeće pravilo za mjesto '{slot}'.")
            rule = rule_factory()
            slot_range = self.config.ranges[slot]

            if raw_spec == "rules":
                self._predictors[slot] = FallbackPredictor(
                    slot=slot,
                    rule=rule,
                    slot_range=slot_range,
                    configured_spec="rules",
                )
                continue

            # raw_spec starts with "model:"
            model_rel_path = raw_spec.removeprefix("model:").strip()
            inferred_version = _infer_version_from_path(model_rel_path)

            if slot in self._models_override:
                override_model = self._models_override[slot]
                self._predictors[slot] = FallbackPredictor(
                    slot=slot,
                    rule=rule,
                    slot_range=slot_range,
                    configured_spec=raw_spec,
                    model=override_model,
                    configured_version=str(getattr(override_model, "version", inferred_version)),
                )
                continue

            resolved_path = _resolve_model_path(model_rel_path, self._base_dir)
            try:
                loaded_model = _load_model_from_disk(resolved_path)
                version = str(getattr(loaded_model, "version", inferred_version))
                self._predictors[slot] = FallbackPredictor(
                    slot=slot,
                    rule=rule,
                    slot_range=slot_range,
                    configured_spec=raw_spec,
                    model=loaded_model,
                    configured_version=version,
                )
            except Exception as exc:
                reason = f"model_load_failed:{type(exc).__name__}"
                logger.disabled = False
                logger.warning(
                    "Povratak prediktora na pravilo pri učitavanju: slot=%s razlog=%s verzija=%s",
                    slot,
                    reason,
                    inferred_version,
                )
                self._predictors[slot] = FallbackPredictor(
                    slot=slot,
                    rule=rule,
                    slot_range=slot_range,
                    configured_spec=raw_spec,
                    model=None,
                    load_error=reason,
                    configured_version=inferred_version,
                )

    def set_model(self, slot: str, model: Predictor) -> FallbackPredictor:
        """Postavi (npr. u testu) model za zadano mjesto uz postojeće rezervno pravilo."""
        if slot not in KNOWN_SLOTS:
            raise KeyError(f"Nepoznato mjesto prediktora: '{slot}'.")
        rule_factory = self._rule_factories.get(slot)
        if rule_factory is None:
            raise PredictorNotConfiguredError(f"Mjesto '{slot}' još nema rezervno pravilo.")
        wrapper = FallbackPredictor(
            slot=slot,
            rule=rule_factory(),
            slot_range=self.config.ranges[slot],
            configured_spec=f"model:{getattr(model, 'name', slot)}",
            model=model,
            configured_version=str(getattr(model, "version", "0.1")),
        )
        self._predictors[slot] = wrapper
        return wrapper

    def get_predictor(self, slot: str) -> FallbackPredictor:
        """Vrati omotač prediktora za traženo mjesto."""
        if slot not in KNOWN_SLOTS:
            raise KeyError(f"Nepoznato mjesto prediktora: '{slot}'.")
        predictor = self._predictors.get(slot)
        if predictor is None:
            raise PredictorNotConfiguredError(f"Prediktor za mjesto '{slot}' nije postavljen.")
        return predictor

    def list_models(self) -> list[ModelSlotStatus]:
        """Vrati pregled svih mjesta u registru za `GET /models`."""
        statuses: list[ModelSlotStatus] = []
        for slot in KNOWN_SLOTS:
            predictor = self._predictors.get(slot)
            if predictor is None:
                statuses.append(
                    ModelSlotStatus(
                        slot=slot,
                        implementation="nije postavljeno",
                        version=None,
                        source=None,
                        fallback_active=False,
                    )
                )
            else:
                statuses.append(
                    ModelSlotStatus(
                        slot=slot,
                        implementation=predictor.name,
                        version=predictor.version,
                        source=predictor.source,
                        fallback_active=predictor.fallback_active,
                    )
                )
        return statuses


def build_predictor_registry(
    yaml_path: Path | None = None,
    *,
    models_override: dict[str, Predictor] | None = None,
) -> PredictorRegistry:
    config = load_predictors_config(yaml_path)
    base_dir = yaml_path.parent if yaml_path is not None else get_settings().data_dir
    return PredictorRegistry(
        config,
        base_dir=base_dir,
        models_override=models_override,
    )


@lru_cache
def get_predictor_registry() -> PredictorRegistry:
    return build_predictor_registry()


def get_predictor(slot: str) -> FallbackPredictor:
    """Dohvati aktivni prediktor s povratkom na pravilo za zadano mjesto."""
    return get_predictor_registry().get_predictor(slot)
