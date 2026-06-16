"""ORM models for taxonomy and reconciliation result tables — plan 3.6 / T-1.7.

Tables created in migration 003:
  - error_families  — 7 seeded business families (spec 2.8).
  - error_codes     — 53 seeded codes mapped to families; SIN_CLASIFICAR fallback (RF-14, EB-10).
  - duplicate_findings — deduplication audit per source_file (spec 2.6).
  - run_items       — one row per SKU in the 3-way reconciliation universe (spec 2.7).
  - item_errors     — 1:N error rows per run_item (RF-07, up to 11+ per SKU observed).

Critical constraints (plan 3.6):
  - sku_norm columns use utf8mb4_bin — byte-exact cross-join key after normalisation (RN-01..06).
  - error_code (item_errors) uses utf8mb4_bin to match error_codes.code collation.
  - Composite INDEX (run_id, sync_status, feed_stock DESC) on run_items for Vista 3 ordering.
  - feed_stock is signed INT — clients may send negative stock (EB-07, confirmed by client).
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — SQLAlchemy resolves Mapped[datetime] at runtime

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, ENUM, INTEGER
from sqlalchemy.dialects.mysql import TEXT as MYSQL_TEXT
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

from marketplace_conciliator.platform.db.base import Base

_TABLE_OPTS: dict[str, str] = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}

# utf8mb4_bin used on cross-join key columns (sku_norm, error_code) — plan 3.6.
_BIN_STR_64 = String(64, collation="utf8mb4_bin")
_BIN_STR_16 = String(16, collation="utf8mb4_bin")


class ErrorFamily(Base):
    """Business grouping of Amazon error codes.

    Seed of 7 families (including SIN_CLASIFICAR fallback) applied in migration 003.
    Maintainable without redeployment — RF-14.
    """

    __tablename__ = "error_families"
    __table_args__ = (_TABLE_OPTS,)

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class ErrorCode(Base):
    """Amazon error code bound to a business family.

    53 codes seeded in migration 003; new codes are auto-inserted with family_code='SIN_CLASIFICAR'
    during reconciliation (T-4.4, RF-14, EB-10).
    code uses utf8mb4_bin for byte-exact grouping in Vista 1 aggregate queries (plan 3.6).
    """

    __tablename__ = "error_codes"
    __table_args__ = (_TABLE_OPTS,)

    code: Mapped[str] = mapped_column(_BIN_STR_16, primary_key=True)
    family_code: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("error_families.code"),
        nullable=False,
        server_default="SIN_CLASIFICAR",
    )
    default_category: Mapped[str | None] = mapped_column(String(16), nullable=True)
    canonical_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_seen_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True)


class DuplicateFinding(Base):
    """Deduplication audit record per source file (spec 2.6).

    sku_norm uses utf8mb4_bin — consistent with the cross-join key (plan 3.6).
    resolution documents the applied policy so Vista 3 can show it explicitly (OBJ-08).
    """

    __tablename__ = "duplicate_findings"
    __table_args__ = (
        Index("ix_duplicate_findings_sku_norm", "sku_norm"),
        _TABLE_OPTS,
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    source_file_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("source_files.id"),
        nullable=False,
    )
    sku_norm: Mapped[str] = mapped_column(_BIN_STR_64, nullable=False)
    occurrences: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False)
    resolution: Mapped[str] = mapped_column(
        ENUM(
            "collapsed_identical",
            "kept_first",
            "kept_max_stock",
            name="duplicate_resolution",
        ),
        nullable=False,
    )
    discarded_values: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


class RunItem(Base):
    """One row per SKU in the 3-way reconciliation universe.

    sku_norm is the cross-join key — utf8mb4_bin ensures byte-exact equality after
    normalisation (RN-01..06) and prevents silent false-negatives from collation folding.
    feed_stock is signed: confirmed by client that other orgs may send negative stock (EB-07).
    Composite index (run_id, sync_status, feed_stock DESC) optimises Vista 3 sorted queries.
    """

    __tablename__ = "run_items"
    __table_args__ = (
        UniqueConstraint("run_id", "sku_norm", name="uq_run_items_run_id_sku_norm"),
        Index(
            "ix_run_items_run_id_sync_status_feed_stock",
            "run_id",
            "sync_status",
            text("feed_stock DESC"),
        ),
        _TABLE_OPTS,
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("reconciliation_runs.id"),
        nullable=False,
    )
    sku_norm: Mapped[str] = mapped_column(_BIN_STR_64, nullable=False)
    sku_raw: Mapped[str] = mapped_column(String(128), nullable=False)
    in_occ: Mapped[bool] = mapped_column(Boolean, nullable=False)
    in_feed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    in_amazon_report: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sync_status: Mapped[str] = mapped_column(
        ENUM(
            "SENT_WITH_ERROR",
            "SENT_OK",
            "NOT_SENT",
            "DESYNC_FEED_ONLY",
            "DESYNC_AMAZON_ONLY",
            name="sync_status_enum",
        ),
        nullable=False,
    )
    feed_stock: Mapped[int | None] = mapped_column(Integer, nullable=True)
    occ_stock: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stock_conflict: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="0",
    )
    submission_status: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ItemError(Base):
    """Individual Amazon error associated with a run_item (RF-07).

    1:N per run_item — up to 11+ errors per SKU observed in real data (spec 2.2.3).
    error_code uses utf8mb4_bin to match the PK collation of error_codes (plan 3.6).
    error_message is TEXT — Amazon messages reach 960+ chars with NBSP (spec 2.2.3, EB-05).
    """

    __tablename__ = "item_errors"
    __table_args__ = (
        Index("ix_item_errors_run_item_id", "run_item_id"),
        Index("ix_item_errors_error_code", "error_code"),
        _TABLE_OPTS,
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    run_item_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("run_items.id"),
        nullable=False,
    )
    error_code: Mapped[str] = mapped_column(
        _BIN_STR_16,
        ForeignKey("error_codes.code"),
        nullable=False,
    )
    error_category: Mapped[str] = mapped_column(
        ENUM("ERROR", "ADVERTENCIA", name="error_category_enum"),
        nullable=False,
    )
    error_message: Mapped[str] = mapped_column(MYSQL_TEXT, nullable=False)
    affected_field: Mapped[str | None] = mapped_column(String(255), nullable=True)
