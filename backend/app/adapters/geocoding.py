import unicodedata
from dataclasses import dataclass
from typing import Protocol

from app.adapters.types import LatLon

COUNTY_LIKA_SENJ = "Ličko-senjska"


@dataclass(frozen=True)
class GeocodedAddress:
    lat: float
    lon: float
    settlement: str
    municipality: str
    county: str = COUNTY_LIKA_SENJ

    @property
    def point(self) -> LatLon:
        return LatLon(self.lat, self.lon)


class GeocodingClient(Protocol):
    def geocode(self, query: str) -> LatLon | None: ...

    def geocode_address(self, query: str) -> GeocodedAddress | None: ...


# Public town-centre coordinates of the five ispostava towns.
TOWN_CENTRES: dict[str, LatLon] = {
    "gospic": LatLon(44.5461, 15.3747),
    "otocac": LatLon(44.8694, 15.2358),
    "senj": LatLon(44.9894, 14.9042),
    "korenica": LatLon(44.7561, 15.7061),
    "novalja": LatLon(44.5569, 14.8856),
}


@dataclass(frozen=True)
class _SettlementEntry:
    address: GeocodedAddress
    tokens: tuple[str, ...]


# Ordered from most specific (multi-word & smaller settlements) to Gospić last,
# so free-text sentences mentioning both a home village and "u bolnicu u Gospić"
# match the home settlement first.
SETTLEMENT_DIRECTORY: tuple[_SettlementEntry, ...] = (
    _SettlementEntry(
        GeocodedAddress(44.52694, 15.17603, "Baške Oštarije", "Karlobag"),
        ("baske ostarije", "baskim ostarijama"),
    ),
    _SettlementEntry(
        GeocodedAddress(44.75986, 15.24962, "Donji Kosinj", "Perušić"),
        ("donji kosinj", "donjem kosinju", "donjeg kosinja", "kosinju", "kosinj"),
    ),
    _SettlementEntry(
        GeocodedAddress(44.55213, 15.96096, "Donji Lapac", "Donji Lapac"),
        ("donji lapac", "donjem lapcu", "donjeg lapca", "53250"),
    ),
    _SettlementEntry(
        GeocodedAddress(44.60256, 15.41026, "Lički Osik", "Gospić"),
        ("licki osik", "lickom osiku", "lickog osika", "53201"),
    ),
    _SettlementEntry(
        GeocodedAddress(44.7897, 15.3175, "Ličko Lešće", "Otočac"),
        ("licko lesce", "lickom lescu"),
    ),
    _SettlementEntry(
        GeocodedAddress(44.5530, 15.3520, "Kaniža Gospićka", "Gospić"),
        ("kaniza gospicka", "kanizi gospickoj"),
    ),
    _SettlementEntry(
        GeocodedAddress(44.8805, 15.6212, "Plitvička Jezera", "Plitvička Jezera"),
        ("plitvicka jezera", "plitvickim jezerima", "53231"),
    ),
    _SettlementEntry(
        GeocodedAddress(44.9283, 14.9189, "Sveti Juraj", "Senj"),
        ("sveti juraj", "svetom jurju"),
    ),
    _SettlementEntry(
        GeocodedAddress(44.82659, 15.13895, "Kuterevo", "Otočac"),
        ("kuterevo", "kuterevu", "kutereva"),
    ),
    _SettlementEntry(
        GeocodedAddress(44.56175, 15.3214, "Smiljan", "Gospić"),
        ("smiljan", "smiljanu", "smiljana"),
    ),
    _SettlementEntry(
        GeocodedAddress(44.6400, 15.2500, "Pazarište", "Gospić"),
        ("pazariste", "pazaristu"),
    ),
    _SettlementEntry(
        GeocodedAddress(44.70625, 14.89778, "Jablanac", "Senj"),
        ("jablanac", "jablancu", "jablanca"),
    ),
    _SettlementEntry(
        GeocodedAddress(44.8211, 15.0489, "Krasno", "Senj"),
        ("krasno", "krasnu"),
    ),
    _SettlementEntry(
        GeocodedAddress(44.99981, 15.13127, "Brinje", "Brinje"),
        ("brinje", "brinju", "brinja", "53260"),
    ),
    _SettlementEntry(
        GeocodedAddress(44.52792, 15.0725, "Karlobag", "Karlobag"),
        ("karlobag", "karlobagu", "karlobaga", "53288"),
    ),
    _SettlementEntry(
        GeocodedAddress(
            TOWN_CENTRES["korenica"].lat,
            TOWN_CENTRES["korenica"].lon,
            "Korenica",
            "Plitvička Jezera",
        ),
        ("korenica", "korenici", "korenice", "53230"),
    ),
    _SettlementEntry(
        GeocodedAddress(44.39088, 15.68644, "Lovinac", "Lovinac"),
        ("lovinac", "lovincu", "lovinca", "53244"),
    ),
    _SettlementEntry(
        GeocodedAddress(
            TOWN_CENTRES["novalja"].lat,
            TOWN_CENTRES["novalja"].lon,
            "Novalja",
            "Novalja",
        ),
        ("novalja", "novalji", "novalje", "53291"),
    ),
    _SettlementEntry(
        GeocodedAddress(
            TOWN_CENTRES["otocac"].lat,
            TOWN_CENTRES["otocac"].lon,
            "Otočac",
            "Otočac",
        ),
        ("otocac", "otoccu", "otocca", "53220"),
    ),
    _SettlementEntry(
        GeocodedAddress(44.65002, 15.38326, "Perušić", "Perušić"),
        ("perusic", "perusicu", "perusica", "53202"),
    ),
    _SettlementEntry(
        GeocodedAddress(
            TOWN_CENTRES["senj"].lat,
            TOWN_CENTRES["senj"].lon,
            "Senj",
            "Senj",
        ),
        ("senj", "senju", "senja", "53270"),
    ),
    _SettlementEntry(
        GeocodedAddress(44.53175, 15.76652, "Udbina", "Udbina"),
        ("udbina", "udbini", "udbine", "53234"),
    ),
    _SettlementEntry(
        GeocodedAddress(44.85176, 15.42057, "Vrhovine", "Vrhovine"),
        ("vrhovine", "vrhovinama", "vrhovina", "53223"),
    ),
    _SettlementEntry(
        GeocodedAddress(
            TOWN_CENTRES["gospic"].lat,
            TOWN_CENTRES["gospic"].lon,
            "Gospić",
            "Gospić",
        ),
        ("gospic", "gospicu", "gospica", "53000"),
    ),
)


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.casefold())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.replace("đ", "d")


class MockGeocodingClient:
    def geocode_address(self, query: str) -> GeocodedAddress | None:
        q = _normalize(query).strip()
        if not q:
            return None
        # Exact settlement match first.
        for entry in SETTLEMENT_DIRECTORY:
            if q == _normalize(entry.address.settlement):
                return entry.address
        # Substring / token match in priority order.
        for entry in SETTLEMENT_DIRECTORY:
            if any(token in q for token in entry.tokens):
                return entry.address
        return None

    def geocode(self, query: str) -> LatLon | None:
        resolved = self.geocode_address(query)
        return resolved.point if resolved is not None else None
