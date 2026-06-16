"""T-5.5 — Integration tests for GET /api/v1/runs (RF-13 historico paginado).

TDD: written BEFORE implementation.
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


@pytest.fixture(autouse=True)
def _clean_runs_table() -> Generator[None, None, None]:
    """Isolate each test — shared in-memory SQLite persists across cases."""
    with _engine.begin() as conn:
        conn.execute(text("DELETE FROM reconciliation_runs"))
    yield


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
    created_at: str,
    completed_at: str | None = None,
    summary_metrics: dict[str, int] | None = None,
) -> int:
    db.execute(
        text("""
            INSERT INTO reconciliation_runs
                (user_id, marketplace, status, summary_metrics, created_at, completed_at)
            VALUES
                (1, 'amazon_es', :status, :metrics, :created_at, :completed_at)
        """),
        {
            "status": status,
            "metrics": json.dumps(summary_metrics) if summary_metrics else None,
            "created_at": created_at,
            "completed_at": completed_at,
        },
    )
    db.commit()
    row = db.execute(text("SELECT last_insert_rowid()")).scalar_one()
    return int(row)


class TestListRuns:
    def test_list_runs_returns_paginated_envelope(self, client: TestClient) -> None:
        db = _SessionLocal()
        try:
            _insert_run(db, status="completed", created_at="2026-06-10T10:00:00")
            _insert_run(db, status="uploaded", created_at="2026-06-11T10:00:00")
        finally:
            db.close()

        resp = client.get("/api/v1/runs?page=1&size=10")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["page"] == 1
        assert body["size"] == 10
        assert body["total"] == 2
        assert len(body["items"]) == 2

    def test_list_runs_ordered_by_created_at_desc(self, client: TestClient) -> None:
        db = _SessionLocal()
        try:
            older = _insert_run(db, status="completed", created_at="2026-06-01T10:00:00")
            newer = _insert_run(db, status="completed", created_at="2026-06-15T10:00:00")
        finally:
            db.close()

        body = client.get("/api/v1/runs").json()
        assert body["items"][0]["id"] == newer
        assert body["items"][1]["id"] == older

    def test_list_runs_filters_by_status(self, client: TestClient) -> None:
        db = _SessionLocal()
        try:
            _insert_run(db, status="completed", created_at="2026-06-10T10:00:00")
            _insert_run(db, status="failed", created_at="2026-06-11T10:00:00")
        finally:
            db.close()

        resp = client.get("/api/v1/runs?status=completed")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["status"] == "completed"

    def test_list_runs_pagination_limits_items(self, client: TestClient) -> None:
        db = _SessionLocal()
        try:
            for day in range(1, 6):
                _insert_run(
                    db,
                    status="completed",
                    created_at=f"2026-06-{day:02d}T10:00:00",
                )
        finally:
            db.close()

        body = client.get("/api/v1/runs?page=1&size=2").json()
        assert body["total"] == 5
        assert len(body["items"]) == 2

    def test_list_runs_item_includes_summary_fields(self, client: TestClient) -> None:
        db = _SessionLocal()
        try:
            run_id = _insert_run(
                db,
                status="completed",
                created_at="2026-06-10T10:00:00",
                completed_at="2026-06-10T10:05:00",
                summary_metrics={"total_skus": 100, "total_errors": 5},
            )
        finally:
            db.close()

        item = client.get("/api/v1/runs").json()["items"][0]
        assert item["id"] == run_id
        assert item["marketplace"] == "amazon_es"
        assert item["status"] == "completed"
        assert item["created_at"] is not None
        assert item["completed_at"] is not None
        assert item["summary_metrics"]["total_skus"] == 100
