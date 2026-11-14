import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy import Connection, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.adapters import get_geocoding_client, get_llm_client
from app.adapters.geocoding import GeocodingClient
from app.adapters.llm import LLMClient
from app.codebooks import Codebooks, get_codebooks, get_urgency_max_shift_days
from app.config import get_settings
from app.db import get_db
from app.intake import extract_intake
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
    PatientRead,
    VisitRequestCreate,
    VisitRequestRead,
)

logger = logging.getLogger("uvicorn.error")
ZAGREB_TZ = ZoneInfo("Europe/Zagreb")

DbSession = Annotated[Session, Depends(get_db)]
LlmDep = Annotated[LLMClient, Depends(get_llm_client)]
GeoDep = Annotated[GeocodingClient, Depends(get_geocoding_client)]


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


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
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
def list_patients(
    db: DbSession,
    mbo: Annotated[str | None, Query(min_length=9, max_length=9)] = None,
) -> list[Patient]:
    stmt = select(Patient).order_by(Patient.id)
    if mbo is not None:
        stmt = stmt.where(Patient.mbo == mbo.strip())
    return list(db.scalars(stmt).all())


@app.post("/patients", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
def create_or_update_patient(
    payload: PatientCreate,
    db: DbSession,
    geocoding_client: GeoDep,
) -> Patient:
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

    existing = db.scalars(select(Patient).where(Patient.mbo == payload.mbo)).first()
    if existing is not None:
        if payload.key is not None:
            existing.key = payload.key
        existing.first_name = payload.first_name
        existing.last_name = payload.last_name
        existing.birth_year = payload.birth_year
        existing.phone = payload.phone
        existing.phone_type = payload.phone_type.value
        existing.address = payload.address
        existing.settlement = settlement
        existing.municipality = municipality
        existing.county = county
        if location_wkt is not None:
            existing.location = location_wkt
        existing.mobility_class = payload.mobility_class.value
        existing.lives_alone = payload.lives_alone
        existing.companion = payload.companion
        existing.floor = payload.floor
        existing.elevator = payload.elevator
        existing.transport_entitlement = payload.transport_entitlement.value
        existing.social_order_today = payload.social_order_today
        existing.own_car = payload.own_car
        existing.carpool_driver_seats = payload.carpool_driver_seats
        existing.carpool_rider_consent = payload.carpool_rider_consent
        existing.driver_documents_confirmed = payload.driver_documents_confirmed
        existing.missed_visits_last_year = payload.missed_visits_last_year
        db.commit()
        db.refresh(existing)
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


def _slot_local_dt(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=ZAGREB_TZ)
    return dt.astimezone(ZAGREB_TZ)


def _matches_time_of_day(dt: datetime, preferred: str | None) -> bool:
    if not preferred:
        return True
    hour = _slot_local_dt(dt).hour
    pref = preferred.strip().lower()
    if pref in ("morning", "ujutro", "prijepodne"):
        return hour < 12
    if pref in ("afternoon", "popodne", "poslijepodne"):
        return hour >= 12
    return True


def find_candidate_slots(
    db: Session,
    facility_id: int,
    department: str,
    earliest_date: date,
    latest_date: date,
    preferred_time_of_day: str | None = None,
) -> list[Slot]:
    stmt = (
        select(Slot)
        .where(Slot.facility_id == facility_id, Slot.department == department)
        .order_by(Slot.start_time)
    )
    all_slots = list(db.scalars(stmt).all())
    in_window = [
        s
        for s in all_slots
        if earliest_date <= _slot_local_dt(s.start_time).date() <= latest_date
        and len(s.assignments) < s.capacity
    ]
    if preferred_time_of_day:
        preferred_matches = [
            s for s in in_window if _matches_time_of_day(s.start_time, preferred_time_of_day)
        ]
        return preferred_matches
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
    urgency_latest = payload.earliest_date + timedelta(days=max_shift_days)
    effective_latest = min(payload.latest_date, urgency_latest)

    if payload.candidate_slot_ids:
        stmt = (
            select(Slot)
            .where(
                Slot.id.in_(payload.candidate_slot_ids),
                Slot.facility_id == payload.facility_id,
                Slot.department == payload.department.value,
            )
            .order_by(Slot.start_time)
        )
        candidates = [
            s
            for s in db.scalars(stmt).all()
            if payload.earliest_date <= _slot_local_dt(s.start_time).date() <= effective_latest
            and len(s.assignments) < s.capacity
        ]
    else:
        candidates = find_candidate_slots(
            db=db,
            facility_id=payload.facility_id,
            department=payload.department.value,
            earliest_date=payload.earliest_date,
            latest_date=effective_latest,
            preferred_time_of_day=payload.preferred_time_of_day,
        )

    if candidates:
        slot_request_pending = False
        preferred_time_of_day = payload.preferred_time_of_day
    else:
        slot_request_pending = True
        preferred_time_of_day = payload.preferred_time_of_day or "morning"

    visit_request = VisitRequest(
        patient_id=payload.patient_id,
        referral_ref=payload.referral_ref,
        facility_id=payload.facility_id,
        department=payload.department.value,
        visit_type=payload.visit_type.value,
        urgency_class=payload.urgency_class.value,
        earliest_date=payload.earliest_date,
        latest_date=effective_latest,
        recurrence=payload.recurrence,
        preferred_time_of_day=preferred_time_of_day,
        slot_request_pending=slot_request_pending,
        status=payload.status.value,
        candidate_slots=candidates,
    )
    db.add(visit_request)
    db.commit()
    db.refresh(visit_request)
    return visit_request
