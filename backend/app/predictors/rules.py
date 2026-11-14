"""Zadana pravila prediktora (E4-T1, KAN-28 i E4-T2, KAN-29).

Pravila omataju postojeće šifrarnike (`app.codebooks`), bodovanje (`app.scoring`)
i adapter za rute (`app.adapters.routing`) u zajedničko sučelje `Predictor`.
Brojke iz YAML datoteka nikad se ne kopiraju u kod.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.adapters import get_routing_client
from app.adapters.routing import RoutingClient
from app.adapters.types import AdapterError, LatLon
from app.codebooks import (
    CodebookError,
    get_boarding_time_min,
    get_visit_duration,
)
from app.predictors.base import (
    MissingFeatureError,
    Prediction,
    PredictorExecutionError,
    PredictorInputError,
)
from app.scoring import ScoringConfig, compute_score

ZAGREB_TZ = ZoneInfo("Europe/Zagreb")


class VisitDurationRule:
    """Pravilo trajanja pregleda po djelatnosti i vrsti pregleda (mjesto `visit_duration`)."""

    name: str = "visit_duration_rule"
    version: str = "1.0"

    def predict(self, features: dict[str, Any]) -> Prediction:
        department = features.get("department")
        if department is None or not isinstance(department, str) or not department.strip():
            raise MissingFeatureError(
                "Nedostaje obvezna značajka 'department' (djelatnost ustanove)."
            )
        visit_type = features.get("visit_type")
        if visit_type is None or not isinstance(visit_type, str) or not visit_type.strip():
            raise MissingFeatureError("Nedostaje obvezna značajka 'visit_type' (vrsta pregleda).")

        try:
            entry = get_visit_duration(department.strip(), visit_type.strip())
        except CodebookError as exc:
            raise PredictorInputError(
                f"Nepoznata ili nepodržana kombinacija djelatnosti i vrste pregleda: "
                f"'{department}' / '{visit_type}'."
            ) from exc

        median = float(entry.median_min)
        p90 = float(entry.p90_min)
        return Prediction(
            value=median,
            low=None,
            high=p90,
            explanation={"median_min": median, "p90_min": p90},
            source="rules",
        )


class ServiceTimeRule:
    """Pravilo vremena ukrcaja po klasi pokretljivosti (mjesto `service_time`)."""

    name: str = "service_time_rule"
    version: str = "1.0"

    def predict(self, features: dict[str, Any]) -> Prediction:
        mobility_class = features.get("mobility_class")
        if (
            mobility_class is None
            or not isinstance(mobility_class, str)
            or not mobility_class.strip()
        ):
            raise MissingFeatureError(
                "Nedostaje obvezna značajka 'mobility_class' (klasa pokretljivosti)."
            )

        try:
            minutes = float(get_boarding_time_min(mobility_class.strip()))
        except CodebookError as exc:
            raise PredictorInputError(
                f"Nepoznata klasa pokretljivosti u šifrarniku: '{mobility_class}'."
            ) from exc

        return Prediction(
            value=minutes,
            low=None,
            high=None,
            explanation={"mobility_class_min": minutes},
            source="rules",
        )


def _extract_lat_lon(raw: Any, key_name: str) -> LatLon:
    if raw is None:
        raise MissingFeatureError(
            f"Nedostaje obvezna značajka '{key_name}' s koordinatama (lat, lon)."
        )
    if isinstance(raw, LatLon):
        lat_raw: Any = raw.lat
        lon_raw: Any = raw.lon
    elif isinstance(raw, dict):
        if "lat" not in raw or "lon" not in raw:
            raise MissingFeatureError(
                f"Značajka '{key_name}' mora sadržavati ključeve 'lat' i 'lon'."
            )
        lat_raw = raw["lat"]
        lon_raw = raw["lon"]
    elif hasattr(raw, "lat") and hasattr(raw, "lon"):
        lat_raw = raw.lat
        lon_raw = raw.lon
    else:
        raise PredictorInputError(
            f"Značajka '{key_name}' mora biti rječnik s koordinatama 'lat' i 'lon'."
        )

    if (
        isinstance(lat_raw, bool)
        or isinstance(lon_raw, bool)
        or not isinstance(lat_raw, int | float)
        or not isinstance(lon_raw, int | float)
    ):
        raise PredictorInputError(f"Koordinate u značajci '{key_name}' moraju biti brojevi.")

    lat = float(lat_raw)
    lon = float(lon_raw)
    if not (math.isfinite(lat) and math.isfinite(lon)):
        raise PredictorInputError(
            f"Koordinate u značajci '{key_name}' moraju biti konačni brojevi."
        )
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise PredictorInputError(
            f"Koordinate u značajci '{key_name}' su izvan dopuštenog raspona WGS84."
        )
    return LatLon(lat=lat, lon=lon)


class TravelTimeRule:
    """Pravilo vremena vožnje preko adaptera za rute (mjesto `travel_time`)."""

    name: str = "travel_time_rule"
    version: str = "1.0"

    def __init__(self, routing_client: RoutingClient | None = None) -> None:
        self._routing_client = routing_client

    def predict(self, features: dict[str, Any]) -> Prediction:
        if "from" not in features:
            raise MissingFeatureError("Nedostaje obvezna značajka 'from' (polazišne koordinate).")
        if "to" not in features:
            raise MissingFeatureError("Nedostaje obvezna značajka 'to' (odredišne koordinate).")

        origin = _extract_lat_lon(features["from"], "from")
        destination = _extract_lat_lon(features["to"], "to")

        client = self._routing_client if self._routing_client is not None else get_routing_client()
        try:
            matrix = client.matrix([origin, destination])
            duration_s = float(matrix.durations_s[0][1])
        except (AdapterError, IndexError, TypeError, ValueError) as exc:
            raise PredictorExecutionError(
                f"Izračun vremena vožnje preko adaptera za rute nije uspio: {exc}"
            ) from exc

        if not math.isfinite(duration_s) or duration_s < 0.0:
            raise PredictorExecutionError("Adapter za rute vratio je nevaljano vrijeme vožnje.")

        minutes = duration_s / 60.0
        return Prediction(
            value=minutes,
            low=None,
            high=None,
            explanation={"travel_time_min": minutes},
            source="rules",
        )


class SupportNeedRule:
    """Pravilo potrebe za podrškom koje omata `compute_score()` (mjesto `support_need`)."""

    name: str = "support_need_rule"
    version: str = "1.0"

    def __init__(self, config: ScoringConfig | None = None) -> None:
        self._config = config

    def predict(self, features: dict[str, Any]) -> Prediction:
        if "mobility_class" not in features or features["mobility_class"] is None:
            raise MissingFeatureError(
                "Nedostaje obvezna značajka 'mobility_class' (klasa pokretljivosti)."
            )
        if "lives_alone" not in features or not isinstance(features["lives_alone"], bool):
            raise MissingFeatureError(
                "Nedostaje obvezna logička značajka 'lives_alone' (živi sam)."
            )
        if (
            "missed_visits_last_year" not in features
            or isinstance(features["missed_visits_last_year"], bool)
            or not isinstance(features["missed_visits_last_year"], int)
        ):
            raise MissingFeatureError(
                "Nedostaje obvezna cjelobrojna značajka 'missed_visits_last_year' "
                "(propušteni pregledi)."
            )
        if "phone_type" not in features or features["phone_type"] is None:
            raise MissingFeatureError("Nedostaje obvezna značajka 'phone_type' (vrsta telefona).")

        if "companion_available" in features:
            companion_val = features["companion_available"]
        elif "companion" in features:
            companion_val = features["companion"]
        else:
            raise MissingFeatureError(
                "Nedostaje obvezna logička značajka 'companion_available' (dostupnost pratnje)."
            )
        if not isinstance(companion_val, bool):
            raise MissingFeatureError(
                "Značajka 'companion_available' mora biti logička vrijednost (bool)."
            )

        patient_id_raw = features.get("patient_id", 0)
        patient_id = (
            int(patient_id_raw)
            if isinstance(patient_id_raw, int) and not isinstance(patient_id_raw, bool)
            else 0
        )

        distance_km = (
            features["distance_km"]
            if "distance_km" in features
            else features.get("distance_to_destination")
        )

        ref_date: date | None = None
        raw_ref = features.get("reference_date")
        if isinstance(raw_ref, datetime):
            ref_date = raw_ref.date()
        elif isinstance(raw_ref, date):
            ref_date = raw_ref
        elif isinstance(raw_ref, str):
            try:
                ref_date = date.fromisoformat(raw_ref)
            except ValueError as exc:
                raise PredictorInputError(
                    f"Neispravan format datuma 'reference_date': '{raw_ref}'."
                ) from exc

        birth_year: int | None = None
        if "birth_year" in features and features["birth_year"] is not None:
            by_raw = features["birth_year"]
            if isinstance(by_raw, bool) or not isinstance(by_raw, int):
                raise PredictorInputError("Značajka 'birth_year' mora biti cijeli broj.")
            birth_year = by_raw
        elif "age" in features and features["age"] is not None:
            age_raw = features["age"]
            if isinstance(age_raw, bool) or not isinstance(age_raw, int):
                raise PredictorInputError("Značajka 'age' mora biti cijeli broj.")
            effective_ref = ref_date or datetime.now(ZAGREB_TZ).date()
            birth_year = effective_ref.year - age_raw

        result = compute_score(
            patient_id=patient_id,
            mobility_class=str(features["mobility_class"]),
            distance_km=distance_km,
            birth_year=birth_year,
            lives_alone=features["lives_alone"],
            missed_visits_last_year=features["missed_visits_last_year"],
            phone_type=str(features["phone_type"]),
            companion_available=companion_val,
            config=self._config,
            reference_date=ref_date,
        )

        explanation = {fc.key: fc.weighted_value for fc in result.factors}
        return Prediction(
            value=result.total_score,
            low=None,
            high=result.total_score_upper,
            explanation=explanation,
            source="rules",
        )
