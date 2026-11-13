import unicodedata
from typing import Protocol

from app.adapters.types import LatLon


class GeocodingClient(Protocol):
    def geocode(self, query: str) -> LatLon | None: ...


# Public town-centre coordinates of the five ispostava towns.
TOWN_CENTRES: dict[str, LatLon] = {
    "gospic": LatLon(44.5461, 15.3747),
    "otocac": LatLon(44.8694, 15.2358),
    "senj": LatLon(44.9894, 14.9042),
    "korenica": LatLon(44.7561, 15.7061),
    "novalja": LatLon(44.5569, 14.8856),
}


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.casefold())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.replace("đ", "d")


class MockGeocodingClient:
    def geocode(self, query: str) -> LatLon | None:
        q = _normalize(query)
        for town, point in TOWN_CENTRES.items():
            if town in q:
                return point
        return None
