from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            if not hasattr(type(self), k):
                raise TypeError(f"{k!r} is an invalid keyword argument for {type(self).__name__}")
            setattr(self, k, v)
        mapper = getattr(self, "__mapper__", None)
        if mapper is not None:
            for col in mapper.columns:
                attr_name = mapper.get_property_by_column(col).key
                if getattr(self, attr_name, None) is None and col.default is not None:
                    if getattr(col.default, "is_scalar", False):
                        setattr(self, attr_name, col.default.arg)



engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

