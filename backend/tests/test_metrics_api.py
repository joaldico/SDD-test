"""T-5.1 — Integration tests for GET /api/v1/runs/{id}/metrics (TDD).

DoD:
  - 404 when run does not exist.
  - 409 when run is not completed (metrics not ready).
  - 200 with dashboard summary cards for a completed run.
  - desynchronized = desync_feed_only + desync_amazon_only.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from marketplace_conciliator.main import create_app
from marketplace_conciliator.reporting.router import get_db

_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(_engine, "connect")
def _set_pragma(dbapi_conn: Any, _: Any) -> None:  # noqa: ANN401
    dbapi_conn.cursor().execute("PRAGMA foreign_keys=ON")


with _engine.begin() as conn:
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
        INSERT OR IGNORE INTO users (id, email, role, hashed_password)
        VALUES (1, 'admin@test.local', 'admin', 'dummy')
    """))

_SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


def _get_test_db() -> Generator[Session, None, None]:
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    app = create_app()
    app.dependency_overrides[get_db] = _get_test_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _insert_run(
    db: Session,
    *,
    status: str,
    summary_metrics: dict[str, int] | None = None,
    completed_at: str | None = None,
) -> int:
    db.execute(
        text("""
            INSERT INTO reconciliation_runs
                (user_id, marketplace, status, summary_metrics, completed_at)
            VALUES
                (1, 'amazon_es', :status, :metrics, :completed_at)
        """),
        {
            "status": status,
            "metrics": json.dumps(summary_metrics) if summary_metrics else None,
            "completed_at": completed_at,
        },
    )
    db.commit()
    row = db.execute(text("SELECT last_insert_rowid()")).scalar_one()
    return int(row)


class TestGetRunMetrics:
    def test_unknown_run_returns_404(self, client: TestClient) -> None:
        response = client.get("/api/v1/runs/999/metrics")
        assert response.status_code == 404

    def test_processing_run_returns_409(self, client: TestClient) -> None:
        db = _SessionLocal()
        try:
            run_id = _insert_run(db, status="processing")
        finally:
            db.close()

        response = client.get(f"/api/v1/runs/{run_id}/metrics")
        assert response.status_code == 409
        assert "not ready" in response.json()["detail"].lower()

    def test_completed_run_returns_dashboard_summary(self, client: TestClient) -> None:
        metrics = {
            "total_skus": 4094,
            "sent_with_error": 120,
            "sent_ok": 3200,
            "not_sent": 708,
            "desync_feed_only": 62,
            "desync_amazon_only": 4,
            "total_errors": 845,
        }
        db = _SessionLocal()
        try:
            run_id = _insert_run(
                db,
                status="completed",
                summary_metrics=metrics,
                completed_at="2026-06-16 12:00:00",
            )
        finally:
            db.close()

        response = client.get(f"/api/v1/runs/{run_id}/metrics")
        assert response.status_code == 200
        data = response.json()

        assert data["run_id"] == run_id
        assert data["status"] == "completed"
        assert data["summary"]["total_skus"] == 4094
        assert data["summary"]["total_errors"] == 845
        assert data["summary"]["desynchronized"] == 66
        assert data["by_sync_status"]["not_sent"] == 708
