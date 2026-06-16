"""T-4.1 — TDD tests for TaskRunner port + ThreadPoolTaskRunner adapter.

DoD verification (spec section 4.3, T-4.1):
  1. Event loop responds /health during a heavy simulated job (non-blocking).
  2. 3rd concurrent job waits when semaphore is full (max 2 simultaneous).
  3. Simulated server restart marks the run as failed with cause.

Written BEFORE the implementation (TDD: red → green → refactor).
Uses SQLite in-memory for DB-dependent tests; no Docker required.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from marketplace_conciliator.main import create_app
from marketplace_conciliator.platform.recovery import recover_stale_runs
from marketplace_conciliator.reconciliation.task_runner import (
    MAX_CONCURRENT_JOBS,
    ThreadPoolTaskRunner,
)

# ---------------------------------------------------------------------------
# SQLite in-memory schema fixture (shared across DB tests in this module)
# ---------------------------------------------------------------------------

_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

with _engine.begin() as _conn:
    _conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            email           TEXT    NOT NULL UNIQUE,
            role            TEXT    NOT NULL,
            hashed_password TEXT    NOT NULL,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """))
    _conn.execute(text("""
        CREATE TABLE IF NOT EXISTS reconciliation_runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL REFERENCES users(id),
            marketplace     TEXT    NOT NULL DEFAULT 'amazon_es',
            status          TEXT    NOT NULL,
            phase           TEXT,
            failure_reason  TEXT,
            summary_metrics TEXT,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at    DATETIME
        )
    """))
    _conn.execute(text("""
        INSERT OR IGNORE INTO users (id, email, role, hashed_password)
        VALUES (1, 'dev@local.test', 'admin', 'dummy')
    """))

_TestSessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


def _db_session() -> Session:
    return _TestSessionLocal()


# ---------------------------------------------------------------------------
# Helpers: spy callbacks for TaskRunner injection
# ---------------------------------------------------------------------------


class _SpyCallbacks:
    """Records on_phase / on_failed calls for assertion."""

    def __init__(self) -> None:
        self.phases: list[tuple[int, str]] = []
        self.failures: list[tuple[int, str]] = []
        self._lock = threading.Lock()

    def on_phase(self, run_id: int, phase: str) -> None:
        with self._lock:
            self.phases.append((run_id, phase))

    def on_failed(self, run_id: int, reason: str) -> None:
        with self._lock:
            self.failures.append((run_id, reason))


def _make_runner(spy: _SpyCallbacks | None = None) -> ThreadPoolTaskRunner:
    """Return a configured runner with optional spy callbacks."""
    s = spy or _SpyCallbacks()
    return ThreadPoolTaskRunner(on_phase=s.on_phase, on_failed=s.on_failed)


# ---------------------------------------------------------------------------
# 1 — Non-blocking: /health responds during a heavy simulated job
# ---------------------------------------------------------------------------


class TestNonBlocking:
    def test_health_responds_during_heavy_job(self) -> None:
        """FastAPI event loop must respond to /health while a long job is running.

        Verifies ADR-002: ThreadPoolExecutor jobs run in background threads and
        never block the HTTP request cycle.
        """
        runner = _make_runner()
        job_started = threading.Event()
        job_gate = threading.Event()

        def slow_work(run_id: int) -> None:  # noqa: ARG001
            job_started.set()
            job_gate.wait(timeout=5.0)

        runner.submit(99, slow_work)
        # Wait until the job is truly inside work_fn (not just scheduled)
        assert job_started.wait(timeout=2.0), "Job did not start within 2 s"
        assert runner.active_count() == 1

        client = TestClient(create_app())
        t0 = time.perf_counter()
        resp = client.get("/api/v1/health")
        elapsed = time.perf_counter() - t0

        try:
            assert resp.status_code == 200
            assert elapsed < 0.5, f"/health took {elapsed:.3f}s — may be blocking"
        finally:
            job_gate.set()
            runner.shutdown()

    def test_submit_returns_immediately(self) -> None:
        """submit() must not block the caller (returns a Future instantly)."""
        runner = _make_runner()
        gate = threading.Event()

        def blocking_work(run_id: int) -> None:  # noqa: ARG001
            gate.wait(timeout=5.0)

        t0 = time.perf_counter()
        future = runner.submit(1, blocking_work)
        elapsed = time.perf_counter() - t0

        try:
            assert elapsed < 0.1, f"submit() blocked for {elapsed:.3f}s"
            assert not future.done()
        finally:
            gate.set()
            runner.shutdown()


# ---------------------------------------------------------------------------
# 2 — Semaphore: concurrency cap and queuing of excess jobs
# ---------------------------------------------------------------------------


class TestSemaphore:
    def test_max_concurrent_jobs_constant_is_two(self) -> None:
        """Semaphore cap must be exactly 2 (spec requirement)."""
        assert MAX_CONCURRENT_JOBS == 2

    def test_at_most_two_jobs_execute_simultaneously(self) -> None:
        """With semaphore=2, never more than 2 work_fns run at the same time."""
        runner = _make_runner()
        started: list[int] = []
        started_lock = threading.Lock()
        gate = threading.Event()

        def tracking_work(run_id: int) -> None:
            with started_lock:
                started.append(run_id)
            gate.wait(timeout=5.0)

        runner.submit(1, tracking_work)
        runner.submit(2, tracking_work)
        runner.submit(3, tracking_work)

        # Give threads time to start and reach the gate
        time.sleep(0.25)

        with started_lock:
            active_now = len(started)

        try:
            assert active_now == MAX_CONCURRENT_JOBS, (
                f"Expected {MAX_CONCURRENT_JOBS} active jobs, got {active_now}"
            )
        finally:
            gate.set()
            runner.shutdown()

    def test_third_job_waits_then_starts_after_slot_opens(self) -> None:
        """3rd job must queue and only start once a semaphore slot is released.

        DoD: '3er job concurrente espera; reinicio simulado…'
        """
        runner = _make_runner()

        started: dict[int, threading.Event] = {i: threading.Event() for i in (1, 2, 3)}
        release: dict[int, threading.Event] = {i: threading.Event() for i in (1, 2, 3)}

        def make_work(job_id: int) -> Callable[[int], None]:
            def work(run_id: int) -> None:  # noqa: ARG001
                started[job_id].set()
                release[job_id].wait(timeout=5.0)

            return work

        # Submit jobs 1 and 2 first, wait for both to be active
        runner.submit(10, make_work(1))
        runner.submit(20, make_work(2))
        assert started[1].wait(timeout=2.0), "Job 1 did not start"
        assert started[2].wait(timeout=2.0), "Job 2 did not start"

        # Job 3 submitted when semaphore is full
        runner.submit(30, make_work(3))
        time.sleep(0.1)
        assert not started[3].is_set(), "Job 3 started prematurely — semaphore leak"

        # Release job 1 → job 3 must now acquire the slot and start
        release[1].set()
        assert started[3].wait(timeout=2.0), "Job 3 never started after job 1 released"

        try:
            assert runner.active_count() == MAX_CONCURRENT_JOBS
        finally:
            release[2].set()
            release[3].set()
            runner.shutdown()

    def test_active_count_tracks_executing_jobs(self) -> None:
        """active_count() reflects jobs currently inside work_fn."""
        runner = _make_runner()
        gate = threading.Event()
        started = threading.Event()

        def work(run_id: int) -> None:  # noqa: ARG001
            started.set()
            gate.wait(timeout=5.0)

        assert runner.active_count() == 0
        runner.submit(1, work)
        started.wait(timeout=2.0)
        assert runner.active_count() == 1

        gate.set()
        runner.shutdown()
        assert runner.active_count() == 0


# ---------------------------------------------------------------------------
# 3 — Phase state: on_phase callback fires at job start
# ---------------------------------------------------------------------------


class TestPhaseCallbacks:
    def test_on_phase_called_with_initializing_at_start(self) -> None:
        """TaskRunner must call on_phase(run_id, 'initializing') before work_fn."""
        spy = _SpyCallbacks()
        runner = _make_runner(spy)
        job_done = threading.Event()

        def work(run_id: int) -> None:  # noqa: ARG001
            job_done.set()

        runner.submit(42, work)
        job_done.wait(timeout=2.0)
        runner.shutdown()

        assert any(run_id == 42 and phase == "initializing" for run_id, phase in spy.phases)

    def test_on_failed_called_when_work_fn_raises(self) -> None:
        """TaskRunner must catch work_fn exceptions and call on_failed."""
        spy = _SpyCallbacks()
        runner = _make_runner(spy)
        job_done = threading.Event()

        def crashing_work(run_id: int) -> None:  # noqa: ARG001
            job_done.set()
            msg = "deliberate crash"
            raise RuntimeError(msg)

        runner.submit(77, crashing_work)
        job_done.wait(timeout=2.0)
        time.sleep(0.1)  # Allow exception handler to fire
        runner.shutdown()

        assert any(run_id == 77 for run_id, _ in spy.failures), (
            "on_failed was not called after crashing work_fn"
        )

    def test_on_failed_reason_contains_exception_message(self) -> None:
        spy = _SpyCallbacks()
        runner = _make_runner(spy)
        job_done = threading.Event()

        def crashing_work(run_id: int) -> None:  # noqa: ARG001
            job_done.set()
            msg = "unique_crash_signature_7f3a"
            raise ValueError(msg)

        runner.submit(55, crashing_work)
        job_done.wait(timeout=2.0)
        time.sleep(0.1)
        runner.shutdown()

        reasons = [reason for _, reason in spy.failures if _ == 55]
        assert any("unique_crash_signature_7f3a" in r for r in reasons)


# ---------------------------------------------------------------------------
# 4 — Startup recovery: stale processing runs marked failed on restart
# ---------------------------------------------------------------------------


class TestStartupRecovery:
    @pytest.fixture(autouse=True)
    def _clean_runs(self) -> None:
        """Truncate reconciliation_runs before each test in this class."""
        with _engine.begin() as conn:
            conn.execute(text("DELETE FROM reconciliation_runs"))

    def _insert_run(self, status: str, run_id: int = 1) -> None:
        with _engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO reconciliation_runs
                        (id, user_id, marketplace, status)
                    VALUES
                        (:id, 1, 'amazon_es', :status)
                """),
                {"id": run_id, "status": status},
            )

    def _get_run(self, run_id: int = 1) -> dict[str, object]:
        with _engine.connect() as conn:
            row = conn.execute(
                text("SELECT status, failure_reason, phase FROM reconciliation_runs WHERE id=:id"),
                {"id": run_id},
            ).fetchone()
        assert row is not None, f"Run {run_id} not found"
        return {"status": row[0], "failure_reason": row[1], "phase": row[2]}

    def test_processing_run_is_marked_failed(self) -> None:
        """recover_stale_runs must transition status=processing → failed."""
        self._insert_run("processing")
        db = _db_session()
        try:
            recover_stale_runs(db)
        finally:
            db.close()

        row = self._get_run()
        assert row["status"] == "failed"

    def test_failure_reason_is_restart_during_processing(self) -> None:
        """failure_reason must be exactly 'restart_during_processing'."""
        self._insert_run("processing")
        db = _db_session()
        try:
            recover_stale_runs(db)
        finally:
            db.close()

        row = self._get_run()
        assert row["failure_reason"] == "restart_during_processing"

    def test_phase_is_cleared_after_recovery(self) -> None:
        """phase column must be NULL after recovery (no stale phase label)."""
        with _engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO reconciliation_runs
                        (id, user_id, marketplace, status, phase)
                    VALUES (1, 1, 'amazon_es', 'processing', 'deduplicating')
                """),
            )
        db = _db_session()
        try:
            recover_stale_runs(db)
        finally:
            db.close()

        row = self._get_run()
        assert row["phase"] is None

    def test_completed_run_is_not_touched(self) -> None:
        """recover_stale_runs must leave completed runs unchanged."""
        self._insert_run("completed")
        db = _db_session()
        try:
            recover_stale_runs(db)
        finally:
            db.close()

        row = self._get_run()
        assert row["status"] == "completed"

    def test_uploaded_run_is_not_touched(self) -> None:
        self._insert_run("uploaded")
        db = _db_session()
        try:
            recover_stale_runs(db)
        finally:
            db.close()

        assert self._get_run()["status"] == "uploaded"

    def test_failed_run_is_not_touched(self) -> None:
        self._insert_run("failed")
        db = _db_session()
        try:
            recover_stale_runs(db)
        finally:
            db.close()

        assert self._get_run()["status"] == "failed"

    def test_returns_count_of_recovered_runs(self) -> None:
        """recover_stale_runs must return the number of runs it recovered."""
        self._insert_run("processing", run_id=1)
        self._insert_run("processing", run_id=2)
        self._insert_run("completed", run_id=3)

        db = _db_session()
        try:
            count = recover_stale_runs(db)
        finally:
            db.close()

        assert count == 2

    def test_returns_zero_when_no_stale_runs(self) -> None:
        db = _db_session()
        try:
            count = recover_stale_runs(db)
        finally:
            db.close()

        assert count == 0
