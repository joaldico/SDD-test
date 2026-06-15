"""T-3.6 — Integration tests for POST /api/v1/runs and POST /api/v1/runs/{id}/files.

TDD: written BEFORE implementation.
Uses SQLite in-memory via dependency override; no Docker required.

DoD:
  - Subir los 3 fixtures crea source_files con sha256 y unique (run_id, role).
  - >50 MB → 413.
  - run_id inválido → 404.
"""

from __future__ import annotations

import hashlib
import io
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from marketplace_conciliator.ingestion.router import get_db
from marketplace_conciliator.main import create_app
from marketplace_conciliator.platform.deps import DUMMY_USER

FIXTURES = Path(__file__).parent / "fixtures"
CSV_FIXTURE = FIXTURES / "wavemarket_fullstock_anonymized.csv"
XLSX_FIXTURE = FIXTURES / "occ_top_sales_anonymized.xlsx"
XLSM_FIXTURE = FIXTURES / "amazon_processing_summary_anonymized.xlsm"

# ---------------------------------------------------------------------------
# SQLite in-memory test database — schema created with portable raw SQL
# so that MySQL ENUM dialect types are replaced by TEXT/VARCHAR.
# ---------------------------------------------------------------------------

_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    # StaticPool ensures all sessions reuse the same in-memory connection so
    # tables created at module import are visible during test execution.
    poolclass=StaticPool,
)


@event.listens_for(_engine, "connect")
def _set_sqlite_pragma(dbapi_conn: Any, connection_record: Any) -> None:  # noqa: ANN401, ARG001
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# Create all tables needed for the upload flow using SQLite-compatible DDL
with _engine.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            email   TEXT NOT NULL UNIQUE,
            role    TEXT NOT NULL,
            hashed_password TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS reconciliation_runs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            marketplace TEXT NOT NULL DEFAULT 'amazon_es',
            status      TEXT NOT NULL,
            phase       TEXT,
            failure_reason TEXT,
            summary_metrics TEXT,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS source_files (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id              INTEGER NOT NULL REFERENCES reconciliation_runs(id),
            role                TEXT NOT NULL,
            original_filename   TEXT NOT NULL,
            sha256              TEXT NOT NULL,
            detected_encoding   TEXT,
            detected_delimiter  TEXT,
            sheet_name          TEXT,
            data_start_row      INTEGER,
            total_rows          INTEGER NOT NULL DEFAULT 0,
            discarded_rows      INTEGER NOT NULL DEFAULT 0,
            uploaded_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (run_id, role)
        )
    """))
    # Seed the dummy admin user
    conn.execute(text("""
        INSERT OR IGNORE INTO users (id, email, role, hashed_password)
        VALUES (:id, :email, :role, 'dummy')
    """), {"id": DUMMY_USER.id, "email": DUMMY_USER.email, "role": DUMMY_USER.role})

_TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def _get_test_db() -> Generator[Session, None, None]:
    db = _TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# App fixture with overridden DB dependency
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db] = _get_test_db
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# POST /api/v1/runs
# ---------------------------------------------------------------------------


class TestCreateRun:
    def test_create_run_returns_201(self, client: TestClient) -> None:
        resp = client.post("/api/v1/runs", json={"marketplace": "amazon_es"})
        assert resp.status_code == 201

    def test_create_run_response_has_id_and_status(self, client: TestClient) -> None:
        resp = client.post("/api/v1/runs", json={"marketplace": "amazon_es"})
        body = resp.json()
        assert "id" in body
        assert body["status"] == "uploaded"

    def test_create_run_default_marketplace(self, client: TestClient) -> None:
        resp = client.post("/api/v1/runs", json={})
        assert resp.status_code == 201
        assert resp.json()["marketplace"] == "amazon_es"


# ---------------------------------------------------------------------------
# POST /api/v1/runs/{id}/files
# ---------------------------------------------------------------------------


class TestUploadFile:
    def _create_run(self, client: TestClient) -> int:
        resp = client.post("/api/v1/runs", json={})
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_upload_csv_creates_source_file(self, client: TestClient) -> None:
        run_id = self._create_run(client)
        data = CSV_FIXTURE.read_bytes()
        resp = client.post(
            f"/api/v1/runs/{run_id}/files",
            data={"role": "wm_feed"},
            files={"file": ("wavemarket_fullstock_anonymized.csv", io.BytesIO(data), "text/csv")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["run_id"] == run_id
        assert body["role"] == "wm_feed"
        assert body["sha256"] == _sha256_of(CSV_FIXTURE)

    def test_upload_xlsx_creates_source_file(self, client: TestClient) -> None:
        run_id = self._create_run(client)
        data = XLSX_FIXTURE.read_bytes()
        resp = client.post(
            f"/api/v1/runs/{run_id}/files",
            data={"role": "occ_top"},
            files={
                "file": (
                    "occ_top_sales_anonymized.xlsx",
                    io.BytesIO(data),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            },
        )
        assert resp.status_code == 201
        assert resp.json()["sha256"] == _sha256_of(XLSX_FIXTURE)

    def test_upload_xlsm_creates_source_file(self, client: TestClient) -> None:
        run_id = self._create_run(client)
        data = XLSM_FIXTURE.read_bytes()
        resp = client.post(
            f"/api/v1/runs/{run_id}/files",
            data={"role": "amazon_report"},
            files={
                "file": (
                    "amazon_processing_summary_anonymized.xlsm",
                    io.BytesIO(data),
                    "application/vnd.ms-excel.sheet.macroenabled.12",
                ),
            },
        )
        assert resp.status_code == 201
        assert resp.json()["sha256"] == _sha256_of(XLSM_FIXTURE)

    def test_upload_duplicate_role_returns_409(self, client: TestClient) -> None:
        """UNIQUE(run_id, role) must be enforced: second upload of same role → 409."""
        run_id = self._create_run(client)
        data = CSV_FIXTURE.read_bytes()
        for _ in range(2):
            resp = client.post(
                f"/api/v1/runs/{run_id}/files",
                data={"role": "wm_feed"},
                files={"file": ("file.csv", io.BytesIO(data), "text/csv")},
            )
        assert resp.status_code == 409

    def test_upload_invalid_run_returns_404(self, client: TestClient) -> None:
        data = CSV_FIXTURE.read_bytes()
        resp = client.post(
            "/api/v1/runs/99999/files",
            data={"role": "wm_feed"},
            files={"file": ("file.csv", io.BytesIO(data), "text/csv")},
        )
        assert resp.status_code == 404

    def test_upload_over_50mb_returns_413(self, client: TestClient) -> None:
        """RNF-05: files > 50 MB must be rejected with 413."""
        run_id = self._create_run(client)
        big_data = b"x" * (50 * 1024 * 1024 + 1)  # 50 MB + 1 byte
        resp = client.post(
            f"/api/v1/runs/{run_id}/files",
            data={"role": "wm_feed"},
            files={"file": ("big.csv", io.BytesIO(big_data), "text/csv")},
        )
        assert resp.status_code == 413

    def test_upload_invalid_role_returns_422(self, client: TestClient) -> None:
        run_id = self._create_run(client)
        data = CSV_FIXTURE.read_bytes()
        resp = client.post(
            f"/api/v1/runs/{run_id}/files",
            data={"role": "invalid_role"},
            files={"file": ("file.csv", io.BytesIO(data), "text/csv")},
        )
        assert resp.status_code == 422

    def test_all_three_fixtures_create_source_files_with_sha256(
        self, client: TestClient,
    ) -> None:
        """Core DoD: uploading all 3 fixture files creates source_files with correct sha256."""
        run_id = self._create_run(client)
        uploads = [
            (CSV_FIXTURE, "wm_feed", "text/csv"),
            (XLSX_FIXTURE, "occ_top", "application/xlsx"),
            (XLSM_FIXTURE, "amazon_report", "application/xlsm"),
        ]
        for path, role, mime in uploads:
            data = path.read_bytes()
            resp = client.post(
                f"/api/v1/runs/{run_id}/files",
                data={"role": role},
                files={"file": (path.name, io.BytesIO(data), mime)},
            )
            assert resp.status_code == 201, f"Failed for role={role}: {resp.text}"
            assert resp.json()["sha256"] == _sha256_of(path)
