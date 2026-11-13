import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="DB tests are opt-in: set RUN_DB_TESTS=1 and start the db service",
)


def test_postgis_extension_present() -> None:
    from app.db import engine
    from app.main import check_postgis

    with engine.connect() as conn:
        assert check_postgis(conn)
