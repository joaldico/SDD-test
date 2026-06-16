"""Synchronous SQLAlchemy session factory (platform dependency, T-3.6).

The session is built lazily from Settings.database_url so that the import
does not fail at startup when the URL is empty (e.g. in unit tests that
override the dependency).
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from marketplace_conciliator.platform.db.url import to_sync_url
from marketplace_conciliator.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Generator


@lru_cache(maxsize=1)
def _get_session_factory() -> sessionmaker[Session]:
    settings = get_settings()
    url = to_sync_url(settings.database_url)
    engine = create_engine(url, pool_pre_ping=True)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session_factory() -> sessionmaker[Session]:
    """Return the cached sessionmaker instance (public API for background threads).

    Background tasks (e.g. TaskRunner) use this to create per-thread sessions
    outside the FastAPI dependency-injection lifecycle.
    """
    return _get_session_factory()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a synchronous SQLAlchemy session."""
    factory = _get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()
