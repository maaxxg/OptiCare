"""Vehicle eligibility per request (E5-T5). Pure; returns vehicle ids only.

An empty result is valid: the solver reports the request as unserved with a reason.
Scores only narrow the choice to vehicles that give more help, never remove a request (rule 1).
The entitlement is read, never set (rule 8).
"""

from collections.abc import Iterable

from app.models import MobilityClass, TransportEntitlement, VehicleProviderType
from app.planner.problem import PVehicle

# Vehicles where a driver helps door to door; required for support_level "high".
DOOR_TO_DOOR_PROVIDERS = frozenset(
    {
        VehicleProviderType.SANITETSKI,
        VehicleProviderType.RED_CROSS,
        VehicleProviderType.MUNICIPAL,
        VehicleProviderType.VOLUNTEER,
        VehicleProviderType.TAXI,
    }
)


def needs_sanitetski_order(
    mobility_class: MobilityClass | str, transport_entitlement: TransportEntitlement | str
) -> bool:
    """Immobile patient without the sanitetski entitlement (reason SANITETSKI_ORDER_NEEDED)."""
    return (
        MobilityClass(mobility_class) in (MobilityClass.WHEELCHAIR, MobilityClass.STRETCHER)
        and TransportEntitlement(transport_entitlement) != TransportEntitlement.SANITETSKI
    )


def _fits(vehicle: PVehicle, mobility_class: MobilityClass, companion: bool) -> bool:
    if mobility_class == MobilityClass.WHEELCHAIR:
        fits = vehicle.wheelchair_spots >= 1
    elif mobility_class == MobilityClass.STRETCHER:
        fits = vehicle.stretcher_spots >= 1
    else:
        fits = vehicle.seats >= 1
    return fits and (not companion or vehicle.seats >= 1)


def allowed_vehicles(
    *,
    mobility_class: MobilityClass | str,
    transport_entitlement: TransportEntitlement | str,
    support_level: str,
    companion: bool,
    vehicles: Iterable[PVehicle],
) -> frozenset[int]:
    mobility = MobilityClass(mobility_class)
    entitlement = TransportEntitlement(transport_entitlement)
    allowed: set[int] = set()
    for v in vehicles:
        ptype = v.provider_type
        # Carpool (patient_driver) is added in E5-T7.
        if ptype == VehicleProviderType.PATIENT_DRIVER:
            continue
        # Rule 7: sanitetski vehicles only for entitled patients, and they only take them.
        if (entitlement == TransportEntitlement.SANITETSKI) != (
            ptype == VehicleProviderType.SANITETSKI
        ):
            continue
        if support_level == "high" and ptype not in DOOR_TO_DOOR_PROVIDERS:
            continue
        if _fits(v, mobility, companion):
            allowed.add(v.id)
    return frozenset(allowed)
