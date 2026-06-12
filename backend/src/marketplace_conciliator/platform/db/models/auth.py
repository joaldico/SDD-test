"""ORM models for authentication tables — plan 3.6 / ADR-003."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.mysql import BIGINT, CHAR, DATETIME, ENUM
from sqlalchemy.orm import Mapped, mapped_column

from marketplace_conciliator.platform.db.base import Base

_TABLE_OPTS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}


class User(Base):
    """Application user with Argon2id password hash and RBAC role."""

    __tablename__ = "users"
    __table_args__ = (_TABLE_OPTS,)

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        ENUM("admin", "operator", name="user_role"),
        nullable=False,
        server_default="operator",
    )
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        server_default="CURRENT_TIMESTAMP(6)",
    )


class RefreshToken(Base):
    """Opaque refresh token state — SHA-256 hash persisted, rotation chain via replaced_by."""

    __tablename__ = "refresh_tokens"
    __table_args__ = (_TABLE_OPTS,)

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(
        CHAR(64, charset="ascii", collation="ascii_bin"),
        nullable=False,
        unique=True,
    )
    family_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False)
    replaced_by: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("refresh_tokens.id"),
        nullable=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False)
