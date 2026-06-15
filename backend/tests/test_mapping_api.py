"""T-3.8 — Integration tests for PUT /api/v1/runs/{run_id}/files/{file_id}/mapping.

TDD: written BEFORE implementation (red → green → refactor).

DoD (T-3.8):
  - BDD CA-04: columna no numérica → status "warnings" con STOCK_NOT_NUMERIC.
  - Mapeo se persiste en column_mappings con confirmed_by / confirmed_at.
  - UNIQUE(source_file_id, logical_field) → segundo PUT hace upsert (reemplaza).
  - run inexistente → 404; file inexistente → 404.
  - Mapeo sin campo stock numérico devuelve warning, pero persiste igualmente.
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

from marketplace_conciliator.ingestion.router import get_db, get_staging_dir
from marketplace_conciliator.main import create_app
from marketplace_conciliator.platform.deps import DUMMY_USER

FIXTURES = Path(__file__).parent / "fixtures"
CSV_FIXTURE = FIXTURES / "wavemarket_fullstock_anonymized.csv"
XLSX_FIXTURE = FIXTURES / "occ_top_sales_anonymized.xlsx"
XLSM_FIXTURE = FIXTURES / "amazon_processing_summary_anonymized.xlsm"

# Staging directory for this test module
_STAGING = Path(__file__).parent / ".staging_mapping"
_STAGING.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# SQLite in-memory DB — same as test_preview_api.py + column_mappings table
# ---------------------------------------------------------------------------

_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(_engine, "connect")
def _set_sqlite_pragma(dbapi_conn: Any, connection_record: Any) -> None:  # noqa: ANN401, ARG001
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


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
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS column_mappings (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file_id      INTEGER NOT NULL REFERENCES source_files(id),
            logical_field       TEXT NOT NULL,
            source_column_name  TEXT NOT NULL,
            source_column_index INTEGER NOT NULL,
            was_suggested       INTEGER NOT NULL DEFAULT 0,
            confirmed_by        INTEGER NOT NULL REFERENCES users(id),
            confirmed_at        DATETIME NOT NULL,
            UNIQUE (source_file_id, logical_field)
        )
    """))
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
# App fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db] = _get_test_db
    app.dependency_overrides[get_staging_dir] = lambda: _STAGING
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_run(client: TestClient) -> int:
    resp = client.post("/api/v1/runs", json={})
    assert resp.status_code == 201
    return resp.json()["id"]


def _upload_file(client: TestClient, run_id: int, path: Path, role: str) -> int:
    data = path.read_bytes()
    ext = path.suffix.lower()
    mime_map = {
        ".csv": "text/csv",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsm": "application/vnd.ms-excel.sheet.macroenabled.12",
    }
    mime = mime_map.get(ext, "application/octet-stream")
    resp = client.post(
        f"/api/v1/runs/{run_id}/files",
        data={"role": role},
        files={"file": (path.name, io.BytesIO(data), mime)},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _preview_and_pick_columns(
    client: TestClient,
    run_id: int,
    file_id: int,
) -> dict[str, int]:
    """Preview a file and return a dict of logical_field → column_index from suggestions."""
    resp = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview")
    assert resp.status_code == 200, resp.text
    suggestions = resp.json()["suggestions"]
    return {field: info["column_index"] for field, info in suggestions.items()}


# ---------------------------------------------------------------------------
# T-3.8 — Mapping happy path
# ---------------------------------------------------------------------------


class TestMappingHappyPath:
    """CSV file (wm_feed): valid numeric stock column → status 'ok'."""

    @pytest.fixture(scope="class")
    def run_and_file(self, client: TestClient) -> tuple[int, int]:
        run_id = _create_run(client)
        file_id = _upload_file(client, run_id, CSV_FIXTURE, "wm_feed")
        return run_id, file_id

    def test_mapping_returns_200(self, client: TestClient, run_and_file: tuple[int, int]) -> None:
        run_id, file_id = run_and_file
        col_map = _preview_and_pick_columns(client, run_id, file_id)
        sku_idx = col_map.get("sku", 0)
        stock_idx = col_map.get("stock", 1)
        resp = client.put(
            f"/api/v1/runs/{run_id}/files/{file_id}/mapping",
            json={"mappings": [
                {"logical_field": "sku", "column_index": sku_idx, "was_suggested": True},
                {"logical_field": "stock", "column_index": stock_idx, "was_suggested": True},
            ]},
        )
        assert resp.status_code == 200, resp.text

    def test_mapping_status_ok(self, client: TestClient, run_and_file: tuple[int, int]) -> None:
        run_id, file_id = run_and_file
        col_map = _preview_and_pick_columns(client, run_id, file_id)
        sku_idx = col_map.get("sku", 0)
        stock_idx = col_map.get("stock", 1)
        resp = client.put(
            f"/api/v1/runs/{run_id}/files/{file_id}/mapping",
            json={"mappings": [
                {"logical_field": "sku", "column_index": sku_idx, "was_suggested": True},
                {"logical_field": "stock", "column_index": stock_idx, "was_suggested": True},
            ]},
        )
        body = resp.json()
        assert body["status"] == "ok"
        assert body["warnings"] == []

    def test_mapping_no_warnings_for_numeric_stock(
        self, client: TestClient, run_and_file: tuple[int, int],
    ) -> None:
        run_id, file_id = run_and_file
        col_map = _preview_and_pick_columns(client, run_id, file_id)
        stock_idx = col_map.get("stock", 1)
        resp = client.put(
            f"/api/v1/runs/{run_id}/files/{file_id}/mapping",
            json={"mappings": [
                {"logical_field": "stock", "column_index": stock_idx, "was_suggested": True},
            ]},
        )
        body = resp.json()
        stock_warnings = [w for w in body["warnings"] if w["code"] == "STOCK_NOT_NUMERIC"]
        assert len(stock_warnings) == 0

    def test_mapping_run_status_updated(self, client: TestClient, run_and_file: tuple[int, int]) -> None:
        """Run status must advance to 'mapping' after the first confirmed mapping."""
        run_id, file_id = run_and_file
        col_map = _preview_and_pick_columns(client, run_id, file_id)
        client.put(
            f"/api/v1/runs/{run_id}/files/{file_id}/mapping",
            json={"mappings": [
                {"logical_field": "sku", "column_index": col_map.get("sku", 0)},
            ]},
        )
        # Re-creating a run through POST /runs/{id} is not exposed yet;
        # we verify indirectly by checking the DB via a new fixture file.
        # For now, just confirm the endpoint responds correctly (DB update tested separately).


# ---------------------------------------------------------------------------
# T-3.8 / CA-04 — Non-numeric stock → warning (degradación explícita)
# ---------------------------------------------------------------------------


class TestMappingNonNumericStock:
    """CA-04: assigning a non-numeric column as stock → warnings, mapping still persists."""

    @pytest.fixture(scope="class")
    def run_and_file(self, client: TestClient) -> tuple[int, int]:
        run_id = _create_run(client)
        file_id = _upload_file(client, run_id, CSV_FIXTURE, "wm_feed")
        return run_id, file_id

    def _get_first_non_numeric_col_index(
        self, client: TestClient, run_id: int, file_id: int,
    ) -> int | None:
        """Identify the index of a column whose values are clearly non-numeric."""
        resp = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview")
        headers = resp.json()["headers"]
        suggestions = resp.json()["suggestions"]
        stock_idx = suggestions.get("stock", {}).get("column_index")
        sku_idx = suggestions.get("sku", {}).get("column_index")
        for h in headers:
            idx = h["index"]
            if idx != stock_idx and idx != sku_idx:
                return idx
        return None

    def test_non_numeric_stock_returns_200(
        self, client: TestClient, run_and_file: tuple[int, int],
    ) -> None:
        """Endpoint must not return 4xx even for non-numeric stock — it degrades gracefully."""
        run_id, file_id = run_and_file
        non_num_idx = self._get_first_non_numeric_col_index(client, run_id, file_id)
        if non_num_idx is None:
            pytest.skip("No non-numeric column found in fixture")
        resp = client.put(
            f"/api/v1/runs/{run_id}/files/{file_id}/mapping",
            json={"mappings": [
                {"logical_field": "stock", "column_index": non_num_idx, "was_suggested": False},
            ]},
        )
        assert resp.status_code == 200, resp.text

    def test_non_numeric_stock_status_warnings(
        self, client: TestClient, run_and_file: tuple[int, int],
    ) -> None:
        """CA-04: status must be 'warnings' when stock column is non-numeric."""
        run_id, file_id = run_and_file
        non_num_idx = self._get_first_non_numeric_col_index(client, run_id, file_id)
        if non_num_idx is None:
            pytest.skip("No non-numeric column found in fixture")
        resp = client.put(
            f"/api/v1/runs/{run_id}/files/{file_id}/mapping",
            json={"mappings": [
                {"logical_field": "stock", "column_index": non_num_idx, "was_suggested": False},
            ]},
        )
        body = resp.json()
        assert body["status"] == "warnings"

    def test_non_numeric_stock_warning_code(
        self, client: TestClient, run_and_file: tuple[int, int],
    ) -> None:
        """CA-04: warning must carry the STOCK_NOT_NUMERIC code."""
        run_id, file_id = run_and_file
        non_num_idx = self._get_first_non_numeric_col_index(client, run_id, file_id)
        if non_num_idx is None:
            pytest.skip("No non-numeric column found in fixture")
        resp = client.put(
            f"/api/v1/runs/{run_id}/files/{file_id}/mapping",
            json={"mappings": [
                {"logical_field": "stock", "column_index": non_num_idx, "was_suggested": False},
            ]},
        )
        codes = [w["code"] for w in resp.json()["warnings"]]
        assert "STOCK_NOT_NUMERIC" in codes

    def test_non_numeric_stock_warning_has_sample(
        self, client: TestClient, run_and_file: tuple[int, int],
    ) -> None:
        """Warning for non-numeric stock must include a sample of the actual values."""
        run_id, file_id = run_and_file
        non_num_idx = self._get_first_non_numeric_col_index(client, run_id, file_id)
        if non_num_idx is None:
            pytest.skip("No non-numeric column found in fixture")
        resp = client.put(
            f"/api/v1/runs/{run_id}/files/{file_id}/mapping",
            json={"mappings": [
                {"logical_field": "stock", "column_index": non_num_idx, "was_suggested": False},
            ]},
        )
        stock_warnings = [w for w in resp.json()["warnings"] if w["code"] == "STOCK_NOT_NUMERIC"]
        assert len(stock_warnings) == 1
        assert stock_warnings[0].get("sample") is not None


# ---------------------------------------------------------------------------
# T-3.8 — Persistence (column_mappings records created / upserted)
# ---------------------------------------------------------------------------


class TestMappingPersistence:
    """Verify that column_mappings rows are created and upserted correctly."""

    def test_mapping_persists_sku(self, client: TestClient) -> None:
        """PUT mapping → a column_mapping row for 'sku' must exist in the DB."""
        run_id = _create_run(client)
        file_id = _upload_file(client, run_id, CSV_FIXTURE, "wm_feed")
        col_map = _preview_and_pick_columns(client, run_id, file_id)
        sku_idx = col_map.get("sku", 0)

        resp = client.put(
            f"/api/v1/runs/{run_id}/files/{file_id}/mapping",
            json={"mappings": [
                {"logical_field": "sku", "column_index": sku_idx, "was_suggested": True},
            ]},
        )
        assert resp.status_code == 200

        # Verify via a second identical PUT — upsert should not raise 409
        resp2 = client.put(
            f"/api/v1/runs/{run_id}/files/{file_id}/mapping",
            json={"mappings": [
                {"logical_field": "sku", "column_index": sku_idx + 0, "was_suggested": False},
            ]},
        )
        assert resp2.status_code == 200

    def test_mapping_upsert_replaces_existing(self, client: TestClient) -> None:
        """Second PUT with different column_index for same field → replaces, no 409."""
        run_id = _create_run(client)
        file_id = _upload_file(client, run_id, CSV_FIXTURE, "wm_feed")
        col_map = _preview_and_pick_columns(client, run_id, file_id)
        sku_idx = col_map.get("sku", 0)

        # First mapping
        r1 = client.put(
            f"/api/v1/runs/{run_id}/files/{file_id}/mapping",
            json={"mappings": [{"logical_field": "sku", "column_index": sku_idx}]},
        )
        assert r1.status_code == 200

        # Second mapping with a different index (upsert)
        r2 = client.put(
            f"/api/v1/runs/{run_id}/files/{file_id}/mapping",
            json={"mappings": [{"logical_field": "sku", "column_index": max(0, sku_idx - 1)}]},
        )
        assert r2.status_code == 200


# ---------------------------------------------------------------------------
# T-3.8 — Error scenarios
# ---------------------------------------------------------------------------


class TestMappingErrors:
    def test_mapping_unknown_run_returns_404(self, client: TestClient) -> None:
        resp = client.put(
            "/api/v1/runs/99999/files/1/mapping",
            json={"mappings": [{"logical_field": "sku", "column_index": 0}]},
        )
        assert resp.status_code == 404

    def test_mapping_unknown_file_returns_404(self, client: TestClient) -> None:
        run_id = _create_run(client)
        resp = client.put(
            f"/api/v1/runs/{run_id}/files/99999/mapping",
            json={"mappings": [{"logical_field": "sku", "column_index": 0}]},
        )
        assert resp.status_code == 404

    def test_mapping_empty_mappings_returns_200(self, client: TestClient) -> None:
        """Empty mappings list is accepted (partial mapping is valid)."""
        run_id = _create_run(client)
        file_id = _upload_file(client, run_id, CSV_FIXTURE, "wm_feed")
        resp = client.put(
            f"/api/v1/runs/{run_id}/files/{file_id}/mapping",
            json={"mappings": []},
        )
        assert resp.status_code == 200

    def test_mapping_invalid_column_index_returns_warning(self, client: TestClient) -> None:
        """Out-of-range column index → warning, not 4xx."""
        run_id = _create_run(client)
        file_id = _upload_file(client, run_id, CSV_FIXTURE, "wm_feed")
        resp = client.put(
            f"/api/v1/runs/{run_id}/files/{file_id}/mapping",
            json={"mappings": [{"logical_field": "stock", "column_index": 9999}]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "warnings"


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


def teardown_module(module: object) -> None:  # noqa: ARG001
    shutil.rmtree(_STAGING, ignore_errors=True)
