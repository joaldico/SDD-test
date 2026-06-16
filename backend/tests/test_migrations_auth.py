"""Migration tests for T-1.5 — users and refresh_tokens (plan 3.6).

TDD gate: written before the Alembic migration exists.
Runs against an ephemeral MySQL 8 container (testcontainers).
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


class _ColumnInfo(TypedDict):
    column_type: str
    collation: str | None
    nullable: str
    key: str
    extra: str


@pytest.fixture(scope="module")
def mysql_url() -> Generator[str, None, None]:
    """Ephemeral MySQL 8 with the same charset/collation as docker-compose (plan 3.6)."""
    container = (
        MySqlContainer("mysql:8")
        .with_command(
            "--character-set-server=utf8mb4 "
            "--collation-server=utf8mb4_0900_ai_ci "
            "--default-time-zone=+00:00",
        )
    )
    with container as mysql:
        yield to_sync_url(mysql.get_connection_url())


@pytest.fixture(scope="module")
def migrated_engine(mysql_url: str) -> Generator[Engine, None, None]:
    """Engine with migration 001 applied (upgrade head)."""
    alembic_cfg = Config(str(ALEMBIC_INI))
    alembic_cfg.set_main_option("sqlalchemy.url", mysql_url)
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(mysql_url)
    yield engine
    engine.dispose()


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


def test_migration_upgrade_creates_users_and_refresh_tokens(
    migrated_engine: Engine,
) -> None:
    tables = set(inspect(migrated_engine).get_table_names())
    assert {"users", "refresh_tokens"}.issubset(tables)


def test_tables_use_utf8mb4_global_collation(migrated_engine: Engine) -> None:
    for table in ("users", "refresh_tokens"):
        assert _table_collation(migrated_engine, table) == EXPECTED_TABLE_COLLATION


def test_users_columns_match_physical_model(migrated_engine: Engine) -> None:
    id_col = _column_info(migrated_engine, "users", "id")
    assert "bigint" in id_col["column_type"].lower()
    assert "unsigned" in id_col["column_type"].lower()
    assert id_col["extra"] == "auto_increment"
    assert id_col["key"] == "PRI"

    email_col = _column_info(migrated_engine, "users", "email")
    assert email_col["column_type"] == "varchar(255)"
    assert email_col["collation"] == EXPECTED_TABLE_COLLATION
    assert email_col["nullable"] == "NO"
    assert email_col["key"] == "UNI"

    role_col = _column_info(migrated_engine, "users", "role")
    assert "enum('admin','operator')" in role_col["column_type"].replace(" ", "").lower()
    assert role_col["nullable"] == "NO"

    created_at = _column_info(migrated_engine, "users", "created_at")
    assert created_at["column_type"] == "datetime(6)"
    assert created_at["nullable"] == "NO"


def test_refresh_tokens_columns_match_physical_model(migrated_engine: Engine) -> None:
    token_hash = _column_info(migrated_engine, "refresh_tokens", "token_hash")
    assert token_hash["column_type"] == "char(64)"
    assert token_hash["collation"] == "ascii_bin"
    assert token_hash["nullable"] == "NO"
    assert token_hash["key"] == "UNI"

    family_id = _column_info(migrated_engine, "refresh_tokens", "family_id")
    assert family_id["column_type"] == "char(36)"
    assert family_id["collation"] == EXPECTED_TABLE_COLLATION
    assert family_id["nullable"] == "NO"
    assert family_id["key"] == "MUL"

    expires_at = _column_info(migrated_engine, "refresh_tokens", "expires_at")
    assert expires_at["column_type"] == "datetime(6)"
    assert expires_at["nullable"] == "NO"

    replaced_by = _column_info(migrated_engine, "refresh_tokens", "replaced_by")
    assert "bigint" in replaced_by["column_type"].lower()
    assert replaced_by["nullable"] == "YES"

    revoked_at = _column_info(migrated_engine, "refresh_tokens", "revoked_at")
    assert revoked_at["column_type"] == "datetime(6)"
    assert revoked_at["nullable"] == "YES"


def test_refresh_tokens_foreign_keys(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    fks = {fk["name"]: fk for fk in inspector.get_foreign_keys("refresh_tokens")}

    user_fk = next(fk for fk in fks.values() if fk["referred_table"] == "users")
    assert user_fk["constrained_columns"] == ["user_id"]
    assert user_fk["referred_columns"] == ["id"]

    self_fk = next(fk for fk in fks.values() if fk["referred_table"] == "refresh_tokens")
    assert self_fk["constrained_columns"] == ["replaced_by"]
    assert self_fk["referred_columns"] == ["id"]


def test_refresh_tokens_family_id_index(migrated_engine: Engine) -> None:
    indexes = {idx["name"]: idx for idx in inspect(migrated_engine).get_indexes("refresh_tokens")}
    family_indexes = [
        idx for idx in indexes.values() if "family_id" in idx["column_names"]
    ]
    assert family_indexes, "family_id must be indexed (plan 3.6 / ADR-003)"


def test_migration_downgrade_removes_tables(mysql_url: str) -> None:
    """Downgrade base on the shared ephemeral DB removes users and refresh_tokens."""
    alembic_cfg = Config(str(ALEMBIC_INI))
    alembic_cfg.set_main_option("sqlalchemy.url", mysql_url)

    command.downgrade(alembic_cfg, "base")

    engine = create_engine(mysql_url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert "users" not in tables
        assert "refresh_tokens" not in tables
    finally:
        engine.dispose()
