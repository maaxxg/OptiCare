import logging
import time
from collections.abc import Sequence

import httpx

from app.adapters.types import AdapterError, LatLon, TravelMatrix

logger = logging.getLogger(__name__)

# Public ORS API: matrix limited to 3500 routes (sources x destinations) per request.
MAX_MATRIX_ROUTES = 3500


class OrsRoutingClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openrouteservice.org",
        timeout_s: float = 30,
        client: httpx.Client | None = None,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/v2/matrix/driving-car"
        self._headers = {"Authorization": api_key}
        self._client = client or httpx.Client(timeout=timeout_s)

    def matrix(self, points: Sequence[LatLon]) -> TravelMatrix:
        n = len(points)
        if n * n > MAX_MATRIX_ROUTES:
            raise AdapterError(
                f"Too many points for ORS matrix: {n} (limit {MAX_MATRIX_ROUTES} routes)"
            )
        body = {
            # ORS order is [lon, lat]
            "locations": [[p.lon, p.lat] for p in points],
            "metrics": ["duration", "distance"],
        }
        start = time.monotonic()
        try:
            resp = self._client.post(self._url, json=body, headers=self._headers)
        except httpx.HTTPError as exc:
            raise AdapterError(f"ORS request failed: {type(exc).__name__}") from None
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.info("ORS matrix points=%s status=%s latency_ms=%s", n, resp.status_code, latency_ms)
        if resp.status_code != 200:
            raise AdapterError(f"ORS returned HTTP {resp.status_code}")
        try:
            data = resp.json()
            durations = data["durations"]
            distances = data["distances"]
        except (ValueError, KeyError, TypeError):
            raise AdapterError("ORS response is malformed") from None
        for name, m in (("durations", durations), ("distances", distances)):
            if (
                not isinstance(m, list)
                or len(m) != n
                or any(not isinstance(r, list) or len(r) != n for r in m)
            ):
                raise AdapterError(f"ORS {name} matrix has unexpected shape")
            for i, row in enumerate(m):
                for j, v in enumerate(row):
                    if v is None:
                        raise AdapterError(f"ORS found no route between points {i} and {j}")
        return TravelMatrix(
            durations_s=[[float(v) for v in r] for r in durations],
            distances_m=[[float(v) for v in r] for r in distances],
        )
