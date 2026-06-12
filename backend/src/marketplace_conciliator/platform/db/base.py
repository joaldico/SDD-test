"""SQLAlchemy declarative base for persistence adapters (plan 3.6)."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared metadata registry for Alembic autogenerate and ORM models."""
