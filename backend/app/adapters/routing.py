import math
from collections.abc import Sequence
from typing import Protocol

from app.adapters.types import LatLon, TravelMatrix

EARTH_RADIUS_M = 6_371_000.0
ROAD_FACTOR = 1.3
AVERAGE_SPEED_KMH = 50.0


class RoutingClient(Protocol):
    def matrix(self, points: Sequence[LatLon]) -> TravelMatrix: ...


def haversine_m(a: LatLon, b: LatLon) -> float:
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dphi = p2 - p1
    dlmb = math.radians(b.lon - a.lon)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


class MockRoutingClient:
    def matrix(self, points: Sequence[LatLon]) -> TravelMatrix:
        n = len(points)
        distances = [[0.0] * n for _ in range(n)]
        durations = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                d = haversine_m(points[i], points[j]) * ROAD_FACTOR
                distances[i][j] = d
                durations[i][j] = d / (AVERAGE_SPEED_KMH * 1000 / 3600)
        return TravelMatrix(durations_s=durations, distances_m=distances)
