from dataclasses import dataclass


@dataclass(frozen=True)
class LatLon:
    lat: float
    lon: float


@dataclass(frozen=True)
class TravelMatrix:
    """NxN matrices in the same order as the input points."""

    durations_s: list[list[float]]
    distances_m: list[list[float]]


class AdapterError(Exception):
    """A real external-service adapter failed. Messages never contain prompt or response content."""
