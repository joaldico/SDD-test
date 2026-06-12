"""Create reconciliation_runs, source_files and column_mappings tables (plan 3.6 / T-1.6).

Revision ID: 002
Revises: 001
Create Date: 2026-06-12

Physical model — critical constraints:
  - reconciliation_runs.status: INDEX for polling queries (ADR-002).
  - source_files: UNIQUE(run_id, role) — one file per role per run (RF-01).
  - column_mappings: UNIQUE(source_file_id, logical_field) — one mapping per field (OBJ-03).
Global charset/collation: utf8mb4 / utf8mb4_0900_ai_ci (InnoDB).
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "002"
down_revision: str | Sequence[str] | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE_OPTS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}


def upgrade() -> None:
    # ── reconciliation_runs ───────────────────────────────────────────────────
    op.create_table(
        "reconciliation_runs",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column(
            "marketplace",
            sa.String(32),
            nullable=False,
            server_default="amazon_es",
        ),
        sa.Column(
            "status",
            mysql.ENUM(
                "uploaded",
                "mapping",
                "processing",
                "completed",
                "failed",
                name="run_status",
            ),
            nullable=False,
        ),
        sa.Column("phase", sa.String(32), nullable=True),
        sa.Column("failure_reason", sa.String(255), nullable=True),
        sa.Column("summary_metrics", sa.JSON, nullable=True),
        sa.Column(
            "created_at",
            mysql.DATETIME(fsp=6),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
        ),
        sa.Column("completed_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_reconciliation_runs_user_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        **_TABLE_OPTS,
    )
    op.create_index(
        "ix_reconciliation_runs_status",
        "reconciliation_runs",
        ["status"],
        unique=False,
    )

    # ── source_files ──────────────────────────────────────────────────────────
    op.create_table(
        "source_files",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("run_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column(
            "role",
            mysql.ENUM("occ_top", "wm_feed", "amazon_report", name="source_file_role"),
            nullable=False,
        ),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column(
            "sha256",
            mysql.CHAR(length=64, charset="ascii", collation="ascii_bin"),
            nullable=False,
        ),
        sa.Column("detected_encoding", sa.String(16), nullable=True),
        sa.Column("detected_delimiter", sa.String(8), nullable=True),
        sa.Column("sheet_name", sa.String(64), nullable=True),
        sa.Column("data_start_row", mysql.INTEGER(unsigned=True), nullable=True),
        sa.Column("total_rows", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("discarded_rows", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("uploaded_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["reconciliation_runs.id"],
            name="fk_source_files_run_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "role", name="uq_source_files_run_id_role"),
        **_TABLE_OPTS,
    )

    # ── column_mappings ───────────────────────────────────────────────────────
    op.create_table(
        "column_mappings",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("source_file_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column(
            "logical_field",
            mysql.ENUM(
                "sku",
                "stock",
                "error_code",
                "error_category",
                "error_message",
                "affected_field",
                name="logical_field_enum",
            ),
            nullable=False,
        ),
        sa.Column("source_column_name", sa.String(255), nullable=False),
        sa.Column("source_column_index", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("was_suggested", sa.Boolean, nullable=False),
        sa.Column("confirmed_by", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("confirmed_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_file_id"],
            ["source_files.id"],
            name="fk_column_mappings_source_file_id",
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by"],
            ["users.id"],
            name="fk_column_mappings_confirmed_by",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_file_id",
            "logical_field",
            name="uq_column_mappings_source_file_id_logical_field",
        ),
        **_TABLE_OPTS,
    )


def downgrade() -> None:
    # Drop in reverse FK dependency order to satisfy InnoDB FK constraints.
    op.drop_table("column_mappings")
    op.drop_table("source_files")
    op.drop_index("ix_reconciliation_runs_status", table_name="reconciliation_runs")
    op.drop_table("reconciliation_runs")
