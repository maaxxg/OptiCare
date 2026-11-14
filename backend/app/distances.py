"""Zajednički modul za izračun cestovnih udaljenosti i putnih matrica."""

from __future__ import annotations

import logging
import math

from app.adapters.routing import RoutingClient
from app.adapters.types import AdapterError, LatLon
from app.models import Facility, Patient

logger = logging.getLogger(__name__)


def road_distance_km(
    patient: Patient, facility: Facility | None, client: RoutingClient
) -> float | None:
    """Road distance in km from the patient's address to the facility via the routing adapter.

    Returns None (distance unknown, flagged for the nurse) when a location is missing, the
    adapter fails or it returns an unusable value. Never guesses a distance.
    """
    if facility is None:
        return None
    p_lat, p_lon = patient.latitude, patient.longitude
    f_lat, f_lon = facility.latitude, facility.longitude
    if p_lat is None or p_lon is None or f_lat is None or f_lon is None:
        return None
    try:
        matrix = client.matrix([LatLon(p_lat, p_lon), LatLon(f_lat, f_lon)])
        km = matrix.distances_m[0][1] / 1000
    except (AdapterError, IndexError, TypeError, ValueError):
        logger.warning("Routing failed for patient_id=%s", patient.id)
        return None
    if not math.isfinite(km) or km < 0:
        return None
    return km
