import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import Connection, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.adapters import get_routing_client
from app.codebooks import Codebooks, get_codebooks
from app.config import get_settings
from app.db import get_db
from app.models import Patient, VisitRequest
from app.scoring import (
    ScoringConfigError,
    ScoringResult,
    compute_score,
    get_scoring_config,
    road_distance_km,
)

logger = logging.getLogger("uvicorn.error")


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
    try:
        get_scoring_config()
    except ScoringConfigError as exc:
        raise StartupCheckError(f"Scoring configuration is invalid: {exc}") from exc
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
