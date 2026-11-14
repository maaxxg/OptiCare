import os
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command

# Tests must run without a database.
os.environ["CHECK_DB_ON_STARTUP"] = "false"

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


@pytest.fixture
def alembic_cfg() -> Config:
    return _alembic_config()


@pytest.fixture
def migrated(alembic_cfg: Config) -> Generator[None, None, None]:
    """Fresh schema at head for one test; always downgraded to base afterwards."""
    cfg = alembic_cfg
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    try:
        yield
    finally:
        from app.db import engine

        engine.dispose()
        command.downgrade(cfg, "base")
