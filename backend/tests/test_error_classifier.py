"""T-4.4 — Tests for error_classifier module (TDD — red → green → refactor).

Covers:
  1. normalise_error_message strips NBSP (U+00A0) and trims whitespace (EB-05/EB-10).
  2. classify_error_rows assigns family_code from the error_codes catalogue.
  3. Unknown codes are auto-inserted into error_codes with family='SIN_CLASIFICAR'
     and a non-null first_seen_at (EB-10, RF-14).
  4. A SKU with 11 distinct error rows produces exactly 11 item_error records.

All tests use an in-memory SQLite database that mirrors the relevant columns
of the production MySQL schema (no Docker dependency).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from marketplace_conciliator.reconciliation.error_classifier import (
    ErrorRow,
    classify_and_insert_errors,
    normalise_error_message,
)

# ---------------------------------------------------------------------------
# In-memory SQLite schema fixture
# ---------------------------------------------------------------------------

_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(_ENGINE, "connect")
def _set_fk(dbapi_conn: Any, _: Any) -> None:  # noqa: ANN401
    dbapi_conn.cursor().execute("PRAGMA foreign_keys=ON")


with _ENGINE.begin() as _c:
    _c.execute(text("""
        CREATE TABLE error_families (
            code TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            description TEXT,
            sort_order INTEGER NOT NULL DEFAULT 99
        )
    """))
    _c.execute(text("""
        INSERT INTO error_families (code, display_name, sort_order) VALUES
            ('SIN_CLASIFICAR', 'Sin clasificar', 99),
            ('AUTORIZACION_MARCA', 'Autorización de marca', 1)
    """))
    _c.execute(text("""
        CREATE TABLE error_codes (
            code TEXT PRIMARY KEY,
            family_code TEXT NOT NULL DEFAULT 'SIN_CLASIFICAR'
                REFERENCES error_families(code),
            default_category TEXT,
            canonical_message TEXT,
            first_seen_at DATETIME
        )
    """))
    # Seed one known code mapped to a real family
    _c.execute(text("""
        INSERT INTO error_codes (code, family_code) VALUES
            ('18299', 'AUTORIZACION_MARCA')
    """))
    _c.execute(text("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL,
            hashed_password TEXT NOT NULL
        )
    """))
    _c.execute(text("""
        INSERT INTO users (id, email, role, hashed_password)
        VALUES (1, 'test@example.com', 'admin', 'dummy')
    """))
    _c.execute(text("""
        CREATE TABLE reconciliation_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            marketplace TEXT NOT NULL DEFAULT 'amazon_es',
            status TEXT NOT NULL,
            phase TEXT,
            failure_reason TEXT,
            summary_metrics TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME
        )
    """))
    _c.execute(text("""
        CREATE TABLE source_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL REFERENCES reconciliation_runs(id),
            role TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            detected_encoding TEXT,
            detected_delimiter TEXT,
            sheet_name TEXT,
            data_start_row INTEGER,
            total_rows INTEGER NOT NULL DEFAULT 0,
            discarded_rows INTEGER NOT NULL DEFAULT 0,
            uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (run_id, role)
        )
    """))
    _c.execute(text("""
        CREATE TABLE run_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL REFERENCES reconciliation_runs(id),
            sku_norm TEXT NOT NULL,
            sku_raw TEXT NOT NULL,
            in_occ INTEGER NOT NULL DEFAULT 0,
            in_feed INTEGER NOT NULL DEFAULT 0,
            in_amazon_report INTEGER NOT NULL DEFAULT 0,
            sync_status TEXT NOT NULL DEFAULT 'SENT_WITH_ERROR',
            feed_stock INTEGER,
            occ_stock INTEGER,
            stock_conflict INTEGER NOT NULL DEFAULT 0,
            submission_status TEXT,
            UNIQUE (run_id, sku_norm)
        )
    """))
    _c.execute(text("""
        CREATE TABLE item_errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_item_id INTEGER NOT NULL REFERENCES run_items(id),
            error_code TEXT NOT NULL REFERENCES error_codes(code),
            error_category TEXT NOT NULL DEFAULT 'ERROR',
            error_message TEXT NOT NULL,
            affected_field TEXT
        )
    """))

_SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=_ENGINE)


@pytest.fixture()
def db() -> Session:  # type: ignore[override]
    """Per-test session that rolls back after each test to keep DB clean."""
    session = _SessionFactory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def run_with_item(db: Session) -> dict[str, int]:
    """Create a minimal reconciliation_run + run_item for tests that need IDs."""
    db.execute(
        text(
            "INSERT INTO reconciliation_runs (user_id, marketplace, status) "
            "VALUES (1, 'amazon_es', 'processing')",
        ),
    )
    run_id = db.execute(text("SELECT last_insert_rowid()")).scalar()
    db.execute(
        text(
            "INSERT INTO run_items "
            "  (run_id, sku_norm, sku_raw, in_amazon_report, sync_status) "
            "VALUES (:run_id, 'S01098S3MRN', 'S01098S3MRN', 1, 'SENT_WITH_ERROR')",
        ),
        {"run_id": run_id},
    )
    item_id = db.execute(text("SELECT last_insert_rowid()")).scalar()
    db.flush()
    return {"run_id": int(run_id), "item_id": int(item_id)}


# ===========================================================================
# 1. NBSP normalisation in error messages
# ===========================================================================


class TestNormaliseErrorMessage:
    def test_strips_nbsp_from_message(self) -> None:
        msg = "Error\u00a0de\u00a0autorización"
        result = normalise_error_message(msg)
        assert "\u00a0" not in result
        assert "Error de autorización" == result

    def test_strips_leading_trailing_nbsp(self) -> None:
        assert normalise_error_message("\u00a0  hello  \u00a0") == "hello"

    def test_collapses_internal_whitespace_after_nbsp_strip(self) -> None:
        # NBSP in the middle becomes a regular space; consecutive spaces collapse to one
        msg = "field\u00a0 \u00a0value"
        result = normalise_error_message(msg)
        assert "  " not in result

    def test_plain_string_unchanged_except_strip(self) -> None:
        assert normalise_error_message("  hello world  ") == "hello world"

    def test_empty_string_returns_empty(self) -> None:
        assert normalise_error_message("") == ""


# ===========================================================================
# 2. classify_and_insert_errors — known code uses existing family
# ===========================================================================


class TestClassifyKnownCode:
    def test_known_code_not_re_inserted(self, db: Session, run_with_item: dict[str, int]) -> None:
        """Code '18299' (AUTORIZACION_MARCA) must NOT be auto-inserted."""
        rows: list[ErrorRow] = [
            ErrorRow(
                sku_norm="S01098S3MRN",
                error_code="18299",
                error_category="ERROR",
                error_message="Brand authorization required",
                affected_field="brand",
            ),
        ]
        classify_and_insert_errors(db, run_with_item["run_id"], rows)

        # Verify the code still maps to its original family (not overwritten)
        family = db.execute(
            text("SELECT family_code FROM error_codes WHERE code = '18299'"),
        ).scalar()
        assert family == "AUTORIZACION_MARCA"

    def test_known_code_item_error_inserted(
        self, db: Session, run_with_item: dict[str, int],
    ) -> None:
        rows: list[ErrorRow] = [
            ErrorRow(
                sku_norm="S01098S3MRN",
                error_code="18299",
                error_category="ERROR",
                error_message="Brand authorization required",
                affected_field="brand",
            ),
        ]
        classify_and_insert_errors(db, run_with_item["run_id"], rows)

        count = db.execute(
            text(
                "SELECT COUNT(*) FROM item_errors WHERE run_item_id = :rid",
            ),
            {"rid": run_with_item["item_id"]},
        ).scalar()
        assert count == 1


# ===========================================================================
# 3. Auto-insert of unknown codes → SIN_CLASIFICAR + first_seen_at
# ===========================================================================


class TestUnknownCodeAutoInsert:
    def test_unknown_code_inserted_with_sin_clasificar(
        self, db: Session, run_with_item: dict[str, int],
    ) -> None:
        """Injecting code '99999' must create a new error_codes row with SIN_CLASIFICAR."""
        rows: list[ErrorRow] = [
            ErrorRow(
                sku_norm="S01098S3MRN",
                error_code="99999",
                error_category="ERROR",
                error_message="Unknown error type",
                affected_field=None,
            ),
        ]
        classify_and_insert_errors(db, run_with_item["run_id"], rows)

        row = db.execute(
            text(
                "SELECT family_code, first_seen_at FROM error_codes WHERE code = '99999'",
            ),
        ).fetchone()
        assert row is not None, "Code '99999' must be auto-inserted into error_codes"
        assert row[0] == "SIN_CLASIFICAR"
        assert row[1] is not None, "first_seen_at must be set for auto-inserted codes"

    def test_first_seen_at_is_a_valid_datetime(
        self, db: Session, run_with_item: dict[str, int],
    ) -> None:
        rows: list[ErrorRow] = [
            ErrorRow(
                sku_norm="S01098S3MRN",
                error_code="88888",
                error_category="ADVERTENCIA",
                error_message="Some warning",
                affected_field="title",
            ),
        ]
        classify_and_insert_errors(db, run_with_item["run_id"], rows)

        raw_ts = db.execute(
            text("SELECT first_seen_at FROM error_codes WHERE code = '88888'"),
        ).scalar()
        assert raw_ts is not None
        # Must be parseable as ISO datetime
        dt = datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00"))
        assert isinstance(dt, datetime)

    def test_repeated_unknown_code_not_duplicated(
        self, db: Session, run_with_item: dict[str, int],
    ) -> None:
        """Calling classify twice for the same unknown code must not raise / duplicate."""
        rows: list[ErrorRow] = [
            ErrorRow(
                sku_norm="S01098S3MRN",
                error_code="77777",
                error_category="ERROR",
                error_message="Error A",
                affected_field=None,
            ),
            ErrorRow(
                sku_norm="S01098S3MRN",
                error_code="77777",
                error_category="ERROR",
                error_message="Error B",
                affected_field=None,
            ),
        ]
        classify_and_insert_errors(db, run_with_item["run_id"], rows)

        code_count = db.execute(
            text("SELECT COUNT(*) FROM error_codes WHERE code = '77777'"),
        ).scalar()
        assert code_count == 1, "error_codes must have exactly one row for '77777'"

        # Both item_errors rows must still be inserted (distinct messages)
        err_count = db.execute(
            text(
                "SELECT COUNT(*) FROM item_errors WHERE run_item_id = :rid",
            ),
            {"rid": run_with_item["item_id"]},
        ).scalar()
        assert err_count == 2


# ===========================================================================
# 4. A SKU with 11 distinct error rows → exactly 11 item_errors
# ===========================================================================


class TestElevenErrors:
    def test_eleven_errors_all_persisted(
        self, db: Session, run_with_item: dict[str, int],
    ) -> None:
        """S01098S3MRN with 11 different error rows must produce 11 item_errors."""
        rows: list[ErrorRow] = [
            ErrorRow(
                sku_norm="S01098S3MRN",
                error_code=f"1{8299 + i:04d}",
                error_category="ERROR",
                error_message=f"Error message número {i} para S01098S3MRN",
                affected_field=f"attribute_{i}",
            )
            for i in range(1, 12)
        ]
        classify_and_insert_errors(db, run_with_item["run_id"], rows)

        count = db.execute(
            text(
                "SELECT COUNT(*) FROM item_errors WHERE run_item_id = :rid",
            ),
            {"rid": run_with_item["item_id"]},
        ).scalar()
        assert count == 11, f"Expected 11 item_errors, found {count}"

    def test_eleven_errors_nbsp_normalised_in_messages(
        self, db: Session, run_with_item: dict[str, int],
    ) -> None:
        """NBSP in error messages must be stripped before persistence."""
        rows: list[ErrorRow] = [
            ErrorRow(
                sku_norm="S01098S3MRN",
                error_code="18299",
                error_category="ERROR",
                error_message="Error\u00a0de\u00a0autorización\u00a0de\u00a0marca",
                affected_field="brand",
            ),
        ]
        classify_and_insert_errors(db, run_with_item["run_id"], rows)

        msg = db.execute(
            text(
                "SELECT error_message FROM item_errors WHERE run_item_id = :rid",
            ),
            {"rid": run_with_item["item_id"]},
        ).scalar()
        assert msg is not None
        assert "\u00a0" not in str(msg), "NBSP must be normalised in persisted error_message"
