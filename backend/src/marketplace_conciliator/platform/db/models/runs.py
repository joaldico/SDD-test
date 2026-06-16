"""ORM models for domain tables — reconciliation_runs, source_files, column_mappings.

Physical model spec: plan 3.6.
Critical constraints:
  - UNIQUE(run_id, role) on source_files — one role per run (RF-01).
  - UNIQUE(source_file_id, logical_field) on column_mappings — one mapping per field (OBJ-03).
  - status INDEX on reconciliation_runs — required for efficient polling (ADR-002).
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — SQLAlchemy resolves Mapped[datetime] at runtime
from typing import Any

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, CHAR, DATETIME, ENUM, INTEGER, JSON
from sqlalchemy.orm import Mapped, mapped_column

from marketplace_conciliator.platform.db.base import Base

_TABLE_OPTS: dict[str, str] = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}


class ReconciliationRun(Base):
    """Top-level run entity.

    Tracks pipeline status and phase for polling (ADR-002).
    summary_metrics is written atomically at completion (plan 3.4).
    """

    __tablename__ = "reconciliation_runs"
    __table_args__ = (
        Index("ix_reconciliation_runs_status", "status"),
        _TABLE_OPTS,
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    marketplace: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default="amazon_es",
    )
    status: Mapped[str] = mapped_column(
        ENUM("uploaded", "mapping", "processing", "completed", "failed", name="run_status"),
        nullable=False,
    )
    phase: Mapped[str | None] = mapped_column(String(32), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        server_default="CURRENT_TIMESTAMP(6)",
    )
    completed_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True)


class SourceFile(Base):
    """Uploaded file bound to a run by its functional role.

    UNIQUE(run_id, role) ensures at most one file per role per run (plan 3.6).
    sha256 stored for integrity traceability (RNF-05).
    """

    __tablename__ = "source_files"
    __table_args__ = (
        UniqueConstraint("run_id", "role", name="uq_source_files_run_id_role"),
        _TABLE_OPTS,
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("reconciliation_runs.id"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        ENUM("occ_top", "wm_feed", "amazon_report", name="source_file_role"),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    sha256: Mapped[str] = mapped_column(
        CHAR(64, charset="ascii", collation="ascii_bin"),
        nullable=False,
    )
    detected_encoding: Mapped[str | None] = mapped_column(String(16), nullable=True)
    detected_delimiter: Mapped[str | None] = mapped_column(String(8), nullable=True)
    sheet_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    data_start_row: Mapped[int | None] = mapped_column(INTEGER(unsigned=True), nullable=True)
    header_fingerprint: Mapped[str | None] = mapped_column(
        CHAR(64, charset="ascii", collation="ascii_bin"),
        nullable=True,
    )
    total_rows: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False)
    discarded_rows: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False)


class ColumnMapping(Base):
    """Confirmed human mapping between a logical field and a physical column.

    UNIQUE(source_file_id, logical_field) prevents mapping the same field twice (plan 3.6).
    confirmed_by + confirmed_at enforce the human gate (OBJ-03).
    """

    __tablename__ = "column_mappings"
    __table_args__ = (
        UniqueConstraint(
            "source_file_id",
            "logical_field",
            name="uq_column_mappings_source_file_id_logical_field",
        ),
        _TABLE_OPTS,
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    source_file_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("source_files.id"),
        nullable=False,
    )
    logical_field: Mapped[str] = mapped_column(
        ENUM(
            "sku",
            "stock",
            "error_code",
            "error_category",
            "error_message",
            "affected_field",
            name="logical_field_enum",
        ),
        nullable=False,
    )
    source_column_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_column_index: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False)
    was_suggested: Mapped[bool] = mapped_column(nullable=False)
    confirmed_by: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    confirmed_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False)
