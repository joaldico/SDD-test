"""T-3.7 — Integration tests for GET /api/v1/runs/{run_id}/files/{file_id}/preview.

TDD: written BEFORE implementation (red → green → refactor).
Uses SQLite in-memory + a module-level staging directory within the workspace.

DoD:
  - Respuesta valida contra el contrato exacto del plan 3.7.
  - Los parsers T-3.2/T-3.3 son los que producen los datos (sin doble implementación).
  - Block info presente para amazon_report (xlsm).
  - Suggestions con reason para los 3 fixtures.
  - 404 para run/file inexistente.
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

# Staging directory for this test module (within the workspace — writable in sandbox)
_STAGING = Path(__file__).parent / ".staging_preview"
_STAGING.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# SQLite in-memory test database (same schema as test_runs_api.py)
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
# App fixture with dependency overrides
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db] = _get_test_db
    app.dependency_overrides[get_staging_dir] = lambda: _STAGING
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helper: upload a file and return (run_id, file_id)
# ---------------------------------------------------------------------------


def _upload_fixture(client: TestClient, path: Path, role: str) -> tuple[int, int]:
    """Create a run, upload a file, and return (run_id, file_id)."""
    run_resp = client.post("/api/v1/runs", json={})
    assert run_resp.status_code == 201, run_resp.text
    run_id: int = run_resp.json()["id"]

    data = path.read_bytes()
    ext = path.suffix.lower()
    mime_map = {
        ".csv": "text/csv",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsm": "application/vnd.ms-excel.sheet.macroenabled.12",
    }
    mime = mime_map.get(ext, "application/octet-stream")

    up_resp = client.post(
        f"/api/v1/runs/{run_id}/files",
        data={"role": role},
        files={"file": (path.name, io.BytesIO(data), mime)},
    )
    assert up_resp.status_code == 201, up_resp.text
    file_id: int = up_resp.json()["id"]
    return run_id, file_id


# ---------------------------------------------------------------------------
# T-3.7 — Preview contract tests
# ---------------------------------------------------------------------------


class TestPreviewCsv:
    """wavemarket_fullstock_anonymized.csv → role wm_feed (flat CSV)."""

    @pytest.fixture(scope="class")
    def ids(self, client: TestClient) -> tuple[int, int]:
        return _upload_fixture(client, CSV_FIXTURE, "wm_feed")

    def test_preview_returns_200(self, client: TestClient, ids: tuple[int, int]) -> None:
        run_id, file_id = ids
        resp = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview")
        assert resp.status_code == 200, resp.text

    def test_preview_file_role(self, client: TestClient, ids: tuple[int, int]) -> None:
        run_id, file_id = ids
        body = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview").json()
        assert body["file_role"] == "wm_feed"

    def test_preview_csv_no_available_sheets(self, client: TestClient, ids: tuple[int, int]) -> None:
        run_id, file_id = ids
        body = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview").json()
        assert body["available_sheets"] is None

    def test_preview_csv_no_block(self, client: TestClient, ids: tuple[int, int]) -> None:
        run_id, file_id = ids
        body = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview").json()
        assert body["block"] is None

    def test_preview_csv_has_headers(self, client: TestClient, ids: tuple[int, int]) -> None:
        run_id, file_id = ids
        body = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview").json()
        assert len(body["headers"]) > 0
        # Each header must have index and name
        for h in body["headers"]:
            assert "index" in h
            assert "name" in h

    def test_preview_csv_has_sample_rows(self, client: TestClient, ids: tuple[int, int]) -> None:
        run_id, file_id = ids
        body = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview").json()
        assert len(body["sample_rows"]) > 0

    def test_preview_csv_has_sku_suggestion(self, client: TestClient, ids: tuple[int, int]) -> None:
        run_id, file_id = ids
        body = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview").json()
        # CSV has SKU column — suggester must find it
        assert "sku" in body["suggestions"]
        assert body["suggestions"]["sku"]["reason"] != ""
        assert 0.0 < body["suggestions"]["sku"]["confidence"] <= 1.0

    def test_preview_csv_has_stock_suggestion(self, client: TestClient, ids: tuple[int, int]) -> None:
        run_id, file_id = ids
        body = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview").json()
        assert "stock" in body["suggestions"]
        assert body["suggestions"]["stock"]["reason"] != ""

    def test_preview_discarded_rows_present(self, client: TestClient, ids: tuple[int, int]) -> None:
        run_id, file_id = ids
        body = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview").json()
        assert "discarded_rows" in body
        assert isinstance(body["discarded_rows"], int)


class TestPreviewXlsx:
    """occ_top_sales_anonymized.xlsx → role occ_top (Plantilla sheet)."""

    @pytest.fixture(scope="class")
    def ids(self, client: TestClient) -> tuple[int, int]:
        return _upload_fixture(client, XLSX_FIXTURE, "occ_top")

    def test_preview_returns_200(self, client: TestClient, ids: tuple[int, int]) -> None:
        run_id, file_id = ids
        resp = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview")
        assert resp.status_code == 200, resp.text

    def test_preview_xlsx_file_role(self, client: TestClient, ids: tuple[int, int]) -> None:
        run_id, file_id = ids
        body = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview").json()
        assert body["file_role"] == "occ_top"

    def test_preview_xlsx_has_available_sheets(self, client: TestClient, ids: tuple[int, int]) -> None:
        run_id, file_id = ids
        body = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview").json()
        assert body["available_sheets"] is not None
        assert len(body["available_sheets"]) > 0
        for s in body["available_sheets"]:
            assert "name" in s
            assert "rows" in s

    def test_preview_xlsx_has_headers(self, client: TestClient, ids: tuple[int, int]) -> None:
        run_id, file_id = ids
        body = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview").json()
        assert len(body["headers"]) > 0

    def test_preview_xlsx_has_sku_suggestion(self, client: TestClient, ids: tuple[int, int]) -> None:
        run_id, file_id = ids
        body = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview").json()
        assert "sku" in body["suggestions"]
        assert body["suggestions"]["sku"]["reason"] != ""

    def test_preview_xlsx_sheet_name_set(self, client: TestClient, ids: tuple[int, int]) -> None:
        run_id, file_id = ids
        body = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview").json()
        assert body["sheet"] is not None

    def test_preview_xlsx_discarded_rows_is_integer(
        self, client: TestClient, ids: tuple[int, int],
    ) -> None:
        """discarded_rows is always present and is a non-negative integer.

        The anonymized occ_top fixture is a plain spreadsheet (no Plantilla/ABC123
        structure), so discarded_rows == 0 is expected.  The parse_plantilla path
        (EB-04) is covered in test_block_locator.py using the relevant fixture.
        """
        run_id, file_id = ids
        body = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview").json()
        assert isinstance(body["discarded_rows"], int)
        assert body["discarded_rows"] >= 0


class TestPreviewXlsm:
    """amazon_processing_summary_anonymized.xlsm → role amazon_report."""

    @pytest.fixture(scope="class")
    def ids(self, client: TestClient) -> tuple[int, int]:
        return _upload_fixture(client, XLSM_FIXTURE, "amazon_report")

    def test_preview_returns_200(self, client: TestClient, ids: tuple[int, int]) -> None:
        run_id, file_id = ids
        resp = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview")
        assert resp.status_code == 200, resp.text

    def test_preview_xlsm_file_role(self, client: TestClient, ids: tuple[int, int]) -> None:
        run_id, file_id = ids
        body = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview").json()
        assert body["file_role"] == "amazon_report"

    def test_preview_xlsm_has_block(self, client: TestClient, ids: tuple[int, int]) -> None:
        """BlockLocator must find 'Errores y advertencias por SKU' (EB-02)."""
        run_id, file_id = ids
        body = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview").json()
        assert body["block"] is not None
        assert "data_start_row" in body["block"]
        assert body["block"]["data_start_row"] > 0

    def test_preview_xlsm_block_title_matched(self, client: TestClient, ids: tuple[int, int]) -> None:
        run_id, file_id = ids
        body = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview").json()
        title = body["block"]["title_matched"].lower()
        assert "errores" in title

    def test_preview_xlsm_has_headers(self, client: TestClient, ids: tuple[int, int]) -> None:
        run_id, file_id = ids
        body = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview").json()
        assert len(body["headers"]) > 0

    def test_preview_xlsm_has_sku_suggestion(self, client: TestClient, ids: tuple[int, int]) -> None:
        run_id, file_id = ids
        body = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview").json()
        assert "sku" in body["suggestions"]
        assert body["suggestions"]["sku"]["confidence"] > 0.5

    def test_preview_xlsm_has_available_sheets(self, client: TestClient, ids: tuple[int, int]) -> None:
        run_id, file_id = ids
        body = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview").json()
        assert body["available_sheets"] is not None
        sheet_names = [s["name"] for s in body["available_sheets"]]
        assert len(sheet_names) > 0

    def test_preview_sheet_param_selects_different_sheet(
        self, client: TestClient, ids: tuple[int, int],
    ) -> None:
        """?sheet= query param must select a different sheet."""
        run_id, file_id = ids
        body = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview").json()
        sheets = body["available_sheets"]
        if len(sheets) > 1:
            other_sheet = sheets[1]["name"]
            resp2 = client.get(
                f"/api/v1/runs/{run_id}/files/{file_id}/preview?sheet={other_sheet}",
            )
            assert resp2.status_code == 200
            assert resp2.json()["sheet"] == other_sheet


class TestPreviewErrors:
    """Error scenarios for the preview endpoint."""

    def test_preview_unknown_run_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/runs/99999/files/1/preview")
        assert resp.status_code == 404

    def test_preview_unknown_file_returns_404(self, client: TestClient) -> None:
        run_resp = client.post("/api/v1/runs", json={})
        run_id = run_resp.json()["id"]
        resp = client.get(f"/api/v1/runs/{run_id}/files/99999/preview")
        assert resp.status_code == 404

    def test_preview_file_belonging_to_different_run_returns_404(
        self, client: TestClient,
    ) -> None:
        """file_id that exists but belongs to a different run → 404."""
        run1_resp = client.post("/api/v1/runs", json={})
        run2_resp = client.post("/api/v1/runs", json={})
        run1_id = run1_resp.json()["id"]
        run2_id = run2_resp.json()["id"]

        data = CSV_FIXTURE.read_bytes()
        up_resp = client.post(
            f"/api/v1/runs/{run1_id}/files",
            data={"role": "wm_feed"},
            files={"file": ("file.csv", io.BytesIO(data), "text/csv")},
        )
        file_id = up_resp.json()["id"]

        resp = client.get(f"/api/v1/runs/{run2_id}/files/{file_id}/preview")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Cleanup staging directory after all tests in this module
# ---------------------------------------------------------------------------


def teardown_module(module: object) -> None:  # noqa: ARG001
    shutil.rmtree(_STAGING, ignore_errors=True)
