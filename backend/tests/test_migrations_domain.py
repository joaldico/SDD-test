"""Migration tests for T-1.6 — reconciliation_runs, source_files, column_mappings (plan 3.6).

TDD gate: written BEFORE the Alembic migration and ORM models exist.
Runs against an ephemeral MySQL 8 container (testcontainers).

Verifies:
  - Tables are created with correct types, collations, and constraints.
  - UNIQUE(run_id, role) in source_files rejects duplicates (plan 3.6, RF-10).
  - UNIQUE(source_file_id, logical_field) in column_mappings rejects duplicates (plan 3.6, RF-10).
  - status column on reconciliation_runs is indexed for polling (ADR-002, plan 3.6).
  - FKs are wired correctly.
  - Downgrade 002→001 removes domain tables while leaving auth tables intact.
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
from sqlalchemy.exc import IntegrityError
from testcontainers.mysql import MySqlContainer

from marketplace_conciliator.platform.db.url import to_sync_url

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"

EXPECTED_TABLE_COLLATION = "utf8mb4_0900_ai_ci"


class _ColumnInfo(TypedDict):
    column_type: str
    collation: str | None
    nullable: str
    key: str
    extra: str


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def mysql_url() -> Generator[str, None, None]:
    """Ephemeral MySQL 8 with the same charset/collation as docker-compose (plan 3.6)."""
    container = MySqlContainer("mysql:8").with_command(
        "--character-set-server=utf8mb4 "
        "--collation-server=utf8mb4_0900_ai_ci "
        "--default-time-zone=+00:00",
    )
    with container as mysql:
        yield to_sync_url(mysql.get_connection_url())


@pytest.fixture(scope="module")
def migrated_engine(mysql_url: str) -> Generator[Engine, None, None]:
    """Engine with migrations 001+002 applied (upgrade head)."""
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


# ── Table existence ───────────────────────────────────────────────────────────


def test_migration_upgrade_creates_domain_tables(migrated_engine: Engine) -> None:
    tables = set(inspect(migrated_engine).get_table_names())
    assert {"reconciliation_runs", "source_files", "column_mappings"}.issubset(tables)


def test_auth_tables_still_present_after_002(migrated_engine: Engine) -> None:
    tables = set(inspect(migrated_engine).get_table_names())
    assert {"users", "refresh_tokens"}.issubset(tables)


# ── Collations ────────────────────────────────────────────────────────────────


def test_domain_tables_use_utf8mb4_global_collation(migrated_engine: Engine) -> None:
    for table in ("reconciliation_runs", "source_files", "column_mappings"):
        assert _table_collation(migrated_engine, table) == EXPECTED_TABLE_COLLATION, (
            f"{table} must use {EXPECTED_TABLE_COLLATION} (plan 3.6 global charset)"
        )


# ── reconciliation_runs ───────────────────────────────────────────────────────


def test_reconciliation_runs_id_is_bigint_unsigned_pk(migrated_engine: Engine) -> None:
    col = _column_info(migrated_engine, "reconciliation_runs", "id")
    assert "bigint" in col["column_type"].lower()
    assert "unsigned" in col["column_type"].lower()
    assert col["extra"] == "auto_increment"
    assert col["key"] == "PRI"


def test_reconciliation_runs_status_enum_values_and_not_null(migrated_engine: Engine) -> None:
    col = _column_info(migrated_engine, "reconciliation_runs", "status")
    enum_type = col["column_type"].lower()
    assert "enum" in enum_type
    for value in ("uploaded", "mapping", "processing", "completed", "failed"):
        assert value in enum_type, f"ENUM must include '{value}' (plan 3.6)"
    assert col["nullable"] == "NO"


def test_reconciliation_runs_status_is_indexed(migrated_engine: Engine) -> None:
    """Status INDEX required for polling queries (ADR-002, plan 3.6)."""
    indexes = inspect(migrated_engine).get_indexes("reconciliation_runs")
    status_indexes = [idx for idx in indexes if "status" in idx["column_names"]]
    assert status_indexes, "status must be indexed on reconciliation_runs (plan 3.6)"


def test_reconciliation_runs_summary_metrics_is_json_nullable(migrated_engine: Engine) -> None:
    col = _column_info(migrated_engine, "reconciliation_runs", "summary_metrics")
    assert col["column_type"].lower() == "json"
    assert col["nullable"] == "YES"


def test_reconciliation_runs_created_at_not_null_completed_at_nullable(
    migrated_engine: Engine,
) -> None:
    created = _column_info(migrated_engine, "reconciliation_runs", "created_at")
    assert created["column_type"] == "datetime(6)"
    assert created["nullable"] == "NO"

    completed = _column_info(migrated_engine, "reconciliation_runs", "completed_at")
    assert completed["column_type"] == "datetime(6)"
    assert completed["nullable"] == "YES"


def test_reconciliation_runs_fk_to_users(migrated_engine: Engine) -> None:
    fks = inspect(migrated_engine).get_foreign_keys("reconciliation_runs")
    user_fk = next((fk for fk in fks if fk["referred_table"] == "users"), None)
    assert user_fk is not None, "reconciliation_runs must have FK to users"
    assert user_fk["constrained_columns"] == ["user_id"]
    assert user_fk["referred_columns"] == ["id"]


# ── source_files ──────────────────────────────────────────────────────────────


def test_source_files_role_enum_values_and_not_null(migrated_engine: Engine) -> None:
    col = _column_info(migrated_engine, "source_files", "role")
    enum_type = col["column_type"].lower()
    assert "enum" in enum_type
    for value in ("occ_top", "wm_feed", "amazon_report"):
        assert value in enum_type, f"role ENUM must include '{value}' (plan 3.6)"
    assert col["nullable"] == "NO"


def test_source_files_sha256_is_char64_not_null(migrated_engine: Engine) -> None:
    col = _column_info(migrated_engine, "source_files", "sha256")
    assert col["column_type"] == "char(64)"
    assert col["nullable"] == "NO"


def test_source_files_total_rows_and_discarded_rows_not_null(migrated_engine: Engine) -> None:
    for colname in ("total_rows", "discarded_rows"):
        col = _column_info(migrated_engine, "source_files", colname)
        assert "int" in col["column_type"].lower(), f"{colname} must be INT type"
        assert col["nullable"] == "NO", f"{colname} must be NOT NULL (RN-06, EB-02)"


def test_source_files_optional_columns_are_nullable(migrated_engine: Engine) -> None:
    for colname in ("detected_encoding", "detected_delimiter", "sheet_name", "data_start_row"):
        col = _column_info(migrated_engine, "source_files", colname)
        assert col["nullable"] == "YES", f"{colname} must be nullable (plan 3.6)"


def test_source_files_fk_to_reconciliation_runs(migrated_engine: Engine) -> None:
    fks = inspect(migrated_engine).get_foreign_keys("source_files")
    run_fk = next((fk for fk in fks if fk["referred_table"] == "reconciliation_runs"), None)
    assert run_fk is not None, "source_files must have FK to reconciliation_runs"
    assert run_fk["constrained_columns"] == ["run_id"]
    assert run_fk["referred_columns"] == ["id"]


# ── column_mappings ───────────────────────────────────────────────────────────


def test_column_mappings_logical_field_enum_values_and_not_null(migrated_engine: Engine) -> None:
    col = _column_info(migrated_engine, "column_mappings", "logical_field")
    enum_type = col["column_type"].lower()
    assert "enum" in enum_type
    logical_field_values = (
        "sku", "stock", "error_code", "error_category", "error_message", "affected_field",
    )
    for value in logical_field_values:
        assert value in enum_type, f"logical_field ENUM must include '{value}' (plan 3.6)"
    assert col["nullable"] == "NO"


def test_column_mappings_was_suggested_is_boolean_not_null(migrated_engine: Engine) -> None:
    col = _column_info(migrated_engine, "column_mappings", "was_suggested")
    assert col["column_type"].lower() in ("tinyint(1)", "tinyint", "boolean", "bit(1)")
    assert col["nullable"] == "NO"


def test_column_mappings_confirmed_at_not_null(migrated_engine: Engine) -> None:
    col = _column_info(migrated_engine, "column_mappings", "confirmed_at")
    assert col["column_type"] == "datetime(6)"
    assert col["nullable"] == "NO"


def test_column_mappings_fk_to_source_files(migrated_engine: Engine) -> None:
    fks = inspect(migrated_engine).get_foreign_keys("column_mappings")
    sf_fk = next((fk for fk in fks if fk["referred_table"] == "source_files"), None)
    assert sf_fk is not None, "column_mappings must have FK to source_files"
    assert sf_fk["constrained_columns"] == ["source_file_id"]
    assert sf_fk["referred_columns"] == ["id"]


def test_column_mappings_fk_confirmed_by_to_users(migrated_engine: Engine) -> None:
    fks = inspect(migrated_engine).get_foreign_keys("column_mappings")
    user_fk = next((fk for fk in fks if fk["referred_table"] == "users"), None)
    assert user_fk is not None, "column_mappings must have FK confirmed_by → users"
    assert user_fk["constrained_columns"] == ["confirmed_by"]
    assert user_fk["referred_columns"] == ["id"]


# ── Critical: composite UNIQUE constraints (DoD T-1.6) ────────────────────────


def test_source_files_unique_constraint_run_id_role_reported(migrated_engine: Engine) -> None:
    """Inspector confirms UNIQUE(run_id, role) exists in source_files (plan 3.6)."""
    ucs = inspect(migrated_engine).get_unique_constraints("source_files")
    col_sets = [set(uc["column_names"]) for uc in ucs]
    assert {"run_id", "role"} in col_sets, (
        "UNIQUE(run_id, role) must be declared in source_files (plan 3.6)"
    )


def test_column_mappings_unique_constraint_source_file_id_logical_field_reported(
    migrated_engine: Engine,
) -> None:
    """Inspector confirms UNIQUE(source_file_id, logical_field) in column_mappings (plan 3.6)."""
    ucs = inspect(migrated_engine).get_unique_constraints("column_mappings")
    col_sets = [set(uc["column_names"]) for uc in ucs]
    assert {"source_file_id", "logical_field"} in col_sets, (
        "UNIQUE(source_file_id, logical_field) must be declared in column_mappings (plan 3.6)"
    )


def test_source_files_unique_run_id_role_rejects_duplicate(migrated_engine: Engine) -> None:
    """UNIQUE(run_id, role) must raise IntegrityError on a duplicate (run_id, role) pair."""
    with migrated_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (email, password_hash, role, created_at) "
                "VALUES ('unique_sf_test@example.com', 'x', 'operator', NOW(6))",
            ),
        )
        uid = conn.execute(
            text("SELECT id FROM users WHERE email = 'unique_sf_test@example.com'"),
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO reconciliation_runs "
                "(user_id, marketplace, status, created_at) "
                "VALUES (:uid, 'amazon_es', 'uploaded', NOW(6))",
            ),
            {"uid": uid},
        )
        run_id = conn.execute(text("SELECT LAST_INSERT_ID()")).scalar_one()
        conn.execute(
            text(
                "INSERT INTO source_files "
                "(run_id, role, original_filename, sha256, "
                "total_rows, discarded_rows, uploaded_at) "
                "VALUES (:run_id, 'occ_top', 'first.xlsx', :sha, 100, 0, NOW(6))",
            ),
            {"run_id": run_id, "sha": "a" * 64},
        )

    with pytest.raises(IntegrityError), migrated_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO source_files "
                "(run_id, role, original_filename, sha256, "
                "total_rows, discarded_rows, uploaded_at) "
                "VALUES (:run_id, 'occ_top', 'duplicate.xlsx', :sha, 50, 0, NOW(6))",
            ),
            {"run_id": run_id, "sha": "b" * 64},
        )


def test_column_mappings_unique_source_file_id_logical_field_rejects_duplicate(
    migrated_engine: Engine,
) -> None:
    """UNIQUE(source_file_id, logical_field) must raise IntegrityError on duplicate mapping."""
    with migrated_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (email, password_hash, role, created_at) "
                "VALUES ('unique_cm_test@example.com', 'x', 'operator', NOW(6))",
            ),
        )
        uid = conn.execute(
            text("SELECT id FROM users WHERE email = 'unique_cm_test@example.com'"),
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO reconciliation_runs "
                "(user_id, marketplace, status, created_at) "
                "VALUES (:uid, 'amazon_es', 'mapping', NOW(6))",
            ),
            {"uid": uid},
        )
        run_id = conn.execute(text("SELECT LAST_INSERT_ID()")).scalar_one()
        conn.execute(
            text(
                "INSERT INTO source_files "
                "(run_id, role, original_filename, sha256, "
                "total_rows, discarded_rows, uploaded_at) "
                "VALUES (:run_id, 'wm_feed', 'feed.csv', :sha, 200, 1, NOW(6))",
            ),
            {"run_id": run_id, "sha": "c" * 64},
        )
        sf_id = conn.execute(text("SELECT LAST_INSERT_ID()")).scalar_one()
        conn.execute(
            text(
                "INSERT INTO column_mappings "
                "(source_file_id, logical_field, source_column_name, source_column_index, "
                "was_suggested, confirmed_by, confirmed_at) "
                "VALUES (:sfid, 'sku', 'SKU Col', 3, 1, :uid, NOW(6))",
            ),
            {"sfid": sf_id, "uid": uid},
        )

    # sf_id and uid are in function scope from the setup block above.
    with pytest.raises(IntegrityError), migrated_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO column_mappings "
                "(source_file_id, logical_field, source_column_name, source_column_index, "
                "was_suggested, confirmed_by, confirmed_at) "
                "VALUES (:sfid, 'sku', 'Duplicate SKU', 5, 0, :uid, NOW(6))",
            ),
            {"sfid": sf_id, "uid": uid},
        )


# ── Downgrade ─────────────────────────────────────────────────────────────────


def test_migration_downgrade_to_001_removes_domain_tables(mysql_url: str) -> None:
    """Downgrade 002→001 drops domain tables but leaves auth tables intact (reversibility)."""
    alembic_cfg = Config(str(ALEMBIC_INI))
    alembic_cfg.set_main_option("sqlalchemy.url", mysql_url)
    command.downgrade(alembic_cfg, "001")

    engine = create_engine(mysql_url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert "column_mappings" not in tables
        assert "source_files" not in tables
        assert "reconciliation_runs" not in tables
        assert "users" in tables, "users must survive downgrade to 001"
        assert "refresh_tokens" in tables, "refresh_tokens must survive downgrade to 001"
    finally:
        engine.dispose()
