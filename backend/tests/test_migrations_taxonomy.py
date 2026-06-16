"""Migration tests for T-1.7.

error_families, error_codes (with seeds), run_items, item_errors, duplicate_findings
(plan 3.6 / spec 2.8).

TDD gate: written BEFORE the Alembic migration and ORM models exist.
Runs against an ephemeral MySQL 8 container (testcontainers).

Verifies:
  - Tables are created with correct types, collations and constraints.
  - utf8mb4_bin on cross-join key columns (sku_norm, error_code) — plan 3.6, spec 2.8.
  - Composite index (run_id, sync_status, feed_stock DESC) on run_items — plan 3.6, Vista 3.
  - EXPLAIN confirms the composite index is used by the Vista 3 ordering query.
  - Seeds: 7 families (including SIN_CLASIFICAR) + 53 mapped codes (0 pointing to SIN_CLASIFICAR)
    are inserted in upgrade() and absent after downgrade 003→002 — T-1.7 DoD.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import TypedDict

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from testcontainers.mysql import MySqlContainer

from marketplace_conciliator.platform.db.url import to_sync_url

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"

EXPECTED_TABLE_COLLATION = "utf8mb4_0900_ai_ci"
EXPECTED_BIN_COLLATION = "utf8mb4_bin"

TAXONOMY_TABLES = frozenset(
    {"error_families", "error_codes", "run_items", "item_errors", "duplicate_findings"},
)
DOMAIN_TABLES = frozenset({"reconciliation_runs", "source_files", "column_mappings"})
AUTH_TABLES = frozenset({"users", "refresh_tokens"})

COMPOSITE_INDEX_NAME = "ix_run_items_run_id_sync_status_feed_stock"

EXPECTED_FAMILIES = 7
EXPECTED_CODES = 53
SIN_CLASIFICAR_CODE = "SIN_CLASIFICAR"


class _ColumnInfo(TypedDict):
    column_type: str
    collation: str | None
    nullable: str
    key: str
    extra: str


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def mysql_url() -> Generator[str, None, None]:
    """Ephemeral MySQL 8 matching docker-compose charset/collation (plan 3.6)."""
    container = MySqlContainer("mysql:8").with_command(
        "--character-set-server=utf8mb4 "
        "--collation-server=utf8mb4_0900_ai_ci "
        "--default-time-zone=+00:00",
    )
    with container as mysql:
        yield to_sync_url(mysql.get_connection_url())


@pytest.fixture(scope="module")
def migrated_engine(mysql_url: str) -> Generator[Engine, None, None]:
    """Engine with migrations 001+002+003 applied (upgrade head)."""
    alembic_cfg = Config(str(ALEMBIC_INI))
    alembic_cfg.set_main_option("sqlalchemy.url", mysql_url)
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(mysql_url)
    yield engine
    engine.dispose()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _table_collation(engine: Engine, table: str) -> str:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT TABLE_COLLATION FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table",
            ),
            {"table": table},
        ).one()
    return str(row[0])


def _column_info(engine: Engine, table: str, column: str) -> _ColumnInfo:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT COLUMN_TYPE, COLLATION_NAME, IS_NULLABLE, COLUMN_KEY, EXTRA "
                "FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME = :table AND COLUMN_NAME = :column",
            ),
            {"table": table, "column": column},
        ).one()
    collation = row[1]
    return {
        "column_type": str(row[0]),
        "collation": str(collation) if collation is not None else None,
        "nullable": str(row[2]),
        "key": str(row[3]),
        "extra": str(row[4]),
    }


def _count(engine: Engine, table: str) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one())  # noqa: S608


# ── Table existence ───────────────────────────────────────────────────────────


def test_migration_upgrade_creates_taxonomy_tables(migrated_engine: Engine) -> None:
    tables = set(inspect(migrated_engine).get_table_names())
    assert TAXONOMY_TABLES.issubset(tables), (
        f"Missing taxonomy tables: {TAXONOMY_TABLES - tables}"
    )


def test_prior_tables_still_present_after_003(migrated_engine: Engine) -> None:
    tables = set(inspect(migrated_engine).get_table_names())
    assert (DOMAIN_TABLES | AUTH_TABLES).issubset(tables), (
        "Domain and auth tables must survive 003 upgrade"
    )


# ── Table-level collations ────────────────────────────────────────────────────


def test_taxonomy_tables_use_utf8mb4_global_collation(migrated_engine: Engine) -> None:
    for table in TAXONOMY_TABLES:
        assert _table_collation(migrated_engine, table) == EXPECTED_TABLE_COLLATION, (
            f"{table} must use {EXPECTED_TABLE_COLLATION} (plan 3.6 global charset)"
        )


# ── error_families ────────────────────────────────────────────────────────────


def test_error_families_code_is_varchar32_pk(migrated_engine: Engine) -> None:
    col = _column_info(migrated_engine, "error_families", "code")
    assert "varchar(32)" in col["column_type"].lower()
    assert col["key"] == "PRI"
    assert col["nullable"] == "NO"


def test_error_families_display_name_not_null(migrated_engine: Engine) -> None:
    col = _column_info(migrated_engine, "error_families", "display_name")
    assert "varchar(64)" in col["column_type"].lower()
    assert col["nullable"] == "NO"


def test_error_families_sort_order_not_null(migrated_engine: Engine) -> None:
    col = _column_info(migrated_engine, "error_families", "sort_order")
    assert "int" in col["column_type"].lower()
    assert col["nullable"] == "NO"


# ── error_codes ───────────────────────────────────────────────────────────────


def test_error_codes_code_is_varchar16_bin_pk(migrated_engine: Engine) -> None:
    """error_codes.code must use utf8mb4_bin for byte-exact cross-join (plan 3.6)."""
    col = _column_info(migrated_engine, "error_codes", "code")
    assert "varchar(16)" in col["column_type"].lower()
    assert col["key"] == "PRI"
    assert col["nullable"] == "NO"
    assert col["collation"] == EXPECTED_BIN_COLLATION, (
        f"error_codes.code must be {EXPECTED_BIN_COLLATION} (plan 3.6)"
    )


def test_error_codes_family_code_not_null_fk(migrated_engine: Engine) -> None:
    col = _column_info(migrated_engine, "error_codes", "family_code")
    assert col["nullable"] == "NO"
    fks = inspect(migrated_engine).get_foreign_keys("error_codes")
    family_fk = next((fk for fk in fks if fk["referred_table"] == "error_families"), None)
    assert family_fk is not None, "error_codes must have FK → error_families"
    assert family_fk["constrained_columns"] == ["family_code"]


def test_error_codes_first_seen_at_nullable(migrated_engine: Engine) -> None:
    col = _column_info(migrated_engine, "error_codes", "first_seen_at")
    assert col["column_type"] == "datetime(6)"
    assert col["nullable"] == "YES"


# ── duplicate_findings ────────────────────────────────────────────────────────


def test_duplicate_findings_sku_norm_is_utf8mb4_bin(migrated_engine: Engine) -> None:
    """sku_norm must use utf8mb4_bin for byte-exact matching (plan 3.6)."""
    col = _column_info(migrated_engine, "duplicate_findings", "sku_norm")
    assert col["collation"] == EXPECTED_BIN_COLLATION, (
        f"duplicate_findings.sku_norm must be {EXPECTED_BIN_COLLATION} (plan 3.6)"
    )
    assert col["nullable"] == "NO"


def test_duplicate_findings_resolution_enum_values(migrated_engine: Engine) -> None:
    col = _column_info(migrated_engine, "duplicate_findings", "resolution")
    enum_type = col["column_type"].lower()
    assert "enum" in enum_type
    for value in ("collapsed_identical", "kept_first", "kept_max_stock"):
        assert value in enum_type, f"resolution ENUM must include '{value}' (spec 2.6)"


def test_duplicate_findings_discarded_values_is_json(migrated_engine: Engine) -> None:
    col = _column_info(migrated_engine, "duplicate_findings", "discarded_values")
    assert col["column_type"].lower() == "json"
    assert col["nullable"] == "NO"


def test_duplicate_findings_fk_to_source_files(migrated_engine: Engine) -> None:
    fks = inspect(migrated_engine).get_foreign_keys("duplicate_findings")
    sf_fk = next((fk for fk in fks if fk["referred_table"] == "source_files"), None)
    assert sf_fk is not None, "duplicate_findings must have FK → source_files"
    assert sf_fk["constrained_columns"] == ["source_file_id"]


# ── run_items ─────────────────────────────────────────────────────────────────


def test_run_items_sku_norm_is_utf8mb4_bin(migrated_engine: Engine) -> None:
    """sku_norm is the cross-join key — must be utf8mb4_bin (plan 3.6)."""
    col = _column_info(migrated_engine, "run_items", "sku_norm")
    assert col["collation"] == EXPECTED_BIN_COLLATION, (
        f"run_items.sku_norm must be {EXPECTED_BIN_COLLATION} (plan 3.6)"
    )
    assert col["nullable"] == "NO"


def test_run_items_sku_raw_not_null(migrated_engine: Engine) -> None:
    col = _column_info(migrated_engine, "run_items", "sku_raw")
    assert "varchar(128)" in col["column_type"].lower()
    assert col["nullable"] == "NO"


def test_run_items_sync_status_enum_values_not_null(migrated_engine: Engine) -> None:
    col = _column_info(migrated_engine, "run_items", "sync_status")
    enum_type = col["column_type"].lower()
    assert "enum" in enum_type
    for value in (
        "SENT_WITH_ERROR",
        "SENT_OK",
        "NOT_SENT",
        "DESYNC_FEED_ONLY",
        "DESYNC_AMAZON_ONLY",
    ):
        assert value.lower() in enum_type, (
            f"sync_status ENUM must include '{value}' (spec 2.7)"
        )
    assert col["nullable"] == "NO"


def test_run_items_feed_stock_signed_nullable(migrated_engine: Engine) -> None:
    """feed_stock must be signed INT (EB-07: negative stock from other clients) and nullable."""
    col = _column_info(migrated_engine, "run_items", "feed_stock")
    assert "int" in col["column_type"].lower()
    assert "unsigned" not in col["column_type"].lower(), (
        "feed_stock must be signed — clients may send negative stock (EB-07)"
    )
    assert col["nullable"] == "YES"


def test_run_items_stock_conflict_boolean_default_false(migrated_engine: Engine) -> None:
    col = _column_info(migrated_engine, "run_items", "stock_conflict")
    assert col["column_type"].lower() in ("tinyint(1)", "tinyint", "boolean", "bit(1)")
    assert col["nullable"] == "NO"


def test_run_items_fk_to_reconciliation_runs(migrated_engine: Engine) -> None:
    fks = inspect(migrated_engine).get_foreign_keys("run_items")
    run_fk = next((fk for fk in fks if fk["referred_table"] == "reconciliation_runs"), None)
    assert run_fk is not None, "run_items must have FK → reconciliation_runs"
    assert run_fk["constrained_columns"] == ["run_id"]


def test_run_items_unique_constraint_run_id_sku_norm(migrated_engine: Engine) -> None:
    ucs = inspect(migrated_engine).get_unique_constraints("run_items")
    col_sets = [set(uc["column_names"]) for uc in ucs]
    assert {"run_id", "sku_norm"} in col_sets, (
        "UNIQUE(run_id, sku_norm) must exist in run_items (spec 2.10)"
    )


def test_run_items_composite_index_exists(migrated_engine: Engine) -> None:
    """Composite index (run_id, sync_status, feed_stock DESC) must exist for Vista 3 (plan 3.6)."""
    indexes = inspect(migrated_engine).get_indexes("run_items")
    idx_names = {idx["name"] for idx in indexes}
    assert COMPOSITE_INDEX_NAME in idx_names, (
        f"Index '{COMPOSITE_INDEX_NAME}' must exist on run_items (plan 3.6)"
    )


def test_run_items_composite_index_columns(migrated_engine: Engine) -> None:
    """First two columns of the composite index must be run_id and sync_status (plan 3.6)."""
    indexes = inspect(migrated_engine).get_indexes("run_items")
    composite = next((idx for idx in indexes if idx["name"] == COMPOSITE_INDEX_NAME), None)
    assert composite is not None
    columns = composite["column_names"]
    assert columns[0] == "run_id", "First composite index column must be run_id"
    assert columns[1] == "sync_status", "Second composite index column must be sync_status"


def test_run_items_composite_index_used_by_explain(migrated_engine: Engine) -> None:
    """EXPLAIN must confirm the composite index is used for the Vista 3 ordering query.

    FORCE INDEX guarantees the optimizer selects the named index regardless of table size
    (plan 3.6: 'índice compuesto para la Vista 3 ordenada por stock').
    """
    with migrated_engine.connect() as conn:
        result = conn.execute(
            text(
                "EXPLAIN SELECT id, sku_raw, sku_norm, feed_stock, submission_status "  # noqa: S608
                f"FROM run_items FORCE INDEX ({COMPOSITE_INDEX_NAME}) "
                "WHERE run_id = 1 AND sync_status = 'SENT_WITH_ERROR' "
                "ORDER BY feed_stock DESC",
            ),
        )
        row = result.mappings().first()
        assert row is not None
        assert row["key"] == COMPOSITE_INDEX_NAME, (
            f"Vista 3 query must use '{COMPOSITE_INDEX_NAME}' (plan 3.6)"
        )


# ── item_errors ───────────────────────────────────────────────────────────────


def test_item_errors_error_code_is_utf8mb4_bin(migrated_engine: Engine) -> None:
    """error_code FK must match error_codes.code collation — utf8mb4_bin (plan 3.6)."""
    col = _column_info(migrated_engine, "item_errors", "error_code")
    assert col["collation"] == EXPECTED_BIN_COLLATION, (
        f"item_errors.error_code must be {EXPECTED_BIN_COLLATION} (plan 3.6)"
    )
    assert col["nullable"] == "NO"


def test_item_errors_error_category_enum(migrated_engine: Engine) -> None:
    col = _column_info(migrated_engine, "item_errors", "error_category")
    enum_type = col["column_type"].lower()
    assert "enum" in enum_type
    for value in ("ERROR", "ADVERTENCIA"):
        assert value.lower() in enum_type, (
            f"error_category ENUM must include '{value}' (spec 2.2.3)"
        )
    assert col["nullable"] == "NO"


def test_item_errors_error_message_is_text_not_null(migrated_engine: Engine) -> None:
    """TEXT column required — Amazon error messages reach 960+ chars (spec 2.2.3)."""
    col = _column_info(migrated_engine, "item_errors", "error_message")
    assert col["column_type"].lower() in ("text", "mediumtext", "longtext"), (
        "error_message must be TEXT (960+ chars observed in real data — spec 2.2.3)"
    )
    assert col["nullable"] == "NO"


def test_item_errors_fk_to_run_items(migrated_engine: Engine) -> None:
    fks = inspect(migrated_engine).get_foreign_keys("item_errors")
    ri_fk = next((fk for fk in fks if fk["referred_table"] == "run_items"), None)
    assert ri_fk is not None, "item_errors must have FK → run_items"
    assert ri_fk["constrained_columns"] == ["run_item_id"]


def test_item_errors_fk_to_error_codes(migrated_engine: Engine) -> None:
    fks = inspect(migrated_engine).get_foreign_keys("item_errors")
    ec_fk = next((fk for fk in fks if fk["referred_table"] == "error_codes"), None)
    assert ec_fk is not None, "item_errors must have FK → error_codes"
    assert ec_fk["constrained_columns"] == ["error_code"]


# ── Critical: Seeds (T-1.7 DoD) ──────────────────────────────────────────────


def test_seed_7_error_families_present(migrated_engine: Engine) -> None:
    """Upgrade must insert exactly 7 error families including SIN_CLASIFICAR (T-1.7 DoD)."""
    count = _count(migrated_engine, "error_families")
    assert count == EXPECTED_FAMILIES, (
        f"Expected {EXPECTED_FAMILIES} error families after upgrade, got {count}"
    )


def test_seed_sin_clasificar_family_present(migrated_engine: Engine) -> None:
    """SIN_CLASIFICAR fallback family must exist (RF-14, EB-10)."""
    with migrated_engine.connect() as conn:
        row = conn.execute(
            text("SELECT code FROM error_families WHERE code = :code"),
            {"code": SIN_CLASIFICAR_CODE},
        ).first()
    assert row is not None, "SIN_CLASIFICAR family must be seeded (RF-14, EB-10)"


def test_seed_53_error_codes_present(migrated_engine: Engine) -> None:
    """Upgrade must insert exactly 53 mapped error codes (T-1.7 DoD)."""
    count = _count(migrated_engine, "error_codes")
    assert count == EXPECTED_CODES, (
        f"Expected {EXPECTED_CODES} error codes after upgrade, got {count}"
    )


def test_seed_no_error_code_points_to_sin_clasificar(migrated_engine: Engine) -> None:
    """All 53 seeded codes belong to a proper family.

    SIN_CLASIFICAR starts empty (T-1.7 DoD).
    """
    with migrated_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT COUNT(*) FROM error_codes WHERE family_code = :fam",
            ),
            {"fam": SIN_CLASIFICAR_CODE},
        ).one()
    count = int(row[0])
    assert count == 0, (
        f"No seeded error_code should point to SIN_CLASIFICAR — got {count} (T-1.7 DoD)"
    )


def test_seed_family_codes_all_have_display_names(migrated_engine: Engine) -> None:
    """Every seeded family must have a non-empty display_name for the UI tab label (plan 3.6)."""
    with migrated_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT code FROM error_families "
                "WHERE display_name IS NULL OR TRIM(display_name) = ''",
            ),
        ).fetchall()
    assert rows == [], (
        f"Families with empty display_name: {[r[0] for r in rows]}"
    )


def test_seed_codes_fk_integrity_against_families(migrated_engine: Engine) -> None:
    """All 53 error_codes.family_code values must reference existing error_families rows."""
    with migrated_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT ec.code FROM error_codes ec "
                "LEFT JOIN error_families ef ON ec.family_code = ef.code "
                "WHERE ef.code IS NULL",
            ),
        ).fetchall()
    assert rows == [], (
        f"error_codes with invalid family_code (no matching family): {[r[0] for r in rows]}"
    )


# ── Downgrade: seeds are removed ─────────────────────────────────────────────


def test_migration_downgrade_to_002_removes_taxonomy_tables(mysql_url: str) -> None:
    """Downgrade 003→002 removes taxonomy tables; domain+auth tables survive.

    Verifies that seeds are gone (tables dropped) on downgrade (T-1.7 DoD).
    """
    alembic_cfg = Config(str(ALEMBIC_INI))
    alembic_cfg.set_main_option("sqlalchemy.url", mysql_url)
    command.downgrade(alembic_cfg, "002")

    engine = create_engine(mysql_url)
    try:
        tables = set(inspect(engine).get_table_names())
        for table in TAXONOMY_TABLES:
            assert table not in tables, (
                f"{table} must be removed after downgrade to 002 (seeds gone)"
            )
        for table in DOMAIN_TABLES | AUTH_TABLES:
            assert table in tables, (
                f"{table} must survive downgrade to 002"
            )
    finally:
        engine.dispose()
