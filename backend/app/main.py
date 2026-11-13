import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import Connection, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings

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
                f"Database is unreachable ({type(exc).__name__}); check DATABASE_URL and that the db service is up"
            ) from None
        logger.info("PostGIS %s detected", version)
    yield


app = FastAPI(title="OptiCare", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
