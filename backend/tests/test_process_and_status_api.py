"""T-4.6 — TDD tests for POST /runs/{id}/process (async gate) and GET /runs/{id}/status.

Tests written FIRST (red), then implementation makes them green.

Coverage:
  1. GET /runs/{id}/status — returns status, phase, failure_reason, summary_metrics.
  2. POST /runs/{id}/process — gate 409 when mapping missing.
  3. POST /runs/{id}/process — 202 with status_url when gate passes (TaskRunner called).
  4. POST /runs/{id}/process — run transitions to 'processing' before TaskRunner runs.
  5. Integration: 202 → polling → completed (SyncTaskRunner runs pipeline inline).
"""

from __future__ import annotations

import io
import json
import threading
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from marketplace_conciliator.ingestion.router import (
    get_db,
    get_db_factory,
    get_staging_dir,
    get_task_runner,
)
from marketplace_conciliator.main import create_app
from marketplace_conciliator.platform.deps import DUMMY_USER

FIXTURES = Path(__file__).parent / "fixtures"
CSV_FIXTURE = FIXTURES / "wavemarket_fullstock_anonymized.csv"
XLSX_FIXTURE = FIXTURES / "occ_top_sales_anonymized.xlsx"
XLSM_FIXTURE = FIXTURES / "amazon_processing_summary_anonymized.xlsm"

# ---------------------------------------------------------------------------
# SQLite in-memory DB — full schema required by the process pipeline
# ---------------------------------------------------------------------------

_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(_engine, "connect")
def _set_pragma(dbapi_conn: Any, _: Any) -> None:  # noqa: ANN401
    dbapi_conn.cursor().execute("PRAGMA foreign_keys=ON")


def _create_schema(conn: Any) -> None:  # noqa: ANN401
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL,
            hashed_password TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS reconciliation_runs (
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
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS source_files (
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
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS column_mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file_id INTEGER NOT NULL REFERENCES source_files(id),
            logical_field TEXT NOT NULL,
            source_column_name TEXT NOT NULL,
            source_column_index INTEGER NOT NULL,
            was_suggested INTEGER NOT NULL DEFAULT 0,
            confirmed_by INTEGER NOT NULL REFERENCES users(id),
            confirmed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (source_file_id, logical_field)
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS duplicate_findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file_id INTEGER NOT NULL REFERENCES source_files(id),
            sku_norm TEXT NOT NULL,
            occurrences INTEGER NOT NULL,
            resolution TEXT NOT NULL,
            discarded_values TEXT NOT NULL
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS error_families (
            code TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            description TEXT,
            sort_order INTEGER NOT NULL DEFAULT 99
        )
    """))
    conn.execute(text("""
        INSERT OR IGNORE INTO error_families (code, display_name, sort_order)
        VALUES ('SIN_CLASIFICAR', 'Sin clasificar', 99)
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS error_codes (
            code TEXT PRIMARY KEY,
            family_code TEXT NOT NULL REFERENCES error_families(code),
            default_category TEXT NOT NULL DEFAULT 'ERROR',
            canonical_message TEXT,
            first_seen_at DATETIME
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS run_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL REFERENCES reconciliation_runs(id),
            sku_norm TEXT NOT NULL,
            sku_raw TEXT NOT NULL,
            in_occ INTEGER NOT NULL DEFAULT 0,
            in_feed INTEGER NOT NULL DEFAULT 0,
            in_amazon_report INTEGER NOT NULL DEFAULT 0,
            feed_stock INTEGER,
            occ_stock INTEGER,
            stock_conflict INTEGER NOT NULL DEFAULT 0,
            sync_status TEXT NOT NULL,
            submission_status TEXT,
            UNIQUE (run_id, sku_norm)
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS item_errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_item_id INTEGER NOT NULL REFERENCES run_items(id),
            error_code TEXT NOT NULL,
            error_category TEXT NOT NULL,
            error_message TEXT NOT NULL,
            affected_field TEXT
        )
    """))
    conn.execute(text("""
        INSERT OR IGNORE INTO users (id, email, role, hashed_password)
        VALUES (:id, :email, :role, 'dummy')
    """), {"id": DUMMY_USER.id, "email": DUMMY_USER.email, "role": DUMMY_USER.role})


with _engine.begin() as _c:
    _create_schema(_c)

_SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def _get_test_db() -> Generator[Session, None, None]:
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# TaskRunner stubs
# ---------------------------------------------------------------------------


class _NoOpTaskRunner:
    """Records submitted run_ids but never executes the work function."""

    def __init__(self) -> None:
        self.submitted: list[int] = []

    def submit(self, run_id: int, work_fn: Callable[[int], None]) -> None:  # noqa: ARG002
        self.submitted.append(run_id)

    def active_count(self) -> int:
        return 0

    def shutdown(self, *, wait: bool = True) -> None:
        pass


class _SyncTaskRunner:
    """Runs work_fn synchronously in the calling thread (for integration tests)."""

    def __init__(self) -> None:
        self.submitted: list[int] = []
        self._lock = threading.Lock()

    def submit(self, run_id: int, work_fn: Callable[[int], None]) -> None:
        with self._lock:
            self.submitted.append(run_id)
        work_fn(run_id)

    def active_count(self) -> int:
        return 0

    def shutdown(self, *, wait: bool = True) -> None:
        pass


# ---------------------------------------------------------------------------
# Staging directory
# ---------------------------------------------------------------------------

_STAGING = Path(__file__).parent / ".staging_t46"
_STAGING.mkdir(parents=True, exist_ok=True)


def _get_test_staging() -> Path:
    return _STAGING


# ---------------------------------------------------------------------------
# App fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def noop_runner() -> _NoOpTaskRunner:
    return _NoOpTaskRunner()


@pytest.fixture(scope="module")
def client_noop(noop_runner: _NoOpTaskRunner) -> TestClient:
    """Client with a no-op TaskRunner: verifies 202 but does not run pipeline."""
    app = create_app()
    app.dependency_overrides[get_db] = _get_test_db
    app.dependency_overrides[get_staging_dir] = _get_test_staging
    app.dependency_overrides[get_task_runner] = lambda: noop_runner
    app.dependency_overrides[get_db_factory] = lambda: _SessionLocal
    return TestClient(app)


@pytest.fixture(scope="module")
def client_sync() -> TestClient:
    """Client with a SyncTaskRunner: runs the full pipeline in-process."""
    runner = _SyncTaskRunner()
    app = create_app()
    app.dependency_overrides[get_db] = _get_test_db
    app.dependency_overrides[get_staging_dir] = _get_test_staging
    app.dependency_overrides[get_task_runner] = lambda: runner
    app.dependency_overrides[get_db_factory] = lambda: _SessionLocal
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_run(client: TestClient) -> int:
    r = client.post("/api/v1/runs", json={"marketplace": "amazon_es"})
    assert r.status_code == 201, r.text
    return int(r.json()["id"])


def _upload_file(client: TestClient, run_id: int, path: Path, role: str) -> int:
    data = path.read_bytes()
    r = client.post(
        f"/api/v1/runs/{run_id}/files",
        data={"role": role},
        files={"file": (path.name, io.BytesIO(data), "application/octet-stream")},
    )
    assert r.status_code == 201, r.text
    return int(r.json()["id"])


def _confirm_mapping(
    client: TestClient,
    run_id: int,
    file_id: int,
    mappings: list[dict[str, Any]],
) -> None:
    r = client.put(
        f"/api/v1/runs/{run_id}/files/{file_id}/mapping",
        json={"mappings": mappings},
    )
    assert r.status_code == 200, r.text


def _setup_full_run(client: TestClient) -> int:
    """Upload all 3 fixture files and confirm their SKU mappings.

    Returns run_id of a run that passes the gate (all 3 SKU mappings confirmed).
    """
    run_id = _create_run(client)

    # ── wm_feed (CSV) ────────────────────────────────────────────────────────
    wm_id = _upload_file(client, run_id, CSV_FIXTURE, "wm_feed")
    # Fetch preview to discover column indices
    prev = client.get(f"/api/v1/runs/{run_id}/files/{wm_id}/preview").json()
    sku_idx = prev["suggestions"]["sku"]["column_index"]
    stock_idx = prev["suggestions"].get("stock", {}).get("column_index")
    wm_mappings: list[dict[str, Any]] = [
        {"logical_field": "sku", "column_index": sku_idx, "was_suggested": True},
    ]
    if stock_idx is not None:
        wm_mappings.append(
            {"logical_field": "stock", "column_index": stock_idx, "was_suggested": True},
        )
    _confirm_mapping(client, run_id, wm_id, wm_mappings)

    # ── occ_top (XLSX) ───────────────────────────────────────────────────────
    occ_id = _upload_file(client, run_id, XLSX_FIXTURE, "occ_top")
    prev = client.get(f"/api/v1/runs/{run_id}/files/{occ_id}/preview").json()
    sku_idx = prev["suggestions"]["sku"]["column_index"]
    occ_mappings: list[dict[str, Any]] = [
        {"logical_field": "sku", "column_index": sku_idx, "was_suggested": True},
    ]
    stock_idx = prev["suggestions"].get("stock", {}).get("column_index")
    if stock_idx is not None:
        occ_mappings.append(
            {"logical_field": "stock", "column_index": stock_idx, "was_suggested": True},
        )
    _confirm_mapping(client, run_id, occ_id, occ_mappings)

    # ── amazon_report (XLSM) ─────────────────────────────────────────────────
    amz_id = _upload_file(client, run_id, XLSM_FIXTURE, "amazon_report")
    prev = client.get(f"/api/v1/runs/{run_id}/files/{amz_id}/preview").json()
    sku_idx = prev["suggestions"]["sku"]["column_index"]
    _confirm_mapping(
        client,
        run_id,
        amz_id,
        [{"logical_field": "sku", "column_index": sku_idx, "was_suggested": True}],
    )

    return run_id


# ===========================================================================
# Tests: GET /runs/{id}/status
# ===========================================================================


class TestGetRunStatus:
    """T-4.6 — GET /runs/{id}/status returns run phase + metrics (ADR-002 polling)."""

    def test_status_uploaded_run(self, client_noop: TestClient) -> None:
        run_id = _create_run(client_noop)
        r = client_noop.get(f"/api/v1/runs/{run_id}/status")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "uploaded"
        assert data["phase"] is None
        assert data["failure_reason"] is None
        assert data["summary_metrics"] is None

    def test_status_not_found(self, client_noop: TestClient) -> None:
        r = client_noop.get("/api/v1/runs/999999/status")
        assert r.status_code == 404

    def test_status_processing_phase(self, client_noop: TestClient) -> None:
        """A run manually put in 'processing' state returns correct status."""
        db = next(_get_test_db())
        run_id = _create_run(client_noop)
        db.execute(
            text("UPDATE reconciliation_runs SET status='processing', phase='Cruzando' WHERE id=:id"),
            {"id": run_id},
        )
        db.commit()
        db.close()

        r = client_noop.get(f"/api/v1/runs/{run_id}/status")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "processing"
        assert data["phase"] == "Cruzando"

    def test_status_completed_returns_summary_metrics(self, client_noop: TestClient) -> None:
        """A completed run exposes summary_metrics as a dict of counters."""
        metrics = {
            "total_skus": 42,
            "sent_with_error": 5,
            "sent_ok": 10,
            "not_sent": 20,
            "desync_feed_only": 4,
            "desync_amazon_only": 3,
            "total_errors": 15,
        }
        db = next(_get_test_db())
        run_id = _create_run(client_noop)
        db.execute(
            text("""
                UPDATE reconciliation_runs
                SET status='completed',
                    summary_metrics=:m
                WHERE id=:id
            """),
            {"id": run_id, "m": json.dumps(metrics)},
        )
        db.commit()
        db.close()

        r = client_noop.get(f"/api/v1/runs/{run_id}/status")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "completed"
        assert data["summary_metrics"]["total_skus"] == 42
        assert data["summary_metrics"]["sent_with_error"] == 5
        assert data["summary_metrics"]["total_errors"] == 15

    def test_status_failed_returns_failure_reason(self, client_noop: TestClient) -> None:
        db = next(_get_test_db())
        run_id = _create_run(client_noop)
        db.execute(
            text("""
                UPDATE reconciliation_runs
                SET status='failed', failure_reason='test_error'
                WHERE id=:id
            """),
            {"id": run_id},
        )
        db.commit()
        db.close()

        r = client_noop.get(f"/api/v1/runs/{run_id}/status")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "failed"
        assert data["failure_reason"] == "test_error"


# ===========================================================================
# Tests: POST /runs/{id}/process — gate 409
# ===========================================================================


class TestTriggerProcessGate:
    """T-4.6 — 409 Conflict when the mapping gate is not satisfied."""

    def test_process_no_files_returns_409(self, client_noop: TestClient) -> None:
        run_id = _create_run(client_noop)
        r = client_noop.post(f"/api/v1/runs/{run_id}/process")
        assert r.status_code == 409

    def test_process_partial_mapping_returns_409(self, client_noop: TestClient) -> None:
        """Only 1 of 3 files mapped → 409."""
        run_id = _create_run(client_noop)
        wm_id = _upload_file(client_noop, run_id, CSV_FIXTURE, "wm_feed")
        prev = client_noop.get(f"/api/v1/runs/{run_id}/files/{wm_id}/preview").json()
        sku_idx = prev["suggestions"]["sku"]["column_index"]
        _confirm_mapping(
            client_noop,
            run_id,
            wm_id,
            [{"logical_field": "sku", "column_index": sku_idx, "was_suggested": True}],
        )
        r = client_noop.post(f"/api/v1/runs/{run_id}/process")
        assert r.status_code == 409

    def test_process_nonexistent_run_returns_404(self, client_noop: TestClient) -> None:
        r = client_noop.post("/api/v1/runs/999999/process")
        assert r.status_code == 404


# ===========================================================================
# Tests: POST /runs/{id}/process — 202 + TaskRunner submission
# ===========================================================================


class TestTriggerProcess202:
    """T-4.6 — 202 Accepted + TaskRunner called when gate is satisfied."""

    def test_process_returns_202_with_status_url(
        self,
        client_noop: TestClient,
        noop_runner: _NoOpTaskRunner,
    ) -> None:
        run_id = _setup_full_run(client_noop)
        noop_runner.submitted.clear()

        r = client_noop.post(f"/api/v1/runs/{run_id}/process")
        assert r.status_code == 202
        body = r.json()
        assert "status_url" in body
        assert str(run_id) in body["status_url"]

    def test_process_submits_to_task_runner(
        self,
        client_noop: TestClient,
        noop_runner: _NoOpTaskRunner,
    ) -> None:
        """The TaskRunner.submit() must be called with the correct run_id."""
        run_id = _setup_full_run(client_noop)
        noop_runner.submitted.clear()

        client_noop.post(f"/api/v1/runs/{run_id}/process")
        assert run_id in noop_runner.submitted

    def test_process_sets_status_to_processing_before_task_runs(
        self,
        client_noop: TestClient,
    ) -> None:
        """The run must be in 'processing' immediately after the 202 response.

        Since the NoOpTaskRunner never executes the pipeline, the run stays
        in 'processing' — which is what we observe here.
        """
        run_id = _setup_full_run(client_noop)
        client_noop.post(f"/api/v1/runs/{run_id}/process")

        r = client_noop.get(f"/api/v1/runs/{run_id}/status")
        assert r.status_code == 200
        assert r.json()["status"] == "processing"


# ===========================================================================
# Integration test: 202 → polling → completed (DoD T-4.6)
# ===========================================================================


class TestPollingIntegration:
    """T-4.6 DoD — full flow: 202 → poll status → completed with metrics."""

    def test_full_pipeline_reaches_completed(self, client_sync: TestClient) -> None:
        """End-to-end: upload → map → process → poll → completed.

        The SyncTaskRunner runs the pipeline in-process so we can check
        the final status without needing a real background thread.
        """
        run_id = _setup_full_run(client_sync)

        # Trigger processing
        r = client_sync.post(f"/api/v1/runs/{run_id}/process")
        assert r.status_code == 202
        status_url = r.json()["status_url"]
        assert status_url  # must be non-empty

        # With SyncTaskRunner, pipeline has already completed by now
        r2 = client_sync.get(f"/api/v1/runs/{run_id}/status")
        assert r2.status_code == 200
        data = r2.json()
        assert data["status"] == "completed", (
            f"Expected completed but got: {data['status']} "
            f"(failure_reason={data.get('failure_reason')})"
        )
        assert data["phase"] is None
        metrics = data["summary_metrics"]
        assert metrics is not None
        assert metrics["total_skus"] > 0

    def test_status_url_from_202_is_accessible(self, client_sync: TestClient) -> None:
        """The status_url returned in 202 body must resolve to a valid endpoint."""
        run_id = _setup_full_run(client_sync)
        r = client_sync.post(f"/api/v1/runs/{run_id}/process")
        assert r.status_code == 202
        status_url = r.json()["status_url"]
        # status_url is relative (/api/v1/runs/{id}/status)
        r2 = client_sync.get(status_url)
        assert r2.status_code == 200
