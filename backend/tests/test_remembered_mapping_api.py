"""T-5.5 — Integration tests for remembered column mapping by header fingerprint (RF-12).

TDD: written BEFORE implementation.

DoD:
  - Second run with same fixture pre-fills remembered_mappings from first confirmed mapping.
  - Mapping still requires explicit confirmation (POST /process → 409 without it).
"""

from __future__ import annotations

import io
import shutil
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from marketplace_conciliator.ingestion.router import get_db, get_db_factory, get_staging_dir, get_task_runner
from marketplace_conciliator.main import create_app
from marketplace_conciliator.platform.deps import DUMMY_USER

FIXTURES = Path(__file__).parent / "fixtures"
CSV_FIXTURE = FIXTURES / "wavemarket_fullstock_anonymized.csv"

_STAGING = Path(__file__).parent / ".staging_remembered"
_STAGING.mkdir(parents=True, exist_ok=True)

_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(_engine, "connect")
def _set_sqlite_pragma(dbapi_conn: Any, _: Any) -> None:  # noqa: ANN401
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


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
            header_fingerprint TEXT,
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
            confirmed_at DATETIME NOT NULL,
            UNIQUE (source_file_id, logical_field)
        )
    """))
    conn.execute(text("""
        INSERT OR IGNORE INTO users (id, email, role, hashed_password)
        VALUES (:id, :email, :role, 'dummy')
    """), {"id": DUMMY_USER.id, "email": DUMMY_USER.email, "role": DUMMY_USER.role})

_SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


class _NoOpTaskRunner:
    def submit(self, run_id: int, work_fn: object) -> None:
        pass


def _get_test_db() -> Generator[Session, None, None]:
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    shutil.rmtree(_STAGING, ignore_errors=True)
    _STAGING.mkdir(parents=True, exist_ok=True)
    app = create_app()
    app.dependency_overrides[get_db] = _get_test_db
    app.dependency_overrides[get_staging_dir] = lambda: _STAGING
    app.dependency_overrides[get_task_runner] = lambda: _NoOpTaskRunner()
    app.dependency_overrides[get_db_factory] = lambda: _SessionLocal
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _create_run(client: TestClient) -> int:
    resp = client.post("/api/v1/runs", json={})
    assert resp.status_code == 201
    return resp.json()["id"]


def _upload_csv(client: TestClient, run_id: int) -> int:
    data = CSV_FIXTURE.read_bytes()
    resp = client.post(
        f"/api/v1/runs/{run_id}/files",
        data={"role": "wm_feed"},
        files={"file": (CSV_FIXTURE.name, io.BytesIO(data), "text/csv")},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _confirm_wm_feed_mapping(client: TestClient, run_id: int, file_id: int) -> None:
    preview = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview").json()
    mappings = [
        {
            "logical_field": field,
            "column_index": preview["suggestions"][field]["column_index"],
            "was_suggested": True,
        }
        for field in ("sku", "stock")
        if field in preview["suggestions"]
    ]
    resp = client.put(
        f"/api/v1/runs/{run_id}/files/{file_id}/mapping",
        json={"mappings": mappings},
    )
    assert resp.status_code == 200, resp.text


class TestRememberedMapping:
    def test_first_preview_has_no_remembered_mappings(self, client: TestClient) -> None:
        run_id = _create_run(client)
        file_id = _upload_csv(client, run_id)
        preview = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview").json()
        assert preview.get("remembered_mappings") == {}

    def test_second_run_prefills_remembered_mappings(self, client: TestClient) -> None:
        run1 = _create_run(client)
        file1 = _upload_csv(client, run1)
        _confirm_wm_feed_mapping(client, run1, file1)

        run2 = _create_run(client)
        file2 = _upload_csv(client, run2)
        preview = client.get(f"/api/v1/runs/{run2}/files/{file2}/preview").json()

        assert "sku" in preview["remembered_mappings"]
        assert "stock" in preview["remembered_mappings"]
        assert preview["remembered_mappings"]["sku"]["from_run_id"] == run1
        assert preview["remembered_mappings"]["sku"]["reason"] != ""

        db = _SessionLocal()
        try:
            row = db.execute(
                text("SELECT source_column_index FROM column_mappings WHERE source_file_id = :fid AND logical_field = 'sku'"),
                {"fid": file1},
            ).fetchone()
            assert row is not None
            assert preview["remembered_mappings"]["sku"]["column_index"] == row[0]
        finally:
            db.close()

    def test_process_still_requires_confirmation_on_second_run(self, client: TestClient) -> None:
        run1 = _create_run(client)
        file1 = _upload_csv(client, run1)
        _confirm_wm_feed_mapping(client, run1, file1)

        run2 = _create_run(client)
        _upload_csv(client, run2)

        resp = client.post(f"/api/v1/runs/{run2}/process")
        assert resp.status_code == 409
        assert "mapeo pendiente" in resp.json()["detail"].lower()
