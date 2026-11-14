import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta
from enum import Enum
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Response, status
from sqlalchemy import Connection, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.adapters import get_geocoding_client, get_routing_client
from app.adapters.geocoding import GeocodingClient, _normalize
from app.adapters.llm import LLMClient
from app.codebooks import Codebooks, get_codebooks, get_urgency_max_shift_days
from app.config import get_settings
from app.db import get_db
from app.intake import extract_intake, get_intake_llm_client
from app.models import (
    Facility,
    Patient,
    Slot,
    VisitRequest,
    make_point_wkt,
)
from app.schemas import (
    FacilityRead,
    GeocodeRequest,
    GeocodeResponse,
    GeoPoint,
    IntakeExtractRequest,
    IntakeExtractResponse,
    PatientCreate,
    PatientLookup,
    PatientRead,
    VisitRequestCreate,
    VisitRequestRead,
)
from app.scoring import (
    ScoringConfigError,
    ScoringResult,
    compute_score,
    get_scoring_config,
    road_distance_km,
)

logger = logging.getLogger("uvicorn.error")
ZAGREB_TZ = ZoneInfo("Europe/Zagreb")

DbSession = Annotated[Session, Depends(get_db)]
LlmDep = Annotated[LLMClient, Depends(get_intake_llm_client)]
GeoDep = Annotated[GeocodingClient, Depends(get_geocoding_client)]


def _name_key(name: str) -> str:
    return _normalize(name).strip()


class StartupCheckError(RuntimeError):
    pass


def check_postgis(conn: Connection) -> str:
    """Return the PostGIS version or raise StartupCheckError with a clear message."""
    try:
        version = conn.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'postgis'")
        ).scalar_one_or_none()
    except SQLAlchemyError as exc:
        raise StartupCheckError(
            f"Database query failed during PostGIS check: {type(exc).__name__}"
        ) from None
    if version is None:
        raise StartupCheckError(
            "PostGIS extension is missing in the database (run CREATE EXTENSION postgis)"
        )
    return str(version)


def check_routing_config() -> None:
    """Fail startup on a misconfigured routing adapter (no DB, no network)."""
    try:
        get_routing_client()
    except (ValueError, NotImplementedError) as exc:
        raise StartupCheckError(f"Routing adapter is misconfigured: {exc}") from exc


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        get_scoring_config()
    except ScoringConfigError as exc:
        raise StartupCheckError(f"Scoring configuration is invalid: {exc}") from exc
    check_routing_config()
    if get_settings().check_db_on_startup:
        from app.db import engine

        try:
            with engine.connect() as conn:
                version = check_postgis(conn)
        except StartupCheckError:
            raise
        except SQLAlchemyError as exc:
            # Do not include the exception text: it can contain the connection URL.
            raise StartupCheckError(
                f"Database is unreachable ({type(exc).__name__}); "
                "check DATABASE_URL and that the db service is up"
            ) from None
        logger.info("PostGIS %s detected", version)
    yield


app = FastAPI(title="OptiCare", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/codebooks", response_model=Codebooks)
def read_codebooks() -> Codebooks:
    return get_codebooks()


@app.post("/intake/geocode", response_model=GeocodeResponse)
def geocode_intake_address(
    payload: GeocodeRequest,
    geocoding_client: GeoDep,
) -> GeocodeResponse:
    query = f"{payload.address}, {payload.settlement}" if payload.settlement else payload.address
    resolved = geocoding_client.geocode_address(query)
    if resolved is None and payload.settlement:
        resolved = geocoding_client.geocode_address(payload.settlement)
    if resolved is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Adresa ili naselje nije prepoznato u tablici naselja.",
        )
    return GeocodeResponse(
        location=GeoPoint(lat=resolved.lat, lon=resolved.lon),
        settlement=resolved.settlement,
        municipality=resolved.municipality,
        county=resolved.county,
    )


@app.post("/intake/extract", response_model=IntakeExtractResponse)
def extract_intake_endpoint(
    payload: IntakeExtractRequest,
    llm_client: LlmDep,
    geocoding_client: GeoDep,
) -> IntakeExtractResponse:
    return extract_intake(
        text=payload.text,
        llm_client=llm_client,
        geocoding_client=geocoding_client,
    )


@app.get("/facilities", response_model=list[FacilityRead])
def list_facilities(db: DbSession) -> list[Facility]:
    return list(db.scalars(select(Facility).order_by(Facility.id)).all())


@app.get("/patients", response_model=list[PatientRead])
def list_patients(db: DbSession) -> list[Patient]:
    return list(db.scalars(select(Patient).order_by(Patient.id)).all())


@app.post("/patients/lookup", response_model=list[PatientRead])
def lookup_patient(payload: PatientLookup, db: DbSession) -> list[Patient]:
    # MBO only in the body, never in a URL (access logs, proxies). Do not log the payload.
    return list(db.scalars(select(Patient).where(Patient.mbo == payload.mbo)).all())


@app.post(
    "/patients",
    response_model=PatientRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"description": "Existing patient (same MBO) updated; only sent fields change."},
        409: {"description": "MBO belongs to a patient with a different name; nothing changed."},
    },
)
def create_or_update_patient(
    payload: PatientCreate,
    response: Response,
    db: DbSession,
    geocoding_client: GeoDep,
) -> Patient:
    """Create a patient (201) or update the one with the same MBO (200).

    On update only the fields present in the request body change. If the MBO belongs to a
    patient with a different name, nothing is written and 409 is returned.
    """
    existing = db.scalars(select(Patient).where(Patient.mbo == payload.mbo)).first()
    if existing is not None and (
        _name_key(existing.first_name) != _name_key(payload.first_name)
        or _name_key(existing.last_name) != _name_key(payload.last_name)
    ):
        # Neither the MBO nor the stored name may appear in the message.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=(
                "Pacijent s ovim MBO-om već postoji pod drugim imenom. "
                "Provjerite MBO i ime pacijenta."
            ),
        )

    sent = payload.model_fields_set
    geo_point = payload.location
    settlement = payload.settlement
    municipality = payload.municipality
    county = payload.county

    if geo_point is None:
        query = f"{payload.address}, {settlement}" if payload.address else settlement
        resolved = geocoding_client.geocode_address(query) or geocoding_client.geocode_address(
            settlement
        )
        if resolved is not None:
            geo_point = GeoPoint(lat=resolved.lat, lon=resolved.lon)
            settlement = resolved.settlement
            municipality = resolved.municipality
            county = resolved.county

    location_wkt = make_point_wkt(geo_point.lat, geo_point.lon) if geo_point is not None else None

    if existing is not None:
        for field in sent - {"mbo", "location", "settlement", "municipality", "county"}:
            value = getattr(payload, field)
            setattr(existing, field, value.value if isinstance(value, Enum) else value)
        # Location group: required in the schema, so the client always sent these three;
        # geocoding (when it succeeded) refined them, otherwise the client's values stand.
        existing.settlement = settlement
        existing.municipality = municipality
        existing.county = county
        if location_wkt is not None:
            existing.location = location_wkt
        db.commit()
        db.refresh(existing)
        response.status_code = status.HTTP_200_OK
        return existing

    patient = Patient(
        key=payload.key,
        first_name=payload.first_name,
        last_name=payload.last_name,
        birth_year=payload.birth_year,
        mbo=payload.mbo,
        phone=payload.phone,
        phone_type=payload.phone_type.value,
        address=payload.address,
        settlement=settlement,
        municipality=municipality,
        county=county,
        location=location_wkt,
        mobility_class=payload.mobility_class.value,
        lives_alone=payload.lives_alone,
        companion=payload.companion,
        floor=payload.floor,
        elevator=payload.elevator,
        transport_entitlement=payload.transport_entitlement.value,
        social_order_today=payload.social_order_today,
        own_car=payload.own_car,
        carpool_driver_seats=payload.carpool_driver_seats,
        carpool_rider_consent=payload.carpool_rider_consent,
        driver_documents_confirmed=payload.driver_documents_confirmed,
        missed_visits_last_year=payload.missed_visits_last_year,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def _matches_time_of_day(dt: datetime, preferred: str | None) -> bool:
    if not preferred:
        return True
    hour = dt.astimezone(ZAGREB_TZ).hour
    if preferred == "morning":
        return hour < 12
    if preferred == "afternoon":
        return hour >= 12
    return True


def _open_slots_in_range(
    db: Session,
    facility_id: int,
    department: str,
    earliest_date: date,
    latest_date: date,
    slot_ids: list[int] | None = None,
) -> list[Slot]:
    """Slots of the facility+department between the dates (Europe/Zagreb, inclusive) with room."""
    start = datetime.combine(earliest_date, time.min, tzinfo=ZAGREB_TZ)
    end = datetime.combine(latest_date + timedelta(days=1), time.min, tzinfo=ZAGREB_TZ)
    stmt = (
        select(Slot)
        .where(
            Slot.facility_id == facility_id,
            Slot.department == department,
            Slot.start_time >= start,
            Slot.start_time < end,
        )
        .options(selectinload(Slot.assignments))
        .order_by(Slot.start_time)
    )
    if slot_ids is not None:
        stmt = stmt.where(Slot.id.in_(slot_ids))
    return [s for s in db.scalars(stmt).all() if len(s.assignments) < s.capacity]


def find_candidate_slots(
    db: Session,
    facility_id: int,
    department: str,
    earliest_date: date,
    latest_date: date,
    preferred_time_of_day: str | None = None,
) -> list[Slot]:
    in_window = _open_slots_in_range(db, facility_id, department, earliest_date, latest_date)
    if preferred_time_of_day:
        return [s for s in in_window if _matches_time_of_day(s.start_time, preferred_time_of_day)]
    return in_window


@app.get("/requests", response_model=list[VisitRequestRead])
def list_visit_requests(db: DbSession) -> list[VisitRequest]:
    return list(db.scalars(select(VisitRequest).order_by(VisitRequest.id)).all())


@app.post("/requests", response_model=VisitRequestRead, status_code=status.HTTP_201_CREATED)
def create_visit_request(
    payload: VisitRequestCreate,
    db: DbSession,
) -> VisitRequest:
    patient = db.get(Patient, payload.patient_id)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pacijent nije pronađen.",
        )

    facility = db.get(Facility, payload.facility_id)
    if facility is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zdravstvena ustanova nije pronađena.",
        )

    max_shift_days = get_urgency_max_shift_days(payload.urgency_class)
    # The urgency window only narrows the slot search; the nurse's dates are stored as entered.
    search_latest = min(payload.latest_date, payload.earliest_date + timedelta(days=max_shift_days))

    if payload.candidate_slot_ids:
        candidates = _open_slots_in_range(
            db,
            payload.facility_id,
            payload.department.value,
            payload.earliest_date,
            search_latest,
            slot_ids=payload.candidate_slot_ids,
        )
    else:
        candidates = find_candidate_slots(
            db=db,
            facility_id=payload.facility_id,
            department=payload.department.value,
            earliest_date=payload.earliest_date,
            latest_date=search_latest,
            preferred_time_of_day=payload.preferred_time_of_day,
        )

    slot_request_pending = not candidates

    visit_request = VisitRequest(
        patient_id=payload.patient_id,
        referral_ref=payload.referral_ref,
        facility_id=payload.facility_id,
        department=payload.department.value,
        visit_type=payload.visit_type.value,
        urgency_class=payload.urgency_class.value,
        earliest_date=payload.earliest_date,
        latest_date=payload.latest_date,
        recurrence=payload.recurrence,
        preferred_time_of_day=payload.preferred_time_of_day,
        slot_request_pending=slot_request_pending,
        status=payload.status.value,
        candidate_slots=candidates,
    )
    db.add(visit_request)
    db.commit()
    db.refresh(visit_request)
    return visit_request


@app.get("/score/{patient_id}", response_model=ScoringResult)
def get_patient_score(
    patient_id: int,
    request_id: int | None = None,
    db: Session = Depends(get_db),
) -> ScoringResult:
    """Izračunaj bodove potrebne za podršku za pacijenta.

    Udaljenost se ne prima od pozivatelja. Ako je zadan ``request_id``, cestovna
    udaljenost od adrese pacijenta do ustanove tog zahtjeva dolazi iz adaptera za
    rute. Bez ``request_id``, bez lokacije ili uz grešku adaptera udaljenost je
    nepoznata i označava se kao nedostajući ulaz (nikad se ne pogađa).
    """
    try:
        config = get_scoring_config()
    except ScoringConfigError:
        logger.exception("Scoring configuration is invalid")
        raise HTTPException(
            status_code=500,
            detail=(
                "Bodovanje trenutačno nije dostupno jer konfiguracija nije ispravna. "
                "Obratite se administratoru."
            ),
        ) from None

    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Pacijent nije pronađen.")

    distance_km: float | None = None
    if request_id is not None:
        visit_request = db.get(VisitRequest, request_id)
        if visit_request is None or visit_request.patient_id != patient.id:
            raise HTTPException(status_code=404, detail="Zahtjev nije pronađen.")
        distance_km = road_distance_km(patient, visit_request.facility, get_routing_client())

    return compute_score(
        patient_id=patient.id,
        mobility_class=patient.mobility_class,
        distance_km=distance_km,
        birth_year=patient.birth_year,
        lives_alone=patient.lives_alone,
        missed_visits_last_year=patient.missed_visits_last_year,
        phone_type=patient.phone_type,
        companion_available=patient.companion,
        config=config,
    )
