"""T-4.5 — Tests for transactional batch persistence (TDD — red → green → refactor).

Covers:
  1. Happy path: run_items + item_errors written atomically; run → completed;
     summary_metrics JSON populated; completed_at set.
  2. Rollback: simulating a write failure mid-batch leaves no orphan rows and
     marks the run as failed.
  3. summary_metrics keys match spec (total_skus, sent_with_error, sent_ok,
     not_sent, desync_feed_only, desync_amazon_only, total_errors).

All tests use an in-memory SQLite DB that mirrors the relevant subset of the
production schema (no Docker dependency).
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from marketplace_conciliator.reconciliation.persistence import (
    RunItemData,
    persist_run_results,
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
            ('SIN_CLASIFICAR', 'Sin clasificar', 99)
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
            header_fingerprint TEXT,
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
            sync_status TEXT NOT NULL DEFAULT 'NOT_SENT',
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
    session = _SessionFactory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def fresh_run_id(db: Session) -> int:
    """Create a run in 'processing' status and return its ID."""
    db.execute(
        text(
            "INSERT INTO reconciliation_runs (user_id, marketplace, status) "
            "VALUES (1, 'amazon_es', 'processing')",
        ),
    )
    run_id = db.execute(text("SELECT last_insert_rowid()")).scalar()
    db.flush()
    return int(run_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_items(n: int, status: str = "NOT_SENT") -> list[RunItemData]:
    return [
        RunItemData(
            sku_norm=f"SKU{i:04d}",
            sku_raw=f"sku{i:04d}",
            in_occ=True,
            in_feed=False,
            in_amazon_report=False,
            sync_status=status,
            feed_stock=None,
            occ_stock=None,
            stock_conflict=False,
            error_rows=[],
        )
        for i in range(n)
    ]


# ===========================================================================
# 1. Happy path
# ===========================================================================


class TestHappyPath:
    def test_run_items_written(self, db: Session, fresh_run_id: int) -> None:
        items = _make_items(5, "NOT_SENT")
        persist_run_results(db, fresh_run_id, items)

        count = db.execute(
            text("SELECT COUNT(*) FROM run_items WHERE run_id = :rid"),
            {"rid": fresh_run_id},
        ).scalar()
        assert count == 5

    def test_run_status_transitions_to_completed(
        self, db: Session, fresh_run_id: int,
    ) -> None:
        persist_run_results(db, fresh_run_id, _make_items(2))

        status = db.execute(
            text("SELECT status FROM reconciliation_runs WHERE id = :rid"),
            {"rid": fresh_run_id},
        ).scalar()
        assert status == "completed"

    def test_completed_at_is_set(self, db: Session, fresh_run_id: int) -> None:
        persist_run_results(db, fresh_run_id, _make_items(2))

        completed_at = db.execute(
            text("SELECT completed_at FROM reconciliation_runs WHERE id = :rid"),
            {"rid": fresh_run_id},
        ).scalar()
        assert completed_at is not None, "completed_at must be set after completion"

    def test_summary_metrics_json_populated(self, db: Session, fresh_run_id: int) -> None:
        items = [
            RunItemData(
                sku_norm="SKU_ERR",
                sku_raw="sku_err",
                in_occ=True,
                in_feed=True,
                in_amazon_report=True,
                sync_status="SENT_WITH_ERROR",
                feed_stock=10,
                occ_stock=10,
                stock_conflict=False,
                error_rows=[],
            ),
            RunItemData(
                sku_norm="SKU_OK",
                sku_raw="sku_ok",
                in_occ=True,
                in_feed=True,
                in_amazon_report=True,
                sync_status="SENT_OK",
                feed_stock=5,
                occ_stock=5,
                stock_conflict=False,
                error_rows=[],
            ),
            RunItemData(
                sku_norm="SKU_NOT",
                sku_raw="sku_not",
                in_occ=True,
                in_feed=False,
                in_amazon_report=False,
                sync_status="NOT_SENT",
                feed_stock=None,
                occ_stock=3,
                stock_conflict=False,
                error_rows=[],
            ),
        ]
        persist_run_results(db, fresh_run_id, items)

        raw = db.execute(
            text("SELECT summary_metrics FROM reconciliation_runs WHERE id = :rid"),
            {"rid": fresh_run_id},
        ).scalar()
        assert raw is not None, "summary_metrics must be set"
        metrics = json.loads(str(raw))

        assert metrics["total_skus"] == 3
        assert metrics["sent_with_error"] == 1
        assert metrics["sent_ok"] == 1
        assert metrics["not_sent"] == 1
        assert metrics["desync_feed_only"] == 0
        assert metrics["desync_amazon_only"] == 0
        assert "total_errors" in metrics

    def test_item_errors_linked_to_run_items(self, db: Session, fresh_run_id: int) -> None:
        from marketplace_conciliator.reconciliation.error_classifier import ErrorRow

        # Seed a known error code so FK is satisfied
        db.execute(
            text(
                "INSERT OR IGNORE INTO error_codes (code, family_code) "
                "VALUES ('18299', 'SIN_CLASIFICAR')",
            ),
        )
        db.flush()

        items = [
            RunItemData(
                sku_norm="ERRSKU",
                sku_raw="errsku",
                in_occ=True,
                in_feed=True,
                in_amazon_report=True,
                sync_status="SENT_WITH_ERROR",
                feed_stock=3,
                occ_stock=3,
                stock_conflict=False,
                error_rows=[
                    ErrorRow(
                        sku_norm="ERRSKU",
                        error_code="18299",
                        error_category="ERROR",
                        error_message="Brand auth required",
                        affected_field="brand",
                    ),
                ],
            ),
        ]
        persist_run_results(db, fresh_run_id, items)

        err_count = db.execute(text("SELECT COUNT(*) FROM item_errors")).scalar()
        assert err_count == 1


# ===========================================================================
# 2. Rollback on failure — no orphan rows, run → failed
# ===========================================================================


class TestRollbackOnFailure:
    def test_rollback_leaves_no_run_items(self, db: Session, fresh_run_id: int) -> None:
        """If an error occurs during batch write, run_items must be fully rolled back."""
        items = _make_items(3, "NOT_SENT")

        # Patch _write_run_items_batch to raise after partial writes
        with patch(
            "marketplace_conciliator.reconciliation.persistence._write_run_items_batch",
            side_effect=RuntimeError("simulated write failure"),
        ):
            with pytest.raises(RuntimeError, match="simulated write failure"):
                persist_run_results(db, fresh_run_id, items)

        # After rollback, no run_items should exist for this run
        count = db.execute(
            text("SELECT COUNT(*) FROM run_items WHERE run_id = :rid"),
            {"rid": fresh_run_id},
        ).scalar()
        assert count == 0, f"Expected 0 run_items after rollback, found {count}"

    def test_run_status_set_to_failed_on_error(self, db: Session, fresh_run_id: int) -> None:
        items = _make_items(3, "NOT_SENT")

        with patch(
            "marketplace_conciliator.reconciliation.persistence._write_run_items_batch",
            side_effect=RuntimeError("disk full"),
        ):
            with pytest.raises(RuntimeError):
                persist_run_results(db, fresh_run_id, items)

        status = db.execute(
            text("SELECT status FROM reconciliation_runs WHERE id = :rid"),
            {"rid": fresh_run_id},
        ).scalar()
        assert status == "failed", f"Expected 'failed', got '{status}'"

    def test_failure_reason_stored(self, db: Session, fresh_run_id: int) -> None:
        items = _make_items(1)

        with patch(
            "marketplace_conciliator.reconciliation.persistence._write_run_items_batch",
            side_effect=RuntimeError("unique key violation"),
        ):
            with pytest.raises(RuntimeError):
                persist_run_results(db, fresh_run_id, items)

        reason = db.execute(
            text("SELECT failure_reason FROM reconciliation_runs WHERE id = :rid"),
            {"rid": fresh_run_id},
        ).scalar()
        assert reason is not None and len(str(reason)) > 0


# ===========================================================================
# 3. summary_metrics — all required keys present
# ===========================================================================


class TestSummaryMetricsKeys:
    _REQUIRED_KEYS = {
        "total_skus",
        "sent_with_error",
        "sent_ok",
        "not_sent",
        "desync_feed_only",
        "desync_amazon_only",
        "total_errors",
    }

    def test_all_required_keys_present(self, db: Session, fresh_run_id: int) -> None:
        persist_run_results(db, fresh_run_id, _make_items(1, "NOT_SENT"))

        raw = db.execute(
            text("SELECT summary_metrics FROM reconciliation_runs WHERE id = :rid"),
            {"rid": fresh_run_id},
        ).scalar()
        metrics = json.loads(str(raw))
        missing = self._REQUIRED_KEYS - set(metrics.keys())
        assert not missing, f"summary_metrics missing keys: {missing}"

    def test_counts_match_items(self, db: Session, fresh_run_id: int) -> None:
        statuses = [
            "SENT_WITH_ERROR",
            "SENT_OK",
            "NOT_SENT",
            "DESYNC_FEED_ONLY",
            "DESYNC_AMAZON_ONLY",
        ]
        items = [
            RunItemData(
                sku_norm=f"SKU{i}",
                sku_raw=f"sku{i}",
                in_occ=True,
                in_feed=True,
                in_amazon_report=True,
                sync_status=s,
                feed_stock=None,
                occ_stock=None,
                stock_conflict=False,
                error_rows=[],
            )
            for i, s in enumerate(statuses)
        ]
        persist_run_results(db, fresh_run_id, items)

        raw = db.execute(
            text("SELECT summary_metrics FROM reconciliation_runs WHERE id = :rid"),
            {"rid": fresh_run_id},
        ).scalar()
        m = json.loads(str(raw))

        assert m["total_skus"] == 5
        assert m["sent_with_error"] == 1
        assert m["sent_ok"] == 1
        assert m["not_sent"] == 1
        assert m["desync_feed_only"] == 1
        assert m["desync_amazon_only"] == 1
