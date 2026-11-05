"""SQLAlchemy engine/session setup (engine created lazily)."""
from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    engine = create_engine(settings.database_url, future=True)
    from app.core.logging_config import init_db_event_logging
    init_db_event_logging(engine)
    return engine


@lru_cache(maxsize=1)
def _get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)


def get_db() -> Iterator[Session]:
    db = _get_sessionmaker()()
    try:
        yield db
    finally:
        db.close()
