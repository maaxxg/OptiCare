import pytest

from app.main import StartupCheckError, check_postgis


class FakeConn:
    def __init__(self, version: str | None) -> None:
        self.version = version

    def execute(self, _stmt):
        version = self.version

        class Result:
            def scalar_one_or_none(self):
                return version

        return Result()


def test_missing_postgis_raises_clear_error() -> None:
    with pytest.raises(StartupCheckError, match="PostGIS extension is missing"):
        check_postgis(FakeConn(None))  # type: ignore[arg-type]


def test_returns_version() -> None:
    assert check_postgis(FakeConn("3.5.2")) == "3.5.2"  # type: ignore[arg-type]
