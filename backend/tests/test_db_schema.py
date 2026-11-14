"""Opt-in schema tests on real PostGIS: migrations round-trip, indexes, CHECKs, ORM geography."""

import os

import pytest
from alembic.config import Config
from geoalchemy2.shape import to_shape
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="DB tests are opt-in: set RUN_DB_TESTS=1 and start the db service",
)


def _table_names() -> set[str]:
    from app.db import engine

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        ).scalars()
        return set(rows)


def test_migration_round_trip(alembic_cfg: Config) -> None:
    cfg = alembic_cfg
    command.downgrade(cfg, "base")
    try:
        command.upgrade(cfg, "head")
        assert {"patients", "facilities", "vehicles", "municipalities"} <= _table_names()
        command.downgrade(cfg, "base")
        assert "patients" not in _table_names()
        command.upgrade(cfg, "head")
        assert "patients" in _table_names()
    finally:
        command.downgrade(cfg, "base")


@pytest.mark.parametrize(
    ("table", "column"),
    [
        ("patients", "location"),
        ("facilities", "location"),
        ("vehicles", "base_location"),
        ("municipalities", "boundary"),
    ],
)
def test_gist_index_on_geography_column(migrated: None, table: str, column: str) -> None:
    from app.db import engine

    with engine.connect() as conn:
        defs = conn.execute(
            text("SELECT indexdef FROM pg_indexes WHERE schemaname = 'public' AND tablename = :t"),
            {"t": table},
        ).scalars()
        assert any("USING gist" in d and f"({column})" in d for d in defs)


def test_check_constraint_rejects_bad_provider_type(migrated: None) -> None:
    from app.db import engine
    from app.models import Vehicle, make_point_wkt

    with Session(engine) as session:
        session.add(
            Vehicle(provider_type="bus", base_location=make_point_wkt(44.54, 15.37)),
        )
        with pytest.raises(IntegrityError) as exc:
            session.flush()
        assert "ck_vehicles_provider_type" in str(exc.value)
        session.rollback()


def test_orm_geography_round_trip(migrated: None) -> None:
    from app.db import engine
    from app.models import (
        Facility,
        Municipality,
        Patient,
        make_multipolygon_wkt,
        make_point_wkt,
    )

    with Session(engine) as session:
        session.add_all(
            [
                Facility(
                    key="test-facility",
                    name="Testna ustanova",
                    settlement="Gospić",
                    municipality="Gospić",
                    county="Ličko-senjska",
                    location=make_point_wkt(44.5461, 15.3748),
                ),
                Patient(
                    first_name="Ivo",
                    last_name="Ivić",
                    mbo="000000001",
                    phone="+385 00 000 0001",
                    settlement="Gospić",
                    municipality="Gospić",
                    county="Ličko-senjska",
                    location=make_point_wkt(44.55, 15.38),
                ),
                Municipality(
                    name="Testna općina",
                    county="Ličko-senjska",
                    boundary=make_multipolygon_wkt(
                        "POLYGON((15.0 44.0, 15.5 44.0, 15.5 44.5, 15.0 44.5, 15.0 44.0))"
                    ),
                ),
            ]
        )
        session.commit()

    with Session(engine) as session:
        facility = session.query(Facility).one()
        patient = session.query(Patient).one()
        municipality = session.query(Municipality).one()

        fpt = to_shape(facility.location)
        assert (fpt.x, fpt.y) == pytest.approx((15.3748, 44.5461), abs=1e-6)
        assert patient.location is not None
        ppt = to_shape(patient.location)
        assert (ppt.x, ppt.y) == pytest.approx((15.38, 44.55), abs=1e-6)
        assert facility.latitude == pytest.approx(44.5461, abs=1e-6)

        boundary = to_shape(municipality.boundary)
        assert boundary.geom_type == "MultiPolygon"
        assert boundary.bounds == pytest.approx((15.0, 44.0, 15.5, 44.5), abs=1e-6)
