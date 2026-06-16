"""Add header_fingerprint to source_files for remembered mappings (RF-12 / T-5.5).

Revision ID: 004
Revises: 003
Create Date: 2026-06-16
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "004"
down_revision: str | Sequence[str] | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "source_files",
        sa.Column(
            "header_fingerprint",
            mysql.CHAR(64, charset="ascii", collation="ascii_bin"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_source_files_role_header_fingerprint",
        "source_files",
        ["role", "header_fingerprint"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_source_files_role_header_fingerprint", table_name="source_files")
    op.drop_column("source_files", "header_fingerprint")
