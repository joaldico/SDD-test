"""T-5.6 — Integration tests for taxonomy admin endpoints (TDD).

GET  /api/v1/error-families  — catalog of families and error codes.
PATCH /api/v1/error-codes/{code} — reassign family (admin only).
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
from marketplace_conciliator.platform.deps import CurrentUser, get_current_user
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
            ('GPSR', 'GPSR / seguridad', 2),
            ('SIN_CLASIFICAR', 'Sin clasificar', 99)
    """))
    conn.execute(text("""
        INSERT OR IGNORE INTO error_codes (code, family_code, default_category, canonical_message)
        VALUES
            ('8541', 'SIN_CLASIFICAR', 'ERROR', 'Unknown listing error'),
            ('90220', 'AUTORIZACION_MARCA', 'ERROR', 'Brand approval required')
    """))


with _engine.begin() as conn:
    _create_schema(conn)

_SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)

ADMIN_USER = CurrentUser(id=1, email="admin@test.local", role="admin")
OPERATOR_USER = CurrentUser(id=2, email="operator@test.local", role="operator")


def _get_test_db() -> Generator[Session, None, None]:
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client_as_admin() -> Generator[TestClient, None, None]:
    app = create_app()
    app.dependency_overrides[get_db] = _get_test_db
    app.dependency_overrides[get_current_user] = lambda: ADMIN_USER
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def client_as_operator() -> Generator[TestClient, None, None]:
    app = create_app()
    app.dependency_overrides[get_db] = _get_test_db
    app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _reset_error_codes() -> Generator[None, None, None]:
    with _engine.begin() as conn:
        conn.execute(text("DELETE FROM item_errors"))
        conn.execute(text("DELETE FROM run_items"))
        conn.execute(text("DELETE FROM reconciliation_runs"))
        conn.execute(text("""
            UPDATE error_codes SET family_code = 'SIN_CLASIFICAR'
            WHERE code = '8541'
        """))
        conn.execute(text("""
            UPDATE error_codes SET family_code = 'AUTORIZACION_MARCA'
            WHERE code = '90220'
        """))
    yield


class TestGetErrorFamilies:
    def test_lists_families_and_codes(self, client_as_admin: TestClient) -> None:
        response = client_as_admin.get("/api/v1/error-families")

        assert response.status_code == 200
        body = response.json()
        assert "families" in body
        assert "codes" in body

        family_codes = {f["code"] for f in body["families"]}
        assert "AUTORIZACION_MARCA" in family_codes
        assert "GPSR" in family_codes

        codes_by_code = {c["code"]: c for c in body["codes"]}
        assert codes_by_code["8541"]["family_code"] == "SIN_CLASIFICAR"
        assert codes_by_code["90220"]["family_code"] == "AUTORIZACION_MARCA"

    def test_families_sorted_by_sort_order(self, client_as_admin: TestClient) -> None:
        response = client_as_admin.get("/api/v1/error-families")
        families = response.json()["families"]
        sort_orders = [f["sort_order"] for f in families]
        assert sort_orders == sorted(sort_orders)


class TestPatchErrorCode:
    def test_admin_can_reassign_family(self, client_as_admin: TestClient) -> None:
        response = client_as_admin.patch(
            "/api/v1/error-codes/8541",
            json={"family_code": "GPSR"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "8541"
        assert body["family_code"] == "GPSR"

        catalog = client_as_admin.get("/api/v1/error-families").json()
        updated = next(c for c in catalog["codes"] if c["code"] == "8541")
        assert updated["family_code"] == "GPSR"

    def test_operator_gets_403(self, client_as_operator: TestClient) -> None:
        response = client_as_operator.patch(
            "/api/v1/error-codes/8541",
            json={"family_code": "GPSR"},
        )

        assert response.status_code == 403

        catalog = client_as_operator.get("/api/v1/error-families").json()
        code = next(c for c in catalog["codes"] if c["code"] == "8541")
        assert code["family_code"] == "SIN_CLASIFICAR"

    def test_unknown_code_returns_404(self, client_as_admin: TestClient) -> None:
        response = client_as_admin.patch(
            "/api/v1/error-codes/99999",
            json={"family_code": "GPSR"},
        )
        assert response.status_code == 404

    def test_unknown_family_returns_422(self, client_as_admin: TestClient) -> None:
        response = client_as_admin.patch(
            "/api/v1/error-codes/8541",
            json={"family_code": "NO_EXISTE"},
        )
        assert response.status_code == 422

    def test_reassignment_reflected_in_vista1(
        self,
        client_as_admin: TestClient,
    ) -> None:
        db = _SessionLocal()
        try:
            db.execute(
                text("""
                    INSERT INTO reconciliation_runs
                        (id, user_id, marketplace, status, summary_metrics, completed_at)
                    VALUES (1, 1, 'amazon_es', 'completed', :metrics, '2026-06-10T10:00:00')
                """),
                {"metrics": json.dumps({"total_skus": 1, "total_errors": 2})},
            )
            db.execute(
                text("""
                    INSERT INTO run_items
                        (id, run_id, sku_norm, sku_raw, in_occ, in_feed, in_amazon_report,
                         sync_status, feed_stock)
                    VALUES (1, 1, 'SKU1', 'SKU1', 1, 1, 1, 'SENT_WITH_ERROR', 5)
                """),
            )
            db.execute(
                text("""
                    INSERT INTO item_errors (run_item_id, error_code, error_category, error_message)
                    VALUES
                        (1, '8541', 'ERROR', 'msg a'),
                        (1, '8541', 'ERROR', 'msg b'),
                        (1, '90220', 'ERROR', 'brand msg')
                """),
            )
            db.commit()
        finally:
            db.close()

        before = client_as_admin.get("/api/v1/runs/1/report/families").json()
        sin_before = next(
            f for f in before["families"] if f["code"] == "SIN_CLASIFICAR"
        )
        assert sin_before["total_errors"] == 2

        patch = client_as_admin.patch(
            "/api/v1/error-codes/8541",
            json={"family_code": "GPSR"},
        )
        assert patch.status_code == 200

        after = client_as_admin.get("/api/v1/runs/1/report/families").json()
        gpsr = next(f for f in after["families"] if f["code"] == "GPSR")
        assert gpsr["total_errors"] == 2
        sin_after = next(
            (f for f in after["families"] if f["code"] == "SIN_CLASIFICAR"),
            None,
        )
        assert sin_after is None or sin_after["total_errors"] == 0
