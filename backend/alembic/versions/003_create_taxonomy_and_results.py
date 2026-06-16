"""Create taxonomy and reconciliation result tables with initial data seeds (plan 3.6 / T-1.7).

Revision ID: 003
Revises: 002
Create Date: 2026-06-12

Tables created:
  - error_families   — 7 seeded business families (spec 2.8).
  - error_codes      — 53 seeded codes mapped to families; SIN_CLASIFICAR starts empty (RF-14).
  - duplicate_findings — deduplication audit per source_file (spec 2.6).
  - run_items        — one row per SKU in the reconciliation universe (spec 2.7).
  - item_errors      — 1:N Amazon errors per run_item (RF-07).

Critical physical constraints (plan 3.6):
  - utf8mb4_bin on sku_norm, error_codes.code, item_errors.error_code — byte-exact cross-join key.
  - Composite INDEX (run_id, sync_status, feed_stock DESC) on run_items — Vista 3 ordering.
  - feed_stock is signed INT — negative values confirmed valid by client (EB-07).
  - Seeds: upgrade() inserts, downgrade() tables are dropped (data removed implicitly).
"""

from __future__ import annotations

from typing import Any, Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "003"
down_revision: str | Sequence[str] | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE_OPTS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}

# utf8mb4_bin for cross-join key columns (plan 3.6).
_BIN_CHAR_64 = sa.String(64, collation="utf8mb4_bin")
_BIN_CHAR_16 = sa.String(16, collation="utf8mb4_bin")

# ── Seed data (spec 2.8) ──────────────────────────────────────────────────────
#
# 7 families derived from the 53 real error codes observed in the client's Amazon
# ListingLoader processing summary (spec 2.2.3). SIN_CLASIFICAR is the mandatory
# fallback family for codes encountered during reconciliation that are not yet mapped (EB-10).
#
# Distribution: AUTORIZACION_MARCA(10) + RESTRICCION_PUBLICACION(8) +
#               CUMPLIMIENTO_NORMATIVO(12) + IDENTIFICADORES_PRODUCTO(6) +
#               CALIDAD_DE_DATOS(12) + IMAGENES(5) = 53 codes.

_FAMILY_SEEDS: list[dict[str, Any]] = [
    {
        "code": "AUTORIZACION_MARCA",
        "display_name": "Autorización de marca",
        "description": (
            "El vendedor necesita aprobación para publicar la marca "
            "o hace uso indebido de marcas registradas."
        ),
        "sort_order": 1,
    },
    {
        "code": "RESTRICCION_PUBLICACION",
        "display_name": "Restricción de publicación",
        "description": (
            "El producto está sujeto a restricciones de categoría "
            "o de publicación de Amazon."
        ),
        "sort_order": 2,
    },
    {
        "code": "CUMPLIMIENTO_NORMATIVO",
        "display_name": "Cumplimiento normativo",
        "description": (
            "RGPD/GPSR: información de fabricante, persona responsable, "
            "advertencias de seguridad y etiquetado energético."
        ),
        "sort_order": 3,
    },
    {
        "code": "IDENTIFICADORES_PRODUCTO",
        "display_name": "Identificadores de producto",
        "description": "EAN/GTIN/UPC inválidos, demasiado cortos o no aceptados por Amazon.",
        "sort_order": 4,
    },
    {
        "code": "CALIDAD_DE_DATOS",
        "display_name": "Calidad de datos",
        "description": (
            "Atributos faltantes o con valores inválidos, detalles insuficientes, "
            "valores no aceptados en listas controladas (TecDoc, tallas…)."
        ),
        "sort_order": 5,
    },
    {
        "code": "IMAGENES",
        "display_name": "Imágenes",
        "description": (
            "Imagen principal ausente o no conforme "
            "(texto superpuesto, logos, marcas de agua)."
        ),
        "sort_order": 6,
    },
    {
        "code": "SIN_CLASIFICAR",
        "display_name": "Sin clasificar",
        "description": (
            "Familia de fallback obligatoria para códigos de error nuevos o no mapeados. "
            "Visible en la Vista 1 con aviso cuando tiene contenido (RF-14, EB-10)."
        ),
        "sort_order": 99,
    },
]

# 53 error codes derived from the real Amazon ListingLoader report (spec 2.2.3).
# All codes point to a concrete family; SIN_CLASIFICAR starts empty.
# first_seen_at is NULL for pre-seeded codes (populated only for auto-detected new codes in T-4.4).
_CODE_SEEDS: list[dict[str, Any]] = [
    # ── AUTORIZACION_MARCA (10 codes) — ≈1.983 errors observed ───────────────
    {"code": "18299", "family_code": "AUTORIZACION_MARCA", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "18749", "family_code": "AUTORIZACION_MARCA", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "18570", "family_code": "AUTORIZACION_MARCA", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "18146", "family_code": "AUTORIZACION_MARCA", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "18148", "family_code": "AUTORIZACION_MARCA", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "18156", "family_code": "AUTORIZACION_MARCA", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "18244", "family_code": "AUTORIZACION_MARCA", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "18355", "family_code": "AUTORIZACION_MARCA", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "18765", "family_code": "AUTORIZACION_MARCA", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "18790", "family_code": "AUTORIZACION_MARCA", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},

    # ── RESTRICCION_PUBLICACION (8 codes) — ≈2.629 errors observed ───────────
    {"code": "18076", "family_code": "RESTRICCION_PUBLICACION", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "18369", "family_code": "RESTRICCION_PUBLICACION", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "100332", "family_code": "RESTRICCION_PUBLICACION", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "18045", "family_code": "RESTRICCION_PUBLICACION", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "18109", "family_code": "RESTRICCION_PUBLICACION", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "18110", "family_code": "RESTRICCION_PUBLICACION", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "18364", "family_code": "RESTRICCION_PUBLICACION", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "100333", "family_code": "RESTRICCION_PUBLICACION", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},

    # ── CUMPLIMIENTO_NORMATIVO (12 codes) — ≈1.450 warnings/errors observed ──
    {"code": "100526", "family_code": "CUMPLIMIENTO_NORMATIVO", "default_category": "ADVERTENCIA",
     "canonical_message": None, "first_seen_at": None},
    {"code": "100527", "family_code": "CUMPLIMIENTO_NORMATIVO", "default_category": "ADVERTENCIA",
     "canonical_message": None, "first_seen_at": None},
    {"code": "100528", "family_code": "CUMPLIMIENTO_NORMATIVO", "default_category": "ADVERTENCIA",
     "canonical_message": None, "first_seen_at": None},
    {"code": "18616", "family_code": "CUMPLIMIENTO_NORMATIVO", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "100229", "family_code": "CUMPLIMIENTO_NORMATIVO", "default_category": "ADVERTENCIA",
     "canonical_message": None, "first_seen_at": None},
    {"code": "18917", "family_code": "CUMPLIMIENTO_NORMATIVO", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "100230", "family_code": "CUMPLIMIENTO_NORMATIVO", "default_category": "ADVERTENCIA",
     "canonical_message": None, "first_seen_at": None},
    {"code": "100231", "family_code": "CUMPLIMIENTO_NORMATIVO", "default_category": "ADVERTENCIA",
     "canonical_message": None, "first_seen_at": None},
    {"code": "100232", "family_code": "CUMPLIMIENTO_NORMATIVO", "default_category": "ADVERTENCIA",
     "canonical_message": None, "first_seen_at": None},
    {"code": "18918", "family_code": "CUMPLIMIENTO_NORMATIVO", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "18919", "family_code": "CUMPLIMIENTO_NORMATIVO", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "100535", "family_code": "CUMPLIMIENTO_NORMATIVO", "default_category": "ADVERTENCIA",
     "canonical_message": None, "first_seen_at": None},

    # ── IDENTIFICADORES_PRODUCTO (6 codes) — ≈573 errors observed ────────────
    {"code": "90226", "family_code": "IDENTIFICADORES_PRODUCTO", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "90227", "family_code": "IDENTIFICADORES_PRODUCTO", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "90228", "family_code": "IDENTIFICADORES_PRODUCTO", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "5562",  "family_code": "IDENTIFICADORES_PRODUCTO", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "5665",  "family_code": "IDENTIFICADORES_PRODUCTO", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "8581",  "family_code": "IDENTIFICADORES_PRODUCTO", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},

    # ── CALIDAD_DE_DATOS (12 codes) — ≈600 errors observed ───────────────────
    {"code": "8560",       "family_code": "CALIDAD_DE_DATOS", "default_category": "ADVERTENCIA",
     "canonical_message": None, "first_seen_at": None},
    {"code": "100632",     "family_code": "CALIDAD_DE_DATOS", "default_category": "ADVERTENCIA",
     "canonical_message": None, "first_seen_at": None},
    {"code": "18448",      "family_code": "CALIDAD_DE_DATOS", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "99016",      "family_code": "CALIDAD_DE_DATOS", "default_category": "ADVERTENCIA",
     "canonical_message": None, "first_seen_at": None},
    {"code": "99022",      "family_code": "CALIDAD_DE_DATOS", "default_category": "ADVERTENCIA",
     "canonical_message": None, "first_seen_at": None},
    {"code": "90220",      "family_code": "CALIDAD_DE_DATOS", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "90244",      "family_code": "CALIDAD_DE_DATOS", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "90004205",   "family_code": "CALIDAD_DE_DATOS", "default_category": "ADVERTENCIA",
     "canonical_message": None, "first_seen_at": None},
    {"code": "8541",       "family_code": "CALIDAD_DE_DATOS", "default_category": "ADVERTENCIA",
     "canonical_message": None, "first_seen_at": None},
    {"code": "99005",      "family_code": "CALIDAD_DE_DATOS", "default_category": "ADVERTENCIA",
     "canonical_message": None, "first_seen_at": None},
    {"code": "90002",      "family_code": "CALIDAD_DE_DATOS", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "90005",      "family_code": "CALIDAD_DE_DATOS", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},

    # ── IMAGENES (5 codes) — ≈68 errors observed ─────────────────────────────
    {"code": "18320", "family_code": "IMAGENES", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "18027", "family_code": "IMAGENES", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "18022", "family_code": "IMAGENES", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "18023", "family_code": "IMAGENES", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
    {"code": "18024", "family_code": "IMAGENES", "default_category": "ERROR",
     "canonical_message": None, "first_seen_at": None},
]

_EXPECTED_CODE_COUNT = 53
assert len(_CODE_SEEDS) == _EXPECTED_CODE_COUNT, (  # noqa: S101
    f"Expected {_EXPECTED_CODE_COUNT} error code seeds, got {len(_CODE_SEEDS)}"
)


def upgrade() -> None:
    # ── error_families ────────────────────────────────────────────────────────
    op.create_table(
        "error_families",
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(64), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False),
        sa.PrimaryKeyConstraint("code"),
        **_TABLE_OPTS,
    )

    # ── error_codes ───────────────────────────────────────────────────────────
    # code uses utf8mb4_bin — byte-exact PK for aggregation in Vista 1 (plan 3.6).
    op.create_table(
        "error_codes",
        sa.Column("code", _BIN_CHAR_16, nullable=False),
        sa.Column(
            "family_code",
            sa.String(32),
            nullable=False,
            server_default="SIN_CLASIFICAR",
        ),
        sa.Column("default_category", sa.String(16), nullable=True),
        sa.Column("canonical_message", sa.Text, nullable=True),
        sa.Column("first_seen_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.ForeignKeyConstraint(
            ["family_code"],
            ["error_families.code"],
            name="fk_error_codes_family_code",
        ),
        sa.PrimaryKeyConstraint("code"),
        **_TABLE_OPTS,
    )

    # ── duplicate_findings ────────────────────────────────────────────────────
    op.create_table(
        "duplicate_findings",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("source_file_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("sku_norm", _BIN_CHAR_64, nullable=False),
        sa.Column("occurrences", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column(
            "resolution",
            mysql.ENUM(
                "collapsed_identical",
                "kept_first",
                "kept_max_stock",
                name="duplicate_resolution",
            ),
            nullable=False,
        ),
        sa.Column("discarded_values", sa.JSON, nullable=False),
        sa.ForeignKeyConstraint(
            ["source_file_id"],
            ["source_files.id"],
            name="fk_duplicate_findings_source_file_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        **_TABLE_OPTS,
    )
    op.create_index("ix_duplicate_findings_sku_norm", "duplicate_findings", ["sku_norm"])

    # ── run_items ─────────────────────────────────────────────────────────────
    # feed_stock is signed INT — negative stock confirmed valid by client (EB-07).
    # sku_norm uses utf8mb4_bin for byte-exact cross-join (plan 3.6).
    op.create_table(
        "run_items",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("run_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("sku_norm", _BIN_CHAR_64, nullable=False),
        sa.Column("sku_raw", sa.String(128), nullable=False),
        sa.Column("in_occ", sa.Boolean, nullable=False),
        sa.Column("in_feed", sa.Boolean, nullable=False),
        sa.Column("in_amazon_report", sa.Boolean, nullable=False),
        sa.Column(
            "sync_status",
            mysql.ENUM(
                "SENT_WITH_ERROR",
                "SENT_OK",
                "NOT_SENT",
                "DESYNC_FEED_ONLY",
                "DESYNC_AMAZON_ONLY",
                name="sync_status_enum",
            ),
            nullable=False,
        ),
        sa.Column("feed_stock", sa.Integer, nullable=True),
        sa.Column("occ_stock", sa.Integer, nullable=True),
        sa.Column("stock_conflict", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("submission_status", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["reconciliation_runs.id"],
            name="fk_run_items_run_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "sku_norm", name="uq_run_items_run_id_sku_norm"),
        **_TABLE_OPTS,
    )
    # Composite index with DESC on feed_stock for Vista 3 ordering query (plan 3.6).
    # raw SQL used because SQLAlchemy/Alembic does not reliably emit DESC index columns
    # for MySQL 8 via the standard op.create_index path.
    op.execute(
        sa.text(
            "CREATE INDEX ix_run_items_run_id_sync_status_feed_stock "
            "ON run_items (run_id, sync_status, feed_stock DESC)",
        ),
    )

    # ── item_errors ───────────────────────────────────────────────────────────
    # error_code uses utf8mb4_bin — must match error_codes.code collation (plan 3.6).
    # error_message is TEXT — Amazon messages reach 960+ chars with NBSP (spec 2.2.3, EB-05).
    op.create_table(
        "item_errors",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("run_item_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("error_code", _BIN_CHAR_16, nullable=False),
        sa.Column(
            "error_category",
            mysql.ENUM("ERROR", "ADVERTENCIA", name="error_category_enum"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text, nullable=False),
        sa.Column("affected_field", sa.String(255), nullable=True),
        sa.ForeignKeyConstraint(
            ["run_item_id"],
            ["run_items.id"],
            name="fk_item_errors_run_item_id",
        ),
        sa.ForeignKeyConstraint(
            ["error_code"],
            ["error_codes.code"],
            name="fk_item_errors_error_code",
        ),
        sa.PrimaryKeyConstraint("id"),
        **_TABLE_OPTS,
    )
    op.create_index("ix_item_errors_run_item_id", "item_errors", ["run_item_id"])
    op.create_index("ix_item_errors_error_code", "item_errors", ["error_code"])

    # ── Seeds: 7 families + 53 error codes ───────────────────────────────────
    # Families must be inserted BEFORE codes (FK: error_codes.family_code → error_families.code).
    families_table = sa.table(
        "error_families",
        sa.column("code", sa.String),
        sa.column("display_name", sa.String),
        sa.column("description", sa.Text),
        sa.column("sort_order", sa.Integer),
    )
    op.bulk_insert(families_table, _FAMILY_SEEDS)

    codes_table = sa.table(
        "error_codes",
        sa.column("code", sa.String),
        sa.column("family_code", sa.String),
        sa.column("default_category", sa.String),
        sa.column("canonical_message", sa.Text),
        sa.column("first_seen_at", sa.DateTime),
    )
    op.bulk_insert(codes_table, _CODE_SEEDS)


def downgrade() -> None:
    # Drop tables in reverse FK dependency order.
    # InnoDB drops all associated indexes (including the raw DESC composite index on run_items
    # and FK-supporting indexes on item_errors) automatically when the table is dropped.
    # Seeds in error_families / error_codes are removed implicitly (T-1.7 DoD).
    op.drop_table("item_errors")
    op.drop_table("run_items")
    op.drop_table("duplicate_findings")
    op.drop_table("error_codes")
    op.drop_table("error_families")
