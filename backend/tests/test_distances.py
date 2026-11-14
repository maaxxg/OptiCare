"""Testovi za modul app.distances."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.adapters.types import AdapterError, TravelMatrix
from app.distances import road_distance_km


def _patient(lat: float | None, lon: float | None) -> SimpleNamespace:
    return SimpleNamespace(id=1, latitude=lat, longitude=lon)


def _facility(lat: float | None, lon: float | None) -> SimpleNamespace:
    return SimpleNamespace(latitude=lat, longitude=lon)


class _MockRoutingClient:
    def __init__(self, distance_m: float) -> None:
        self.distance_m = distance_m

    def matrix(self, points: Any) -> TravelMatrix:
        return TravelMatrix(
            durations_s=[[0.0, 100.0], [100.0, 0.0]],
            distances_m=[[0.0, self.distance_m], [self.distance_m, 0.0]],
        )


def test_road_distance_km_success() -> None:
    patient = _patient(45.81, 15.98)
    facility = _facility(45.82, 15.99)
    client = _MockRoutingClient(15_400.0)

    dist = road_distance_km(patient, facility, client)  # type: ignore[arg-type]
    assert dist == pytest.approx(15.4)


def test_road_distance_km_none_facility() -> None:
    patient = _patient(45.81, 15.98)
    client = _MockRoutingClient(1000.0)
    assert road_distance_km(patient, None, client) is None  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("p_lat", "p_lon", "f_lat", "f_lon"),
    [
        (None, 15.98, 45.82, 15.99),
        (45.81, None, 45.82, 15.99),
        (45.81, 15.98, None, 15.99),
        (45.81, 15.98, 45.82, None),
    ],
)
def test_road_distance_km_missing_coords(
    p_lat: float | None, p_lon: float | None, f_lat: float | None, f_lon: float | None
) -> None:
    client = _MockRoutingClient(1000.0)
    assert (
        road_distance_km(_patient(p_lat, p_lon), _facility(f_lat, f_lon), client)  # type: ignore[arg-type]
        is None
    )


def test_road_distance_km_adapter_error() -> None:
    class _FailingClient:
        def matrix(self, points: Any) -> Any:
            raise AdapterError("connection failed")

    assert (
        road_distance_km(_patient(45.81, 15.98), _facility(45.82, 15.99), _FailingClient())  # type: ignore[arg-type]
        is None
    )


@pytest.mark.parametrize("invalid_dist", [-100.0, float("nan"), float("inf"), float("-inf")])
def test_road_distance_km_invalid_values(invalid_dist: float) -> None:
    class _Client:
        def matrix(self, points: Any) -> TravelMatrix:
            return TravelMatrix(
                durations_s=[[0.0, 0.0], [0.0, 0.0]],
                distances_m=[[0.0, invalid_dist], [invalid_dist, 0.0]],
            )

    assert (
        road_distance_km(_patient(45.81, 15.98), _facility(45.82, 15.99), _Client())  # type: ignore[arg-type]
        is None
    )
