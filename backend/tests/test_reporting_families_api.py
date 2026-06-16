"""T-5.2 — Integration tests for GET /api/v1/runs/{id}/report/families (TDD)."""

from __future__ import annotations

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
        CREATE TABLE IF NOT EXISTS error_families (
            code TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            description TEXT,
            sort_order INTEGER NOT NULL
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS error_codes (
            code TEXT PRIMARY KEY,
            family_code TEXT NOT NULL REFERENCES error_families(code),
            default_category TEXT,
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
        CREATE TABLE IF NOT EXISTS item_errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_item_id INTEGER NOT NULL REFERENCES run_items(id),
            error_code TEXT NOT NULL REFERENCES error_codes(code),
            error_category TEXT NOT NULL,
            error_message TEXT NOT NULL,
            affected_field TEXT
        )
    """))
    conn.execute(text("""
        INSERT OR IGNORE INTO users (id, email, role, hashed_password)
        VALUES (1, 'admin@test.local', 'admin', 'dummy')
    """))
    conn.execute(text("""
        INSERT OR IGNORE INTO error_families (code, display_name, sort_order)
        VALUES
            ('AUTORIZACION_MARCA', 'Autorización de marca', 1),
            ('SIN_CLASIFICAR', 'Sin clasificar', 99)
    """))
    conn.execute(text("""
        INSERT OR IGNORE INTO error_codes (code, family_code, canonical_message)
        VALUES
            ('18299', 'AUTORIZACION_MARCA', 'Marca no autorizada'),
            ('18749', 'AUTORIZACION_MARCA', 'Uso indebido de marca'),
            ('99999', 'SIN_CLASIFICAR', 'Código desconocido')
    """))


with _engine.begin() as conn:
    _create_schema(conn)

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


def _seed_brand_family_errors(db: Session, run_id: int) -> None:
    db.execute(
        text("""
            INSERT INTO run_items
                (run_id, sku_norm, sku_raw, in_occ, in_feed, in_amazon_report,
                 sync_status, feed_stock, occ_stock, stock_conflict)
            VALUES
                (:run_id, 'SKU-A', 'SKU-A', 0, 1, 1, 'SENT_WITH_ERROR', 5, NULL, 0),
                (:run_id, 'SKU-B', 'SKU-B', 0, 1, 1, 'SENT_WITH_ERROR', 3, NULL, 0)
        """),
        {"run_id": run_id},
    )
    item_a = int(
        db.execute(
            text("SELECT id FROM run_items WHERE run_id = :run_id AND sku_norm = 'SKU-A'"),
            {"run_id": run_id},
        ).scalar_one(),
    )
    item_b = int(
        db.execute(
            text("SELECT id FROM run_items WHERE run_id = :run_id AND sku_norm = 'SKU-B'"),
            {"run_id": run_id},
        ).scalar_one(),
    )

    errors = [
        (item_a, "18299", "ERROR", "Marca no autorizada en SKU-A"),
        (item_a, "18299", "ERROR", "Marca no autorizada repetida"),
        (item_b, "18749", "ERROR", "Uso indebido de marca en SKU-B"),
    ]
    for run_item_id, code, category, message in errors:
        db.execute(
            text("""
                INSERT INTO item_errors (run_item_id, error_code, error_category, error_message)
                VALUES (:run_item_id, :code, :category, :message)
            """),
            {
                "run_item_id": run_item_id,
                "code": code,
                "category": category,
                "message": message,
            },
        )
    db.commit()


class TestGetFamiliesReport:
    def test_unknown_run_returns_404(self, client: TestClient) -> None:
        response = client.get("/api/v1/runs/999/report/families")
        assert response.status_code == 404

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

        response = client.get(f"/api/v1/runs/{run_id}/report/families")
        assert response.status_code == 409

    def test_completed_run_returns_family_aggregation(self, client: TestClient) -> None:
        db = _SessionLocal()
        try:
            run_id = _insert_completed_run(db)
            _seed_brand_family_errors(db, run_id)
        finally:
            db.close()

        response = client.get(f"/api/v1/runs/{run_id}/report/families")
        assert response.status_code == 200
        data = response.json()

        assert data["run_id"] == run_id
        assert data["sin_clasificar_warning"] is False
        assert len(data["families"]) == 1

        family = data["families"][0]
        assert family["code"] == "AUTORIZACION_MARCA"
        assert family["display_name"] == "Autorización de marca"
        assert family["unique_skus"] == 2
        assert family["total_errors"] == 3
        assert family["codes"] == [
            {"code": "18299", "message": "Marca no autorizada", "count": 2},
            {"code": "18749", "message": "Uso indebido de marca", "count": 1},
        ]

    def test_sin_clasificar_warning_when_present(self, client: TestClient) -> None:
        db = _SessionLocal()
        try:
            run_id = _insert_completed_run(db)
            db.execute(
                text("""
                    INSERT INTO run_items
                        (run_id, sku_norm, sku_raw, in_occ, in_feed, in_amazon_report,
                         sync_status, feed_stock, occ_stock, stock_conflict)
                    VALUES
                        (:run_id, 'SKU-X', 'SKU-X', 0, 1, 1, 'SENT_WITH_ERROR', 1, NULL, 0)
                """),
                {"run_id": run_id},
            )
            item_id = int(
                db.execute(
                    text("SELECT id FROM run_items WHERE sku_norm = 'SKU-X'"),
                ).scalar_one(),
            )
            db.execute(
                text("""
                    INSERT INTO item_errors (run_item_id, error_code, error_category, error_message)
                    VALUES (:item_id, '99999', 'ERROR', 'Código nuevo')
                """),
                {"item_id": item_id},
            )
            db.commit()
        finally:
            db.close()

        response = client.get(f"/api/v1/runs/{run_id}/report/families")
        assert response.status_code == 200
        data = response.json()
        assert data["sin_clasificar_warning"] is True
        sin = next(f for f in data["families"] if f["code"] == "SIN_CLASIFICAR")
        assert sin["total_errors"] == 1

    def test_empty_families_when_no_errors(self, client: TestClient) -> None:
        db = _SessionLocal()
        try:
            run_id = _insert_completed_run(db)
        finally:
            db.close()

        response = client.get(f"/api/v1/runs/{run_id}/report/families")
        assert response.status_code == 200
        assert response.json()["families"] == []
