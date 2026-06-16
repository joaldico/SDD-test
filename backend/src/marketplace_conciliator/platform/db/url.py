"""Database URL helpers for sync (Alembic) and async (FastAPI) engines."""

from __future__ import annotations


def to_sync_url(database_url: str) -> str:
    """Convert any MySQL SQLAlchemy URL to synchronous pymysql for Alembic."""
    if database_url.startswith("mysql+aiomysql://"):
        return database_url.replace("mysql+aiomysql://", "mysql+pymysql://", 1)
    if database_url.startswith("mysql+asyncmy://"):
        return database_url.replace("mysql+asyncmy://", "mysql+pymysql://", 1)
    if database_url.startswith("mysql://"):
        return database_url.replace("mysql://", "mysql+pymysql://", 1)
    return database_url
