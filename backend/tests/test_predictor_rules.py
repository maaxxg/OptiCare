"""Testovi za zadana pravila prediktora (E4-T2, KAN-29)."""

from __future__ import annotations

import math
from collections.abc import Sequence

import pytest

from app.adapters.types import AdapterError, LatLon, TravelMatrix
from app.codebooks import get_codebooks
from app.config import get_settings
from app.models import MobilityClass, VisitType
from app.predictors import (
    MissingFeatureError,
    PredictorExecutionError,
    PredictorInputError,
    ServiceTimeRule,
    TravelTimeRule,
    VisitDurationRule,
)
from app.seed import (
    FACILITIES_DATA,
    PATIENT_PROFILES_PATH,
    SETTLEMENT_COORDINATES,
    SLOT_TIMES,
    SLOT_VISIT_TYPE,
    load_patient_profiles,
)


class _FailingRoutingClient:
    def matrix(self, points: Sequence[LatLon]) -> TravelMatrix:
        raise AdapterError("Simulated ORS timeout")


class _NanRoutingClient:
    def matrix(self, points: Sequence[LatLon]) -> TravelMatrix:
        return TravelMatrix(
            durations_s=[[0.0, math.nan], [math.nan, 0.0]],
            distances_m=[[0.0, 1000.0], [1000.0, 0.0]],
        )


def test_visit_duration_rule_matches_every_yaml_entry() -> None:
    codebooks = get_codebooks()
    rule = VisitDurationRule()

    assert len(codebooks.visit_durations) > 0
    for entry in codebooks.visit_durations:
        pred = rule.predict(
            {
                "department": entry.department.value,
                "visit_type": entry.visit_type.value,
            }
        )
        assert pred.value == float(entry.median_min)
        assert pred.high == float(entry.p90_min)
        assert pred.low is None
        assert pred.explanation == {
            "median_min": float(entry.median_min),
            "p90_min": float(entry.p90_min),
        }
        assert pred.source == "rules"


def test_all_seed_and_demo_visit_combinations_exist_in_visit_duration_rule() -> None:
    rule = VisitDurationRule()

    # 1. Sve kombinacije iz seed.py (SLOT_TIMES + SLOT_VISIT_TYPE)
    for _facility_key, departments in SLOT_TIMES.items():
        for department in departments:
            visit_type = SLOT_VISIT_TYPE.get(department, VisitType.FOLLOW_UP)
            pred = rule.predict(
                {
                    "department": department.value,
                    "visit_type": visit_type.value,
                }
            )
            assert pred.value > 0
            assert pred.high is not None and pred.high >= pred.value

    # 2. Sve kombinacije iz 18 demo profila pacijenata (patient_profiles.yaml)
    profiles = load_patient_profiles(get_settings().data_dir / PATIENT_PROFILES_PATH)
    assert len(profiles) == 18
    for profile in profiles:
        visit = profile["visit"]
        pred = rule.predict(
            {
                "department": visit["department"],
                "visit_type": visit["visit_type"],
            }
        )
        assert pred.value > 0
        assert pred.high is not None and pred.high >= pred.value


def test_visit_duration_rule_rejects_unlisted_or_missing_combination() -> None:
    rule = VisitDurationRule()

    # Dijaliza nema "first_visit" u tablici
    with pytest.raises(PredictorInputError):
        rule.predict({"department": "dialysis", "visit_type": "first_visit"})

    # Nepostojeća djelatnost
    with pytest.raises(PredictorInputError):
        rule.predict({"department": "dermatology", "visit_type": "first_visit"})

    # Nedostaje značajka
    with pytest.raises(MissingFeatureError):
        rule.predict({"department": "cardiology"})


def test_service_time_rule_matches_all_mobility_classes_in_yaml() -> None:
    codebooks = get_codebooks()
    rule = ServiceTimeRule()

    assert set(codebooks.boarding_time_min.keys()) == set(MobilityClass)
    for mobility in MobilityClass:
        expected = float(codebooks.boarding_time_min[mobility])
        pred = rule.predict(
            {
                "mobility_class": mobility.value,
                # Dodatna polja (kat, lift, pratnja) ne mijenjaju pravilo
                "floor": 3,
                "elevator": False,
                "companion": True,
            }
        )
        assert pred.value == expected
        assert pred.low is None
        assert pred.high is None
        assert pred.explanation == {"mobility_class_min": expected}
        assert pred.source == "rules"

    with pytest.raises(PredictorInputError):
        rule.predict({"mobility_class": "hoverboard"})

    with pytest.raises(MissingFeatureError):
        rule.predict({})


def test_travel_time_rule_mock_adapter_and_error_handling() -> None:
    rule = TravelTimeRule()
    u_lat, u_lon = SETTLEMENT_COORDINATES["Udbina"]
    gospic = next(f for f in FACILITIES_DATA if f["key"] == "ob_gospic")

    pred = rule.predict(
        {
            "from": {"lat": u_lat, "lon": u_lon},
            "to": {"lat": gospic["lat"], "lon": gospic["lon"]},
        }
    )
    assert pred.source == "rules"
    assert math.isfinite(pred.value)
    assert pred.value > 0.0
    assert pred.explanation == {"travel_time_min": pred.value}

    # Greška adaptera mora baciti grešku, nikad vratiti izmišljeni broj
    failing_rule = TravelTimeRule(routing_client=_FailingRoutingClient())
    with pytest.raises(PredictorExecutionError):
        failing_rule.predict(
            {
                "from": {"lat": u_lat, "lon": u_lon},
                "to": {"lat": gospic["lat"], "lon": gospic["lon"]},
            }
        )

    nan_rule = TravelTimeRule(routing_client=_NanRoutingClient())
    with pytest.raises(PredictorExecutionError):
        nan_rule.predict(
            {
                "from": {"lat": u_lat, "lon": u_lon},
                "to": {"lat": gospic["lat"], "lon": gospic["lon"]},
            }
        )

    # Nedostaju ili su neispravne koordinate
    with pytest.raises(MissingFeatureError):
        rule.predict({"from": {"lat": u_lat, "lon": u_lon}})

    with pytest.raises(PredictorInputError):
        rule.predict(
            {
                "from": {"lat": 999.0, "lon": u_lon},
                "to": {"lat": gospic["lat"], "lon": gospic["lon"]},
            }
        )
