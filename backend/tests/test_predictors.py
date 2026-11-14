"""Testovi za sučelje i registar prediktora (E4-T1, KAN-28)."""

from __future__ import annotations

import logging
import math
import pickle
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import get_settings
from app.main import StartupCheckError, app, lifespan
from app.predictors import (
    KNOWN_SLOTS,
    Prediction,
    Predictor,
    PredictorConfigError,
    PredictorNotConfiguredError,
    build_predictor_registry,
    get_predictor,
    get_predictor_registry,
    load_predictors_config,
)
from app.predictors.api import list_models_endpoint, predict_slot_endpoint
from app.predictors.registry import PREDICTORS_RELATIVE_PATH
from app.scoring import compute_score
from app.seed import PATIENT_PROFILES_PATH, load_patient_profiles


class DummyPicklableModel:
    """Jednostavan model koji se može serijalizirati u datoteku za testiranje registra."""

    def __init__(
        self,
        *,
        value: float = 42.0,
        high: float | None = 65.0,
        name: str = "visit_duration_gbm",
        version: str = "0.1",
        should_raise: bool = False,
    ) -> None:
        self.name = name
        self.version = version
        self._value = value
        self._high = high
        self._should_raise = should_raise

    def predict(self, features: dict[str, Any]) -> Prediction:
        if self._should_raise:
            raise RuntimeError("Simulirana greška modela")
        return Prediction(
            value=self._value,
            low=None,
            high=self._high,
            explanation={"dept_contribution": self._value},
            source="model",
        )


def test_prediction_source_accepts_only_rules_or_model() -> None:
    p_rules = Prediction(value=30.0, explanation={"base": 30.0}, source="rules")
    p_model = Prediction(value=30.0, low=20.0, high=45.0, explanation={"f1": 30.0}, source="model")
    assert p_rules.source == "rules"
    assert p_model.source == "model"

    with pytest.raises(ValidationError):
        Prediction(value=30.0, explanation={}, source="fallback")  # type: ignore[arg-type]


def test_default_predictors_yaml_is_valid_and_implements_protocol() -> None:
    get_predictor_registry.cache_clear()
    registry = get_predictor_registry()
    for slot in ("visit_duration", "service_time", "support_need", "travel_time"):
        pred = registry.get_predictor(slot)
        assert isinstance(pred, Predictor)
        assert pred.source == "rules"
        assert pred.fallback_active is False

    with pytest.raises(PredictorNotConfiguredError):
        registry.get_predictor("demand")


def test_missing_model_file_falls_back_to_rule_and_logs_without_pii(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    orig_yaml = (get_settings().data_dir / PREDICTORS_RELATIVE_PATH).read_text(encoding="utf-8")
    modified_yaml = orig_yaml.replace(
        "visit_duration: rules",
        "visit_duration: model:models/nonexistent_visit_duration-0.2.joblib",
    )
    cfg_path = tmp_path / "predictors.yaml"
    cfg_path.write_text(modified_yaml, encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        registry = build_predictor_registry(cfg_path)
        predictor = registry.get_predictor("visit_duration")
        result = predictor.predict(
            {
                "department": "cardiology",
                "visit_type": "first_visit",
                "mbo": "123456789",
                "patient_name": "Tajno Ime",
            }
        )

    assert result.source == "rules"
    assert result.value == 50.0
    assert result.high == 80.0
    assert predictor.fallback_active is True

    warnings = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings, "Očekivan je zapis upozorenja u logu pri povratku na pravilo"
    combined_log = "\n".join(warnings)
    assert "visit_duration" in combined_log
    assert "0.2" in combined_log
    # Pravilo 12: nikad ne logirati ulazne značajke ni MBO
    assert "123456789" not in combined_log
    assert "Tajno Ime" not in combined_log


@pytest.mark.parametrize(
    "bad_model",
    [
        DummyPicklableModel(value=1.0, high=10.0, version="0.3"),  # ispod min (5.0)
        DummyPicklableModel(value=600.0, high=650.0, version="0.3"),  # iznad max (480.0)
        DummyPicklableModel(value=50.0, high=900.0, version="0.3"),  # high iznad max
        DummyPicklableModel(value=math.nan, high=80.0, version="0.3"),  # NaN
        DummyPicklableModel(value=math.inf, high=80.0, version="0.3"),  # Inf
        DummyPicklableModel(should_raise=True, version="0.3"),  # baca iznimku
    ],
)
def test_out_of_range_or_nan_model_falls_back_to_rule_and_logs(
    bad_model: DummyPicklableModel, caplog: pytest.LogCaptureFixture
) -> None:
    registry = build_predictor_registry()
    registry.set_model("visit_duration", bad_model)
    predictor = registry.get_predictor("visit_duration")

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        pred = predictor.predict(
            {
                "department": "internal_medicine",
                "visit_type": "follow_up",
                "mbo": "987654321",
            }
        )

    assert pred.source == "rules"
    assert pred.value == 25.0
    assert pred.high == 45.0
    assert predictor.fallback_active is True

    warnings = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warnings) == 1
    assert "visit_duration" in warnings[0]
    assert "0.3" in warnings[0]
    assert "987654321" not in warnings[0]


def test_single_line_config_change_switches_implementation_to_model(tmp_path: Path) -> None:
    model_file = tmp_path / "visit_duration-0.4.joblib"
    model_file.write_bytes(pickle.dumps(DummyPicklableModel(value=55.0, high=92.0, version="0.4")))

    orig_yaml = (get_settings().data_dir / PREDICTORS_RELATIVE_PATH).read_text(encoding="utf-8")
    # Zamjena točno jednog retka u konfiguraciji
    one_line_changed = orig_yaml.replace(
        "  visit_duration: rules",
        "  visit_duration: model:visit_duration-0.4.joblib",
    )
    assert orig_yaml != one_line_changed
    cfg_path = tmp_path / "predictors.yaml"
    cfg_path.write_text(one_line_changed, encoding="utf-8")

    registry = build_predictor_registry(cfg_path)
    predictor = registry.get_predictor("visit_duration")
    pred = predictor.predict({"department": "cardiology", "visit_type": "first_visit"})

    assert pred.source == "model"
    assert pred.value == 55.0
    assert pred.high == 92.0
    assert predictor.fallback_active is False

    statuses = {s.slot: s for s in registry.list_models()}
    assert statuses["visit_duration"].source == "model"
    assert statuses["visit_duration"].implementation == "visit_duration_gbm"
    assert statuses["visit_duration"].version == "0.4"
    assert statuses["visit_duration"].fallback_active is False


def test_support_need_via_registry_matches_compute_score_for_all_profiles() -> None:
    profiles = load_patient_profiles(get_settings().data_dir / PATIENT_PROFILES_PATH)
    predictor = get_predictor("support_need")
    ref_date = date(2026, 11, 14)

    for idx, profile in enumerate(profiles, start=1):
        distance_km = float(idx * 6)
        direct = compute_score(
            patient_id=idx,
            mobility_class=profile["mobility_class"],
            distance_km=distance_km,
            birth_year=profile.get("birth_year"),
            lives_alone=bool(profile.get("lives_alone", False)),
            missed_visits_last_year=int(profile.get("missed_visits_last_year", 0)),
            phone_type=profile["phone_type"],
            companion_available=bool(profile.get("companion", False)),
            reference_date=ref_date,
        )
        via_registry = predictor.predict(
            {
                "patient_id": idx,
                "mobility_class": profile["mobility_class"],
                "distance_km": distance_km,
                "birth_year": profile.get("birth_year"),
                "lives_alone": bool(profile.get("lives_alone", False)),
                "missed_visits_last_year": int(profile.get("missed_visits_last_year", 0)),
                "phone_type": profile["phone_type"],
                "companion_available": bool(profile.get("companion", False)),
                "reference_date": ref_date.isoformat(),
            }
        )

        assert via_registry.source == "rules"
        assert via_registry.value == direct.total_score
        assert via_registry.high == direct.total_score_upper
        expected_explanation = {f.key: f.weighted_value for f in direct.factors}
        assert via_registry.explanation == expected_explanation


def test_invalid_predictors_config_unknown_slot_or_rule_fails_validation(
    tmp_path: Path,
) -> None:
    orig_yaml = (get_settings().data_dir / PREDICTORS_RELATIVE_PATH).read_text(encoding="utf-8")

    # 1. Nepoznato mjesto u konfiguraciji
    bad_slot_yaml = orig_yaml + "\n  unknown_slot: rules\n"
    bad_slot_path = tmp_path / "bad_slot.yaml"
    bad_slot_path.write_text(bad_slot_yaml, encoding="utf-8")
    with pytest.raises(PredictorConfigError):
        load_predictors_config(bad_slot_path)

    # 2. Nepostojeće pravilo (demand: rules ili nepoznat naziv pravila)
    bad_rule_yaml = orig_yaml.replace("demand: unset", "demand: rules")
    bad_rule_path = tmp_path / "bad_rule.yaml"
    bad_rule_path.write_text(bad_rule_yaml, encoding="utf-8")
    with pytest.raises(PredictorConfigError):
        load_predictors_config(bad_rule_path)


def _enter_lifespan_sync() -> None:
    cm = lifespan(app)
    coro = cm.__aenter__()
    try:
        coro.send(None)
    except StopIteration:
        pass
    finally:
        coro.close()


def test_lifespan_raises_on_invalid_predictors_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Provjera u lifespanu: nepoznato mjesto ili nepostojeće pravilo ruše start aplikacije."""
    orig_yaml = (get_settings().data_dir / PREDICTORS_RELATIVE_PATH).read_text(encoding="utf-8")
    bad_yaml = orig_yaml.replace("visit_duration: rules", "visit_duration: nepostojece_pravilo")

    domain_dir = tmp_path / "domain"
    domain_dir.mkdir(parents=True, exist_ok=True)
    for yaml_file in (get_settings().data_dir / "domain").glob("*.yaml"):
        (domain_dir / yaml_file.name).write_text(
            yaml_file.read_text(encoding="utf-8"), encoding="utf-8"
        )
    (domain_dir / "predictors.yaml").write_text(bad_yaml, encoding="utf-8")

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    get_predictor_registry.cache_clear()

    try:
        with pytest.raises(StartupCheckError, match="Predictors configuration is invalid"):
            _enter_lifespan_sync()
    finally:
        monkeypatch.delenv("DATA_DIR", raising=False)
        get_settings.cache_clear()
        get_predictor_registry.cache_clear()


def test_endpoints_get_models_and_post_predict() -> None:
    get_predictor_registry.cache_clear()
    models = list_models_endpoint()
    by_slot = {m.slot: m for m in models}
    assert tuple(by_slot.keys()) == KNOWN_SLOTS
    assert by_slot["demand"].implementation == "nije postavljeno"
    assert by_slot["demand"].source is None
    assert by_slot["visit_duration"].source == "rules"
    assert by_slot["visit_duration"].fallback_active is False

    # Uspješna predikcija
    pred = predict_slot_endpoint(
        "visit_duration",
        {"department": "cardiology", "visit_type": "first_visit"},
    )
    assert pred.value == 50.0
    assert pred.high == 80.0
    assert pred.source == "rules"

    # 404 za nepoznato mjesto
    with pytest.raises(HTTPException) as exc_404:
        predict_slot_endpoint("nepoznato_mjesto", {})
    assert exc_404.value.status_code == 404

    # 404 za demand koji još nije postavljen
    with pytest.raises(HTTPException) as exc_demand:
        predict_slot_endpoint("demand", {})
    assert exc_demand.value.status_code == 404

    # 422 s hrvatskom porukom kad značajka nedostaje
    with pytest.raises(HTTPException) as exc_422:
        predict_slot_endpoint("visit_duration", {"department": "cardiology"})
    assert exc_422.value.status_code == 422
    assert "Nedostaje obvezna značajka" in str(exc_422.value.detail)


def test_http_endpoints_via_testclient() -> None:
    get_predictor_registry.cache_clear()
    client = TestClient(app)

    res_models = client.get("/models")
    assert res_models.status_code == 200
    items = {item["slot"]: item for item in res_models.json()}
    assert tuple(items.keys()) == KNOWN_SLOTS
    assert items["demand"]["implementation"] == "nije postavljeno"
    assert items["visit_duration"]["source"] == "rules"
    assert items["visit_duration"]["fallback_active"] is False

    res_pred = client.post(
        "/predict/service_time",
        json={"mobility_class": "wheelchair"},
    )
    assert res_pred.status_code == 200
    body = res_pred.json()
    assert body["value"] == 10.0
    assert body["source"] == "rules"
    assert body["explanation"] == {"mobility_class_min": 10.0}

    res_404 = client.post("/predict/unknown_slot", json={})
    assert res_404.status_code == 404

    res_demand = client.post("/predict/demand", json={})
    assert res_demand.status_code == 404

    res_422 = client.post("/predict/service_time", json={})
    assert res_422.status_code == 422
    assert "Nedostaje obvezna značajka" in res_422.json()["detail"]


def test_planner_estimates_seam_uses_predictor_registry() -> None:
    from app.codebooks import CodebookError
    from app.plan_schemas import EstimateSource
    from app.planner.estimates import boarding_minutes, visit_duration

    get_predictor_registry.cache_clear()
    est = visit_duration("cardiology", "first_visit")
    assert est.minutes == 80
    assert est.source == EstimateSource.RULES
    assert est.version == "1.0"

    assert boarding_minutes("wheelchair") == 10

    with pytest.raises(CodebookError):
        visit_duration("dialysis", "first_visit")
