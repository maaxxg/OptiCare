"""Pravila HZZO-a za prijevoz na liječenje (E13-T4, E3-T2).

Učitava i validira pravila iz ``data/domain/hzzo_rules.yaml``.
Sve vrijednosti (pragovi, pojasevi, klase pokretljivosti, iznimke, cijene)
učitavaju se dinamički iz YAML-a bez hardkodiranja u Python kodu.
"""

from __future__ import annotations

import logging
import math
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters import get_routing_client
from app.adapters.routing import RoutingClient
from app.config import get_settings
from app.db import get_db
from app.distances import road_distance_km
from app.models import Facility, MobilityClass, Patient, Slot, VisitRequest, VisitType

HZZO_RULES_RELATIVE_PATH = Path("domain") / "hzzo_rules.yaml"

logger = logging.getLogger(__name__)

ZAGREB = ZoneInfo("Europe/Zagreb")

router = APIRouter(tags=["entitlement"])


class HZZORulesError(Exception):
    """Pravila HZZO-a ne mogu se pročitati ili nisu valjana."""


class SanitetskiIssuedByEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    who: str
    when: str


class SanitetskiRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    legal_criteria: list[str]
    by_mobility_class: dict[str, str]
    issued_by: list[SanitetskiIssuedByEntry]


class DistanceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    official_source: str
    system_source: str
    borderline_band_km: list[float]
    on_borderline: str
    on_unknown: str

    @model_validator(mode="after")
    def _check_borderline_band(self) -> DistanceConfig:
        if len(self.borderline_band_km) != 2:
            raise ValueError("borderline_band_km must contain exactly two numbers [min, max]")
        if self.borderline_band_km[0] >= self.borderline_band_km[1]:
            raise ValueError("borderline_band_km min must be strictly less than max")
        return self


class PlaceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    separate_if_km_from_town: float


class NearestProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule: str
    manual_overrides: list[str]


class DistanceException(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    system_check: str


class CompensationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rate: str
    approx_eur_per_km: float
    round_trip: bool


class TravelOrderRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conditions: list[str]
    min_distance_km: float
    distance: DistanceConfig
    place: PlaceConfig
    nearest_provider: NearestProviderConfig
    distance_exceptions: list[DistanceException]
    compensation: CompensationConfig
    issued_by: list[str]


class SourceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    url: str
    note: str | None = None


class HZZORules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sanitetski: SanitetskiRules
    travel_order: TravelOrderRules
    sources: list[SourceEntry]


def load_hzzo_rules_from_path(yaml_path: Path | None = None) -> HZZORules:
    path = yaml_path or (get_settings().data_dir / HZZO_RULES_RELATIVE_PATH)
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        logger.error("HZZO rules YAML cannot be read: %s (check DATA_DIR)", path)
        raise HZZORulesError(f"Cannot read HZZO rules YAML at {path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise HZZORulesError(f"HZZO rules YAML at {path} must be a mapping")
    try:
        return HZZORules.model_validate(loaded)
    except ValidationError as exc:
        raise HZZORulesError(f"Invalid HZZO rules YAML at {path}: {exc}") from exc


load_hzzo_rules = load_hzzo_rules_from_path


@lru_cache
def get_hzzo_rules() -> HZZORules:
    return load_hzzo_rules_from_path()


class EntitlementFlag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    text: str


class TravelOrderData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_name: str | None = None
    address: str | None = None
    facility_name: str | None = None
    department: str | None = None
    appointment_date: date | None = None
    distance_km_one_way: float | None = None
    distance_km_round_trip: float | None = None
    estimated_compensation_eur: float | None = None
    issued_by: list[str] = Field(default_factory=list)


class EntitlementProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal: Literal["sanitetski", "travel_order", "none"]
    flags: list[EntitlementFlag] = Field(default_factory=list)
    distance_km: float | None = None
    exceptions_applied: list[str] = Field(default_factory=list)
    order_data: TravelOrderData | None = None


def propose_entitlement(
    *,
    mobility_class: str | MobilityClass,
    birth_year: int | None,
    visit_type: str | VisitType | None,
    distance_km: float | None,
    is_nearest_facility: bool = True,
    reference_date: date | None = None,
    patient_name: str | None = None,
    address: str | None = None,
    facility_name: str | None = None,
    department: str | None = None,
    appointment_date: date | None = None,
    rules: HZZORules | None = None,
    **extra: Any,
) -> EntitlementProposal:
    """Predloži pravo na prijevoz (sanitetski, putni nalog ili ništa).

    Čista funkcija bez ovisnosti o bazi podataka ili mreži. Svi pragovi, pojasevi
    i iznosi čitaju se dinamički iz HZZO pravila.
    """
    cfg = rules or get_hzzo_rules()
    flags: list[EntitlementFlag] = []
    exceptions_applied: list[str] = []

    p_name = patient_name or extra.get("name")
    p_addr = address or extra.get("patient_address")
    f_name = facility_name or extra.get("facility")
    dept = department or extra.get("department_name")
    appt_date = appointment_date or extra.get("date")

    # 1. Klasa pokretljivosti (sanitetski.by_mobility_class)
    m_key = ""
    if mobility_class is not None:
        m_key = (
            mobility_class.value.lower()
            if isinstance(mobility_class, MobilityClass)
            else str(mobility_class).lower()
        )
    sanitetski_status = cfg.sanitetski.by_mobility_class.get(m_key, "doctor_judgement")

    if sanitetski_status == "candidate":
        return EntitlementProposal(
            proposal="sanitetski",
            flags=flags,
            distance_km=distance_km,
            exceptions_applied=[],
            order_data=None,
        )

    if sanitetski_status == "doctor_judgement":
        flags.append(
            EntitlementFlag(
                code="doctor_judgement",
                text=(
                    "Pacijent koristi pomagalo pri kretanju (procjena liječnika). Provjeriti "
                    "s izabranim liječnikom ima li pacijent pravo na sanitetski prijevoz "
                    "zbog prirode bolesti ili otežanog kretanja."
                ),
            )
        )

    # 2. Iznimke od praga udaljenosti
    under_18_exc = next(
        (e for e in cfg.travel_order.distance_exceptions if e.system_check == "birth_year"),
        None,
    )
    if under_18_exc is not None and birth_year is not None and not isinstance(birth_year, bool):
        digits = "".join(c for c in under_18_exc.key if c.isdigit())
        age_limit = int(digits) if digits else 18
        ref = reference_date or datetime.now(ZAGREB).date()
        age = ref.year - birth_year
        if 0 <= age < age_limit:
            exceptions_applied.append(under_18_exc.key)

    v_str = ""
    if visit_type is not None:
        v_str = (
            visit_type.value.lower()
            if isinstance(visit_type, VisitType)
            else str(visit_type).lower()
        )
    for exc in cfg.travel_order.distance_exceptions:
        if exc.key == "hemodialysis" and v_str in ("dialysis_session", "hemodialysis"):
            if exc.key not in exceptions_applied:
                exceptions_applied.append(exc.key)
        elif exc.key == "radiotherapy_chemotherapy" and v_str in (
            "chemotherapy",
            "radiotherapy",
            "radiotherapy_chemotherapy",
        ):
            if exc.key not in exceptions_applied:
                exceptions_applied.append(exc.key)

    # 3. Udaljenost
    proposal: Literal["sanitetski", "travel_order", "none"]
    band_min, band_max = cfg.travel_order.distance.borderline_band_km
    min_dist = cfg.travel_order.min_distance_km

    valid_distance = distance_km is not None and math.isfinite(distance_km) and distance_km >= 0

    if not valid_distance:
        flags.append(
            EntitlementFlag(
                code="distance_unknown",
                text=(
                    "Udaljenost do ustanove nije poznata. Prema pravilima HZZO-a bez točne "
                    "udaljenosti ne može se predložiti putni nalog; potrebno je provjeriti "
                    "adresu pacijenta i ugovorne ustanove."
                ),
            )
        )
        proposal = "none"
    else:
        assert distance_km is not None
        if band_min <= distance_km <= band_max:
            flags.append(
                EntitlementFlag(
                    code="distance_borderline",
                    text=(
                        f"Cestovna udaljenost ({distance_km:.1f} km) nalazi se u rubnom pojasu "
                        f"({band_min:.0f}–{band_max:.0f} km). Provjeriti točnu relaciju na "
                        "interaktivnoj karti HAK-a."
                    ),
                )
            )

        if distance_km >= min_dist or bool(exceptions_applied):
            proposal = "travel_order"
        else:
            proposal = "none"

    # 4. Najbliža ustanova
    if not is_nearest_facility:
        manual_labels = ", ".join(
            e.label for e in cfg.travel_order.distance_exceptions if e.system_check == "manual_flag"
        )
        flags.append(
            EntitlementFlag(
                code="not_nearest_facility",
                text=(
                    "Ciljana ustanova nije najbliži ugovorni subjekt s traženom djelatnošću. "
                    "Putni nalog se ne predlaže osim ako liječnik utvrdi ili sestra ručno potvrdi "
                    f"opravdani razlog ili iznimku (npr. {manual_labels}, kraća lista čekanja "
                    "ili nemogućnost pružanja skrbi u roku u bližoj ustanovi)."
                ),
            )
        )
        proposal = "none"

    order_data: TravelOrderData | None = None
    if proposal == "travel_order" and valid_distance and distance_km is not None:
        round_trip = round(distance_km * 2, 2)
        rate = cfg.travel_order.compensation.approx_eur_per_km
        estimated_eur = round(rate * round_trip, 2)
        order_data = TravelOrderData(
            patient_name=p_name,
            address=p_addr,
            facility_name=f_name,
            department=dept,
            appointment_date=appt_date,
            distance_km_one_way=round(distance_km, 2),
            distance_km_round_trip=round_trip,
            estimated_compensation_eur=estimated_eur,
            issued_by=list(cfg.travel_order.issued_by),
        )

    return EntitlementProposal(
        proposal=proposal,
        flags=flags,
        distance_km=distance_km,
        exceptions_applied=exceptions_applied,
        order_data=order_data,
    )


@router.get("/entitlement/{request_id}", response_model=EntitlementProposal)
def get_entitlement_proposal(
    request_id: int,
    db: Annotated[Session, Depends(get_db)],
    routing_client: Annotated[RoutingClient, Depends(get_routing_client)],
) -> EntitlementProposal:
    """Predloži pravo na prijevoz za zadani zahtjev za pregled.

    Isključivo za čitanje/prijedlog: ne mijenja patient.transport_entitlement u bazi.
    Pronalazi najbližu ustanovu za traženu djelatnost sortiranjem u PostGIS-u
    pomoću ST_Distance te računa cestovnu udaljenost preko road_distance_km().
    """
    visit_request = db.get(VisitRequest, request_id)
    if visit_request is None:
        raise HTTPException(status_code=404, detail="Zahtjev nije pronađen.")

    patient = visit_request.patient or db.get(Patient, visit_request.patient_id)
    target_facility = visit_request.facility or db.get(Facility, visit_request.facility_id)
    if patient is None or target_facility is None:
        raise HTTPException(
            status_code=404, detail="Podaci o pacijentu ili ustanovi nisu pronađeni."
        )

    nearest_facility: Facility | None = None
    if patient.location is not None:
        try:
            stmt = (
                select(Facility)
                .join(Slot, Slot.facility_id == Facility.id)
                .where(Slot.department == visit_request.department)
                .order_by(func.ST_Distance(Facility.location, patient.location))
                .limit(1)
            )
            nearest_facility = db.scalars(stmt).first()
        except Exception:
            nearest_facility = None

    is_nearest_facility = nearest_facility is None or target_facility.id == nearest_facility.id

    target_distance_km = road_distance_km(patient, target_facility, routing_client)

    nearest_distance_km: float | None = None
    if nearest_facility is not None and not is_nearest_facility:
        nearest_distance_km = road_distance_km(patient, nearest_facility, routing_client)

    return propose_entitlement(
        mobility_class=patient.mobility_class,
        birth_year=patient.birth_year,
        visit_type=visit_request.visit_type,
        distance_km=target_distance_km,
        is_nearest_facility=is_nearest_facility,
        patient_name=patient.name,
        address=patient.address,
        facility_name=target_facility.name,
        department=visit_request.department,
        appointment_date=visit_request.earliest_date,
        nearest_facility_name=nearest_facility.name
        if (nearest_facility and not is_nearest_facility)
        else None,
        nearest_distance_km=nearest_distance_km,
    )
