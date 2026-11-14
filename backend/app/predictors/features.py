"""Graditelj značajki za treniranje i posluživanje prediktora (E4-T3, KAN-30).

Jedan modul pretvara retke `Patient`, `VisitRequest`, `Slot`, `Facility`, `Vehicle`
(pri posluživanju) te `TripLog` (pri treniranju) u kanonske rječnike značajki.
Nikad ne uključuje osobne identifikatore (MBO, ime, prezime, telefon, adresu).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.adapters import get_routing_client
from app.adapters.routing import RoutingClient
from app.adapters.types import LatLon
from app.codebooks import time_of_day_for_hour, time_of_day_keys
from app.models import (
    Facility,
    Patient,
    Slot,
    TripLog,
    Vehicle,
    VisitRequest,
    VisitType,
)
from app.predictors.base import MissingFeatureError, PredictorInputError
from app.scoring import _patient_age, road_distance_km

ZAGREB_TZ = ZoneInfo("Europe/Zagreb")

PII_FORBIDDEN_KEYS = frozenset(
    {"mbo", "first_name", "last_name", "name", "phone", "address", "driver_phone", "driver_name"}
)


def age_group_for_age(age: int | None) -> str:
    """Dobna skupina usklađena s pojasevima u `scoring_factors.yaml`."""
    if age is None or age < 0:
        return "unknown"
    if age < 65:
        return "under_65"
    if age < 75:
        return "65_74"
    if age < 85:
        return "75_84"
    return "85_plus"


def _local_datetime(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=ZAGREB_TZ)
    return dt.astimezone(ZAGREB_TZ)


def _compose_visit_duration_dict(
    *,
    department: str | None,
    visit_type: str | None,
    visit_dt: datetime | None,
    fallback_date: date | None,
    preferred_time_of_day: str | None,
    patient_age: int | None,
) -> dict[str, Any]:
    if not department or not isinstance(department, str) or not department.strip():
        raise MissingFeatureError("Nedostaje obvezna značajka 'department' (djelatnost ustanove).")
    if not visit_type or not isinstance(visit_type, str) or not visit_type.strip():
        raise MissingFeatureError("Nedostaje obvezna značajka 'visit_type' (vrsta pregleda).")

    dept_clean = department.strip()
    vtype_clean = visit_type.strip()

    local_dt = _local_datetime(visit_dt)
    hour_of_day: int | None = local_dt.hour if local_dt is not None else None
    time_of_day: str | None = None
    if hour_of_day is not None:
        time_of_day = time_of_day_for_hour(hour_of_day)
    elif preferred_time_of_day and preferred_time_of_day in time_of_day_keys():
        time_of_day = preferred_time_of_day

    day_of_week: int | None = None
    if local_dt is not None:
        day_of_week = local_dt.weekday()
    elif fallback_date is not None:
        day_of_week = fallback_date.weekday()

    return {
        "department": dept_clean,
        "visit_type": vtype_clean,
        "is_first_visit": vtype_clean == VisitType.FIRST_VISIT.value,
        "is_follow_up": vtype_clean == VisitType.FOLLOW_UP.value,
        "time_of_day": time_of_day,
        "hour_of_day": hour_of_day,
        "day_of_week": day_of_week,
        "patient_age": patient_age,
        "age_over_75": patient_age is not None and patient_age >= 75,
        "age_group": age_group_for_age(patient_age),
    }


def build_visit_duration_features(
    request: VisitRequest,
    *,
    patient: Patient | None = None,
    slot: Slot | None = None,
    reference_date: date | None = None,
) -> dict[str, Any]:
    """Izgradi značajke za prediktor `visit_duration` iz zahtjeva, pacijenta i termina."""
    resolved_patient = patient if patient is not None else request.patient
    visit_dt = slot.start_time if slot is not None else None
    local_visit_dt = _local_datetime(visit_dt)

    ref = (
        reference_date
        or (local_visit_dt.date() if local_visit_dt is not None else None)
        or request.earliest_date
    )
    patient_age = (
        _patient_age(resolved_patient.birth_year, ref) if resolved_patient is not None else None
    )

    return _compose_visit_duration_dict(
        department=request.department,
        visit_type=request.visit_type,
        visit_dt=visit_dt,
        fallback_date=request.earliest_date,
        preferred_time_of_day=request.preferred_time_of_day,
        patient_age=patient_age,
    )


def visit_duration_from_trip_log(trip_log: TripLog) -> tuple[dict[str, Any], float]:
    """Izgradi `(features, actual_visit_minutes)` iz retka `TripLog` za treniranje modela."""
    if (
        trip_log.actual_check_in_at_facility is None
        or trip_log.actual_check_out_from_facility is None
    ):
        raise PredictorInputError("TripLog nema upisana vremena prijave i odjave u ustanovi.")

    duration_min = (
        trip_log.actual_check_out_from_facility - trip_log.actual_check_in_at_facility
    ).total_seconds() / 60.0
    if duration_min <= 0:
        raise PredictorInputError(
            f"Nevaljano trajanje pregleda u TripLogu: {duration_min:.2f} min."
        )

    assignment = trip_log.assignment
    req = assignment.request if assignment is not None else None
    pat = req.patient if req is not None else None
    slot = assignment.slot if assignment is not None else None

    department = trip_log.department or (req.department if req is not None else None)
    visit_type = trip_log.visit_type or (req.visit_type if req is not None else None)
    visit_dt = (
        slot.start_time
        if slot is not None and slot.start_time is not None
        else trip_log.actual_check_in_at_facility
    )

    patient_age = trip_log.patient_age
    if patient_age is None and pat is not None:
        local_checkin = _local_datetime(trip_log.actual_check_in_at_facility)
        ref_date = local_checkin.date() if local_checkin is not None else None
        patient_age = _patient_age(pat.birth_year, ref_date)

    features = _compose_visit_duration_dict(
        department=department,
        visit_type=visit_type,
        visit_dt=visit_dt,
        fallback_date=None,
        preferred_time_of_day=req.preferred_time_of_day if req is not None else None,
        patient_age=patient_age,
    )
    return features, round(duration_min, 2)


def _compose_service_time_dict(
    *,
    mobility_class: str | None,
    floor: int | None,
    elevator: bool | None,
    companion: bool | None,
) -> dict[str, Any]:
    if not mobility_class or not isinstance(mobility_class, str) or not mobility_class.strip():
        raise MissingFeatureError(
            "Nedostaje obvezna značajka 'mobility_class' (klasa pokretljivosti)."
        )

    resolved_floor = int(floor) if floor is not None else 0
    resolved_elevator = bool(elevator) if elevator is not None else False
    resolved_companion = bool(companion) if companion is not None else False
    stairs_floors = max(0, resolved_floor) if not resolved_elevator else 0

    return {
        "mobility_class": mobility_class.strip(),
        "floor": resolved_floor,
        "elevator": resolved_elevator,
        "stairs_floors": stairs_floors,
        "companion": resolved_companion,
    }


def build_service_time_features(patient: Patient) -> dict[str, Any]:
    """Izgradi značajke za prediktor `service_time` (vrijeme ukrcaja) iz retka `Patient`."""
    return _compose_service_time_dict(
        mobility_class=patient.mobility_class,
        floor=patient.floor,
        elevator=patient.elevator,
        companion=patient.companion,
    )


def service_time_from_trip_log(trip_log: TripLog) -> tuple[dict[str, Any], float]:
    """Izgradi `(features, actual_boarding_minutes)` iz retka `TripLog` za treniranje modela."""
    if trip_log.actual_arrival_at_door is None or trip_log.actual_departure_from_door is None:
        raise PredictorInputError("TripLog nema upisana vremena dolaska pred vrata i polaska.")

    boarding_min = (
        trip_log.actual_departure_from_door - trip_log.actual_arrival_at_door
    ).total_seconds() / 60.0
    if boarding_min <= 0:
        raise PredictorInputError(f"Nevaljano vrijeme ukrcaja u TripLogu: {boarding_min:.2f} min.")

    assignment = trip_log.assignment
    req = assignment.request if assignment is not None else None
    pat = req.patient if req is not None else None

    mobility_class = trip_log.mobility_class or (pat.mobility_class if pat is not None else None)
    floor = trip_log.floor if trip_log.floor is not None else (pat.floor if pat else 0)
    elevator = (
        trip_log.elevator if trip_log.elevator is not None else (pat.elevator if pat else False)
    )
    companion = (
        trip_log.companion if trip_log.companion is not None else (pat.companion if pat else False)
    )

    features = _compose_service_time_dict(
        mobility_class=mobility_class,
        floor=floor,
        elevator=elevator,
        companion=companion,
    )
    return features, round(boarding_min, 2)


def build_support_need_features(
    patient: Patient,
    *,
    request: VisitRequest | None = None,
    facility: Facility | None = None,
    distance_km: float | None = None,
    routing_client: RoutingClient | None = None,
    reference_date: date | None = None,
) -> dict[str, Any]:
    """Izgradi značajke za prediktor `support_need` iz retka `Patient` i opcionalnog zahtjeva."""
    if not patient.mobility_class or not patient.mobility_class.strip():
        raise MissingFeatureError(
            "Nedostaje obvezna značajka 'mobility_class' (klasa pokretljivosti)."
        )
    if not patient.phone_type or not patient.phone_type.strip():
        raise MissingFeatureError("Nedostaje obvezna značajka 'phone_type' (vrsta telefona).")

    target_facility = facility or (request.facility if request is not None else None)
    resolved_distance = distance_km
    if resolved_distance is None and target_facility is not None:
        client = routing_client if routing_client is not None else get_routing_client()
        resolved_distance = road_distance_km(patient, target_facility, client)

    ref = reference_date or datetime.now(ZAGREB_TZ).date()
    age = _patient_age(patient.birth_year, ref)

    return {
        "patient_id": patient.id if patient.id is not None else 0,
        "mobility_class": patient.mobility_class.strip(),
        "distance_km": resolved_distance,
        "birth_year": patient.birth_year,
        "age": age,
        "lives_alone": bool(patient.lives_alone),
        "missed_visits_last_year": (
            int(patient.missed_visits_last_year)
            if patient.missed_visits_last_year is not None
            else 0
        ),
        "phone_type": patient.phone_type.strip(),
        "companion_available": bool(patient.companion),
        "reference_date": ref.isoformat(),
    }


def _extract_point_dict(entity: Any, label: str) -> dict[str, float]:
    if entity is None:
        raise MissingFeatureError(f"Nedostaje obvezna lokacija '{label}'.")

    lat: float | None = None
    lon: float | None = None
    if isinstance(entity, dict):
        if "lat" in entity and "lon" in entity:
            lat = float(entity["lat"]) if entity["lat"] is not None else None
            lon = float(entity["lon"]) if entity["lon"] is not None else None
    elif isinstance(entity, LatLon):
        lat = float(entity.lat)
        lon = float(entity.lon)
    elif hasattr(entity, "latitude") and hasattr(entity, "longitude"):
        lat = entity.latitude
        lon = entity.longitude
    elif hasattr(entity, "lat") and hasattr(entity, "lon"):
        lat = float(entity.lat) if entity.lat is not None else None
        lon = float(entity.lon) if entity.lon is not None else None

    if lat is None or lon is None:
        raise MissingFeatureError(f"Lokacija '{label}' nema definirane koordinate (lat, lon).")
    return {"lat": float(lat), "lon": float(lon)}


def build_travel_time_features(
    origin: Patient | Facility | Vehicle | LatLon | dict[str, float] | Any,
    destination: Facility | Patient | Vehicle | LatLon | dict[str, float] | Any,
    *,
    departure_time: datetime | None = None,
    vehicle: Vehicle | None = None,
) -> dict[str, Any]:
    """Izgradi značajke za prediktor `travel_time` iz polazišta, odredišta i opcionalnog vozila."""
    from_point = _extract_point_dict(origin, "from")
    to_point = _extract_point_dict(destination, "to")
    local_dt = _local_datetime(departure_time)

    return {
        "from": from_point,
        "to": to_point,
        "hour_of_day": local_dt.hour if local_dt is not None else None,
        "day_of_week": local_dt.weekday() if local_dt is not None else None,
        "vehicle_provider_type": vehicle.provider_type if vehicle is not None else None,
    }


def build_features(
    slot: str,
    *,
    patient: Patient | None = None,
    request: VisitRequest | None = None,
    slot_obj: Slot | None = None,
    facility: Facility | None = None,
    vehicle: Vehicle | None = None,
    origin: Any | None = None,
    destination: Any | None = None,
    distance_km: float | None = None,
    departure_time: datetime | None = None,
    reference_date: date | None = None,
) -> dict[str, Any]:
    """Jedinstveni ulaz graditelja značajki po mjestu u registru (`slot`)."""
    if slot == "visit_duration":
        if request is None:
            raise MissingFeatureError(
                "Za mjesto 'visit_duration' potreban je objekt 'request' (VisitRequest)."
            )
        return build_visit_duration_features(
            request,
            patient=patient,
            slot=slot_obj,
            reference_date=reference_date,
        )

    if slot == "service_time":
        target_patient = patient or (request.patient if request is not None else None)
        if target_patient is None:
            raise MissingFeatureError(
                "Za mjesto 'service_time' potreban je objekt 'patient' (Patient)."
            )
        return build_service_time_features(target_patient)

    if slot == "support_need":
        target_patient = patient or (request.patient if request is not None else None)
        if target_patient is None:
            raise MissingFeatureError(
                "Za mjesto 'support_need' potreban je objekt 'patient' (Patient)."
            )
        return build_support_need_features(
            target_patient,
            request=request,
            facility=facility,
            distance_km=distance_km,
            reference_date=reference_date,
        )

    if slot == "travel_time":
        orig = origin if origin is not None else (patient or vehicle)
        dest = (
            destination
            if destination is not None
            else (facility or (request.facility if request is not None else None))
        )
        return build_travel_time_features(
            orig,
            dest,
            departure_time=departure_time,
            vehicle=vehicle,
        )

    raise KeyError(f"Nepoznato ili nepodržano mjesto za gradnju značajki: '{slot}'.")
