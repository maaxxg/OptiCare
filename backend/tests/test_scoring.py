"""Testovi za modul bodovanja (app.scoring).

Pokrivaju:
- učitavanje YAML konfiguracije iz stvarne datoteke,
- razrješavanje pojaseva, mappinga i logičkih faktora,
- izračun ukupnog boda i razine za razne profile,
- rubne slučajeve (nedostajuća udaljenost, nepoznata mobilnost).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.scoring import (
    ScoringConfig,
    ScoringConfigError,
    ScoringResult,
    _determine_level,
    _patient_age,
    _resolve_bands,
    _resolve_factor,
    compute_score,
    load_scoring_config,
)

# ---------------------------------------------------------------------------
# Pomoćni podaci (fixture)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SCORING_YAML = REPO_ROOT / "data" / "domain" / "scoring_factors.yaml"


@pytest.fixture
def config() -> ScoringConfig:
    return load_scoring_config(SCORING_YAML)


# ---------------------------------------------------------------------------
# Testovi učitavanja konfiguracije
# ---------------------------------------------------------------------------


def test_load_scoring_config_parses_all_factors(config: ScoringConfig) -> None:
    assert len(config.factors) == 7
    keys = [f.key for f in config.factors]
    assert "mobility_class" in keys
    assert "distance_to_destination" in keys
    assert "companion_available" in keys


def test_load_scoring_config_weights_sum_to_one(config: ScoringConfig) -> None:
    total = sum(f.weight for f in config.factors)
    assert abs(total - 1.0) < 0.01, f"Težine se zbrajaju u {total}, a očekuje se ~1.0"


def test_load_scoring_config_has_three_levels(config: ScoringConfig) -> None:
    assert len(config.levels) == 3
    level_keys = [lv.key for lv in config.levels]
    assert level_keys == ["low", "medium", "high"]


# ---------------------------------------------------------------------------
# Testovi razrješavanja faktora
# ---------------------------------------------------------------------------


def test_resolve_bands_below_first() -> None:
    from app.scoring import BandEntry

    bands = [
        BandEntry(max=20, value=0.0),
        BandEntry(max=50, value=0.4),
        BandEntry(max=None, value=1.0),
    ]
    assert _resolve_bands(bands, 10) == 0.0


def test_resolve_bands_above_last() -> None:
    from app.scoring import BandEntry

    bands = [
        BandEntry(max=20, value=0.0),
        BandEntry(max=50, value=0.4),
        BandEntry(max=None, value=1.0),
    ]
    assert _resolve_bands(bands, 150) == 1.0


def test_resolve_factor_boolean_true(config: ScoringConfig) -> None:
    lives_alone_factor = next(f for f in config.factors if f.key == "lives_alone")
    assert _resolve_factor(lives_alone_factor, True) == 1.0


def test_resolve_factor_boolean_false(config: ScoringConfig) -> None:
    lives_alone_factor = next(f for f in config.factors if f.key == "lives_alone")
    assert _resolve_factor(lives_alone_factor, False) == 0.0


def test_resolve_factor_mapping_wheelchair(config: ScoringConfig) -> None:
    mobility_factor = next(f for f in config.factors if f.key == "mobility_class")
    assert _resolve_factor(mobility_factor, "wheelchair") == 0.8


def test_resolve_factor_mapping_unknown_key(config: ScoringConfig) -> None:
    mobility_factor = next(f for f in config.factors if f.key == "mobility_class")
    assert _resolve_factor(mobility_factor, "jetpack") == 0.0


def test_resolve_factor_none_input(config: ScoringConfig) -> None:
    distance_factor = next(f for f in config.factors if f.key == "distance_to_destination")
    assert _resolve_factor(distance_factor, None) == 0.0


# ---------------------------------------------------------------------------
# Testovi dobi
# ---------------------------------------------------------------------------


def test_patient_age_normal() -> None:
    assert _patient_age(1951, reference_date=date(2026, 11, 14)) == 75


def test_patient_age_none() -> None:
    assert _patient_age(None) is None


# ---------------------------------------------------------------------------
# Testovi razina
# ---------------------------------------------------------------------------


def test_determine_level_low(config: ScoringConfig) -> None:
    level = _determine_level(config, 0.10)
    assert level.key == "low"


def test_determine_level_medium(config: ScoringConfig) -> None:
    level = _determine_level(config, 0.45)
    assert level.key == "medium"


def test_determine_level_high(config: ScoringConfig) -> None:
    level = _determine_level(config, 0.75)
    assert level.key == "high"


def test_determine_level_boundary_low_medium(config: ScoringConfig) -> None:
    """Bod 0.35 je gornja granica 'low' (isključiva) → pada u 'medium'."""
    level = _determine_level(config, 0.35)
    assert level.key == "medium"


def test_determine_level_boundary_medium_high(config: ScoringConfig) -> None:
    """Bod 0.60 je gornja granica 'medium' (isključiva) → pada u 'high'."""
    level = _determine_level(config, 0.60)
    assert level.key == "high"


# ---------------------------------------------------------------------------
# Testovi compute_score — profili iz patient_profiles.yaml
# ---------------------------------------------------------------------------


def test_compute_score_p18_milka_high(config: ScoringConfig) -> None:
    """Milka Rončević (p18): štap, živi sama, 86 god., landline, 3 propuštena, bez pratnje.
    Očekivana razina: high.
    """
    result = compute_score(
        patient_id=18,
        mobility_class="cane",
        distance_km=2.0,  # unutar grada Gospića
        birth_year=1940,
        lives_alone=True,
        missed_visits_last_year=3,
        phone_type="landline",
        companion_available=False,
        config=config,
        reference_date=date(2026, 11, 14),
    )
    assert isinstance(result, ScoringResult)
    assert result.level_key == "high"
    assert result.total_score >= 0.60
    assert len(result.factors) == 7


def test_compute_score_p05_stjepan_low(config: ScoringConfig) -> None:
    """Stjepan Perković (p05): hoda, 71 god., smartphone, 0 propuštenih, ima pratnju=false,
    ne živi sam, vlastiti auto. Očekivana razina: low.
    """
    result = compute_score(
        patient_id=5,
        mobility_class="walks",
        distance_km=25.0,  # Perušić–OB Gospić ~25 km
        birth_year=1955,
        lives_alone=False,
        missed_visits_last_year=0,
        phone_type="smartphone",
        companion_available=False,
        config=config,
        reference_date=date(2026, 11, 14),
    )
    assert result.level_key == "low"
    assert result.total_score < 0.35


def test_compute_score_p02_ivan_wheelchair(config: ScoringConfig) -> None:
    """Ivan Kovačević (p02): kolica, 68 god., basic_mobile, pratnja, ne živi sam, 0 propuštenih.
    Očekivana razina: medium ili high (kolica donose velik doprinos).
    """
    result = compute_score(
        patient_id=2,
        mobility_class="wheelchair",
        distance_km=57.0,  # Otočac–OB Gospić
        birth_year=1958,
        lives_alone=False,
        missed_visits_last_year=0,
        phone_type="basic_mobile",
        companion_available=True,
        config=config,
        reference_date=date(2026, 11, 14),
    )
    assert result.level_key in ("medium", "high")


def test_compute_score_no_distance(config: ScoringConfig) -> None:
    """Kad distance_km nije poznat, faktor udaljenosti doprinosi 0."""
    result = compute_score(
        patient_id=99,
        mobility_class="walks",
        distance_km=None,
        birth_year=1980,
        lives_alone=False,
        missed_visits_last_year=0,
        phone_type="smartphone",
        companion_available=True,
        config=config,
        reference_date=date(2026, 11, 14),
    )
    dist_factor = next(f for f in result.factors if f.key == "distance_to_destination")
    assert dist_factor.raw_value == 0.0
    assert dist_factor.weighted_value == 0.0


def test_compute_score_contributions_sum_to_total(config: ScoringConfig) -> None:
    """Zbroj weighted_value svih faktora mora biti jednak total_score."""
    result = compute_score(
        patient_id=1,
        mobility_class="cane",
        distance_km=49.0,
        birth_year=1951,
        lives_alone=False,
        missed_visits_last_year=4,
        phone_type="landline",
        companion_available=True,
        config=config,
        reference_date=date(2026, 11, 14),
    )
    contributions_sum = sum(f.weighted_value for f in result.factors)
    assert abs(contributions_sum - result.total_score) < 0.001


def test_compute_score_all_factors_present(config: ScoringConfig) -> None:
    """Svaki faktor iz konfiguracije mora biti u rezultatu."""
    result = compute_score(
        patient_id=1,
        mobility_class="walks",
        distance_km=10.0,
        birth_year=2000,
        lives_alone=False,
        missed_visits_last_year=0,
        phone_type="smartphone",
        companion_available=True,
        config=config,
        reference_date=date(2026, 11, 14),
    )
    result_keys = {f.key for f in result.factors}
    config_keys = {f.key for f in config.factors}
    assert result_keys == config_keys


def test_compute_score_max_need_patient(config: ScoringConfig) -> None:
    """Hipotetički pacijent s maksimalnom potrebom po svim faktorima → score blizu 1.0, high."""
    result = compute_score(
        patient_id=999,
        mobility_class="stretcher",
        distance_km=200.0,
        birth_year=1930,
        lives_alone=True,
        missed_visits_last_year=5,
        phone_type="landline",
        companion_available=False,
        config=config,
        reference_date=date(2026, 11, 14),
    )
    assert result.total_score >= 0.95
    assert result.level_key == "high"


# ---------------------------------------------------------------------------
# Validacija konfiguracije
# ---------------------------------------------------------------------------


def _mutated(mutate) -> dict:  # type: ignore[no-untyped-def]
    data = yaml.safe_load(SCORING_YAML.read_text(encoding="utf-8"))
    mutate(data)
    return data


def _factor(data: dict, key: str) -> dict:
    return next(f for f in data["factors"] if f["key"] == key)


def _bands_and_mapping(d: dict) -> None:
    _factor(d, "age")["mapping"] = {"x": 0.5}


def _only_if_true(d: dict) -> None:
    del _factor(d, "lives_alone")["if_false"]


def _empty_bands(d: dict) -> None:
    _factor(d, "age")["bands"] = []


def _non_increasing(d: dict) -> None:
    _factor(d, "age")["bands"][1]["max"] = 65


def _last_band_closed(d: dict) -> None:
    _factor(d, "age")["bands"][-1]["max"] = 120


def _weights_high(d: dict) -> None:
    _factor(d, "age")["weight"] = 0.25


def _unknown_key(d: dict) -> None:
    _factor(d, "age")["key"] = "shoe_size"


def _duplicate_key(d: dict) -> None:
    d["factors"].append(dict(_factor(d, "age"), weight=0.0))


def _missing_stretcher(d: dict) -> None:
    del _factor(d, "mobility_class")["mapping"]["stretcher"]


def _empty_levels(d: dict) -> None:
    d["levels"] = []


def _level_gap(d: dict) -> None:
    d["levels"][1]["min_score"] = 0.40


def _last_level_too_low(d: dict) -> None:
    d["levels"][-1]["max_score"] = 1.0


@pytest.mark.parametrize(
    "mutate",
    [
        _bands_and_mapping,
        _only_if_true,
        _empty_bands,
        _non_increasing,
        _last_band_closed,
        _weights_high,
        _unknown_key,
        _duplicate_key,
        _missing_stretcher,
        _empty_levels,
        _level_gap,
        _last_level_too_low,
    ],
)
def test_invalid_scoring_config_is_rejected(mutate, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "scoring.yaml"
    path.write_text(yaml.safe_dump(_mutated(mutate)), encoding="utf-8")
    with pytest.raises(ScoringConfigError):
        load_scoring_config(path)


def test_score_endpoint_returns_croatian_error_on_bad_config(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def broken() -> ScoringConfig:
        raise ScoringConfigError("broken")

    monkeypatch.setattr("app.main.get_scoring_config", broken)
    app.dependency_overrides[get_db] = lambda: None
    try:
        response = TestClient(app).get("/score/1")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 500
    assert response.json()["detail"].startswith("Bodovanje trenutačno nije dostupno")
