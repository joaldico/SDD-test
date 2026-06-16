"""T-5.2 — Integration tests for GET /api/v1/runs/{id}/catalog-health enhancements (TDD)."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from marketplace_conciliator.ingestion.router import get_db
from marketplace_conciliator.main import create_app

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
            hashed_password TEXT NOT NULL
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
        CREATE TABLE IF NOT EXISTS run_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL REFERENCES reconciliation_runs(id),
            sku_norm TEXT NOT NULL,
            sku_raw TEXT NOT NULL,
            in_occ INTEGER NOT NULL,
            in_feed INTEGER NOT NULL,
            in_amazon_report INTEGER NOT NULL,
            sync_status TEXT NOT NULL,
            feed_stock INTEGER,
            occ_stock INTEGER,
            stock_conflict INTEGER NOT NULL DEFAULT 0,
            submission_status TEXT,
            UNIQUE(run_id, sku_norm)
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


def _insert_completed_run(db: Session) -> int:
    db.execute(
        text("""
            INSERT INTO reconciliation_runs (user_id, marketplace, status, completed_at)
            VALUES (1, 'amazon_es', 'completed', '2026-06-16 12:00:00')
        """),
    )
    db.commit()
    return int(db.execute(text("SELECT last_insert_rowid()")).scalar_one())


class TestCatalogHealthApi:
    def test_prioritizes_stock_conflicts_within_same_status(self, client: TestClient) -> None:
        db = _SessionLocal()
        try:
            run_id = _insert_completed_run(db)
            rows = [
                ("SKU-LOW", "DESYNC_FEED_ONLY", 50, 0),
                ("SKU-CONFLICT", "DESYNC_FEED_ONLY", 10, 1),
                ("SKU-HIGH", "DESYNC_FEED_ONLY", 100, 0),
            ]
            for sku, status, stock, conflict in rows:
                db.execute(
                    text("""
                        INSERT INTO run_items
                            (run_id, sku_norm, sku_raw, in_occ, in_feed, in_amazon_report,
                             sync_status, feed_stock, occ_stock, stock_conflict)
                        VALUES
                            (:run_id, :sku, :sku, 0, 1, 0, :status, :stock, NULL, :conflict)
                    """),
                    {
                        "run_id": run_id,
                        "sku": sku,
                        "status": status,
                        "stock": stock,
                        "conflict": conflict,
                    },
                )
            db.commit()
        finally:
            db.close()

        response = client.get(
            f"/api/v1/runs/{run_id}/catalog-health",
            params={"sync_status": "DESYNC_FEED_ONLY"},
        )
        assert response.status_code == 200
        norms = [item["sku_norm"] for item in response.json()["items"]]
        assert norms[0] == "SKU-CONFLICT"
        assert norms.index("SKU-HIGH") < norms.index("SKU-LOW")

    def test_pagination_is_stable(self, client: TestClient) -> None:
        db = _SessionLocal()
        try:
            run_id = _insert_completed_run(db)
            for idx in range(5):
                db.execute(
                    text("""
                        INSERT INTO run_items
                            (run_id, sku_norm, sku_raw, in_occ, in_feed, in_amazon_report,
                             sync_status, feed_stock, occ_stock, stock_conflict)
                        VALUES
                            (:run_id, :sku, :sku, 0, 1, 0, 'NOT_SENT', :stock, NULL, 0)
                    """),
                    {"run_id": run_id, "sku": f"SKU-{idx}", "stock": idx},
                )
            db.commit()
        finally:
            db.close()

        page1 = client.get(
            f"/api/v1/runs/{run_id}/catalog-health",
            params={"page": 1, "page_size": 2},
        )
        page2 = client.get(
            f"/api/v1/runs/{run_id}/catalog-health",
            params={"page": 2, "page_size": 2},
        )
        assert page1.status_code == 200
        assert page2.status_code == 200

        data1 = page1.json()
        data2 = page2.json()
        assert data1["total"] == 5
        assert len(data1["items"]) == 2
        assert len(data2["items"]) == 2

        page1_skus = {item["sku_norm"] for item in data1["items"]}
        page2_skus = {item["sku_norm"] for item in data2["items"]}
        assert page1_skus.isdisjoint(page2_skus)

    def test_processing_run_returns_409(self, client: TestClient) -> None:
        db = _SessionLocal()
        try:
            db.execute(
                text("""
                    INSERT INTO reconciliation_runs (user_id, marketplace, status)
                    VALUES (1, 'amazon_es', 'processing')
                """),
            )
            db.commit()
            run_id = int(db.execute(text("SELECT last_insert_rowid()")).scalar_one())
        finally:
            db.close()

        response = client.get(f"/api/v1/runs/{run_id}/catalog-health")
        assert response.status_code == 409
