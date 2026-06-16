"""T-4.2 — BDD CA-03: Detección y resolución explícita de duplicados (gate Hito M4).

Suite pytest-bdd ejecutando literalmente los 4 escenarios Gherkin del spec 2.11
(CA-03) sobre la API real (TestClient + SQLite in-memory).

Escenarios cubiertos:
  1. Filas idénticas en el feed se colapsan y se reportan
     (collapsed_identical, duplicate_findings, stock preservado)
  2. Stock en conflicto en el feed — nunca se suma
     (kept_max_stock, stock_conflict=True, MAX(stock) aplicado)
  3. Duplicado en Libro1 conserva la primera ocurrencia
     (kept_first, datos de la primera fila conservados)
  4. Múltiples errores por SKU no se tratan como duplicados
     (1:N cardinality respected, item_errors populated, no duplicate_finding)

DoD: CA-03 100% verde; los Gherkin del spec se ejecutan literalmente sin reescritura.
"""

from __future__ import annotations

import io
import json
import shutil
from collections.abc import Generator
from pathlib import Path
from typing import Any

import openpyxl
import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from marketplace_conciliator.ingestion.router import get_db, get_db_factory, get_staging_dir, get_task_runner
from marketplace_conciliator.main import create_app
from marketplace_conciliator.platform.deps import DUMMY_USER

# ── Link feature file ────────────────────────────────────────────────────────

scenarios("../features/ca_03_deduplication.feature")

# ── Staging directory ────────────────────────────────────────────────────────

_STAGING = Path(__file__).parent.parent / ".staging_bdd_ca03"
_STAGING.mkdir(parents=True, exist_ok=True)

# ── SQLite in-memory DB ──────────────────────────────────────────────────────

_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(_engine, "connect")
def _set_pragma(dbapi_conn: Any, _: Any) -> None:  # noqa: ANN401
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


with _engine.begin() as _conn:
    _conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL,
            hashed_password TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """))
    _conn.execute(text("""
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
    _conn.execute(text("""
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
    _conn.execute(text("""
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
    _conn.execute(text("""
        CREATE TABLE IF NOT EXISTS run_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL REFERENCES reconciliation_runs(id),
            sku_norm TEXT NOT NULL,
            sku_raw TEXT NOT NULL,
            in_occ INTEGER NOT NULL DEFAULT 0,
            in_feed INTEGER NOT NULL DEFAULT 0,
            in_amazon_report INTEGER NOT NULL DEFAULT 0,
            sync_status TEXT NOT NULL DEFAULT 'NOT_SENT',
            feed_stock INTEGER,
            occ_stock INTEGER,
            stock_conflict INTEGER NOT NULL DEFAULT 0,
            submission_status TEXT,
            UNIQUE (run_id, sku_norm)
        )
    """))
    _conn.execute(text("""
        CREATE TABLE IF NOT EXISTS duplicate_findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file_id INTEGER NOT NULL REFERENCES source_files(id),
            sku_norm TEXT NOT NULL,
            occurrences INTEGER NOT NULL,
            resolution TEXT NOT NULL,
            discarded_values TEXT NOT NULL
        )
    """))
    # error_families: SIN_CLASIFICAR seed (needed for item_errors FK chain)
    _conn.execute(text("""
        CREATE TABLE IF NOT EXISTS error_families (
            code TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            description TEXT,
            sort_order INTEGER NOT NULL DEFAULT 99
        )
    """))
    _conn.execute(text("""
        INSERT OR IGNORE INTO error_families (code, display_name, sort_order)
        VALUES ('SIN_CLASIFICAR', 'Sin clasificar', 99)
    """))
    # error_codes: auto-populated by processor (EB-10)
    _conn.execute(text("""
        CREATE TABLE IF NOT EXISTS error_codes (
            code TEXT PRIMARY KEY,
            family_code TEXT NOT NULL DEFAULT 'SIN_CLASIFICAR'
                REFERENCES error_families(code),
            default_category TEXT,
            canonical_message TEXT,
            first_seen_at DATETIME
        )
    """))
    # item_errors: 1:N error rows per run_item (RF-07)
    _conn.execute(text("""
        CREATE TABLE IF NOT EXISTS item_errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_item_id INTEGER NOT NULL REFERENCES run_items(id),
            error_code TEXT NOT NULL REFERENCES error_codes(code),
            error_category TEXT NOT NULL DEFAULT 'ERROR',
            error_message TEXT NOT NULL,
            affected_field TEXT
        )
    """))
    _conn.execute(
        text(
            "INSERT OR IGNORE INTO users (id, email, role, hashed_password) "
            "VALUES (:id, :email, :role, 'dummy')"
        ),
        {"id": DUMMY_USER.id, "email": DUMMY_USER.email, "role": DUMMY_USER.role},
    )

_SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def _get_test_db() -> Generator[Session, None, None]:
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Module-scoped test client ────────────────────────────────────────────────


class _SyncTaskRunner:
    """Executes work_fn synchronously — ensures BDD assertions see results immediately."""

    def submit(self, run_id: int, work_fn: Any) -> None:  # noqa: ANN401
        work_fn(run_id)

    def active_count(self) -> int:
        return 0

    def shutdown(self, *, wait: bool = True) -> None:  # noqa: ARG002
        pass


_sync_runner = _SyncTaskRunner()


@pytest.fixture(scope="module")
def bdd_client() -> TestClient:
    """Single TestClient reused across all BDD scenarios in this module.

    Uses _SyncTaskRunner so the pipeline completes before the 202 response
    is observed — BDD assertions can check results immediately (T-4.6).
    """
    app = create_app()
    app.dependency_overrides[get_db] = _get_test_db
    app.dependency_overrides[get_staging_dir] = lambda: _STAGING
    app.dependency_overrides[get_task_runner] = lambda: _sync_runner
    app.dependency_overrides[get_db_factory] = lambda: _SessionLocal
    return TestClient(app)


# ── Scenario-scoped context ───────────────────────────────────────────────────


@pytest.fixture
def ctx() -> dict[str, Any]:
    """Mutable dict shared among all steps within one scenario."""
    return {}


# ── Synthetic file factories ─────────────────────────────────────────────────


def _make_csv(rows: list[dict[str, str]], *, header: list[str] | None = None) -> bytes:
    """Build a CSV bytes payload from a list of row dicts."""
    cols = header or list(rows[0].keys())
    lines = [",".join(cols)]
    for row in rows:
        lines.append(",".join(str(row.get(c, "")) for c in cols))
    return "\n".join(lines).encode("utf-8")


def _make_occ_xlsx(
    rows: list[dict[str, str]],
) -> bytes:
    """Build a minimal OCC (Libro1) Excel file.

    Schema: Name | SKU | Supplier | (sin nombre) | stock occ
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Hoja1"
    ws.append(["Name", "SKU", "Supplier", None, "stock occ"])
    for row in rows:
        ws.append([
            row.get("Name", ""),
            row.get("SKU", ""),
            row.get("Supplier", ""),
            None,
            row.get("stock occ", ""),
        ])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _make_amazon_report_xlsx(
    error_rows: list[dict[str, str]],
) -> bytes:
    """Build a minimal Amazon processing-summary Excel file.

    Structure compatible with BlockLocator:
      Row 1: (empty — becomes DF column names)
      Row 2: title "Errores y advertencias por SKU" in col A
      Row 3: headers #, Código de error, Categoría de error,
                      Mensaje de error, Campo afectado, SKU
      Row 4+: data rows
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Resumen de procesamiento"
    ws.append([""])  # row 1 — empty (becomes DF column header)
    ws.append(["Errores y advertencias por SKU"])  # row 2 — block title
    ws.append([  # row 3 — column headers
        "#", "Código de error", "Categoría de error",
        "Mensaje de error", "Campo afectado", "SKU",
    ])
    for i, row in enumerate(error_rows, start=1):
        ws.append([
            str(i),
            row.get("Código de error", ""),
            row.get("Categoría de error", "ERROR"),
            row.get("Mensaje de error", ""),
            row.get("Campo afectado", ""),
            row.get("SKU", ""),
        ])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── Upload helpers ────────────────────────────────────────────────────────────


def _upload_file(
    client: TestClient,
    run_id: int,
    role: str,
    filename: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> int:
    """Upload bytes as a source file, return source_file.id."""
    resp = client.post(
        f"/api/v1/runs/{run_id}/files",
        data={"role": role},
        files={"file": (filename, io.BytesIO(data), content_type)},
    )
    assert resp.status_code == 201, f"Upload failed ({role}): {resp.text}"
    return int(resp.json()["id"])


def _confirm_mapping(
    client: TestClient,
    run_id: int,
    file_id: int,
    mappings: list[dict[str, Any]],
) -> None:
    """Confirm column mappings for a file via the PUT mapping endpoint."""
    resp = client.put(
        f"/api/v1/runs/{run_id}/files/{file_id}/mapping",
        json={"mappings": mappings},
    )
    assert resp.status_code == 200, f"Mapping confirmation failed: {resp.text}"


def _confirm_sku_by_preview(
    client: TestClient, run_id: int, file_id: int,
) -> None:
    """Confirm the heuristically suggested SKU mapping for *file_id*."""
    resp = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview")
    assert resp.status_code == 200, f"Preview failed: {resp.text}"
    suggestions = resp.json()["suggestions"]
    mappings = [
        {"logical_field": field, "column_index": info["column_index"], "was_suggested": True}
        for field, info in suggestions.items()
    ]
    if not mappings:
        mappings = [{"logical_field": "sku", "column_index": 0, "was_suggested": False}]
    _confirm_mapping(client, run_id, file_id, mappings)


def _find_col_index(client: TestClient, run_id: int, file_id: int, col_name: str) -> int:
    """Return the column index for *col_name* in the preview headers."""
    resp = client.get(f"/api/v1/runs/{run_id}/files/{file_id}/preview")
    assert resp.status_code == 200
    for h in resp.json()["headers"]:
        if h["name"] == col_name:
            return int(h["index"])
    msg = f"Column '{col_name}' not found in preview headers"
    raise ValueError(msg)


# ── Background (Antecedentes) — no shared background in CA-03 ─────────────────
# Each scenario creates its own run with tailored synthetic fixtures.


# =============================================================================
# Escenario 1: Filas idénticas en el feed se colapsan y se reportan
# =============================================================================


@given(
    parsers.parse(
        'que el feed contiene 3 filas idénticas para el SKU "{sku}" con stock {stock:d}'
    )
)
def step_s1_feed_identical_rows(
    bdd_client: TestClient, ctx: dict[str, Any], sku: str, stock: int,
) -> None:
    """Create a run and upload 3 identical feed rows + minimal OCC + minimal amazon_report."""
    # Create run
    resp = bdd_client.post("/api/v1/runs", json={})
    assert resp.status_code == 201
    run_id = int(resp.json()["id"])
    ctx["run_id"] = run_id
    ctx["sku"] = sku
    ctx["stock"] = stock

    # Feed: 3 identical rows for the same SKU
    feed_csv = _make_csv([
        {"sku": sku, "stock": str(stock), "site": "ES", "condition": "new"},
        {"sku": sku, "stock": str(stock), "site": "ES", "condition": "new"},
        {"sku": sku, "stock": str(stock), "site": "ES", "condition": "new"},
    ])
    feed_id = _upload_file(
        bdd_client, run_id, "wm_feed", "feed.csv", feed_csv, "text/csv"
    )
    ctx["feed_id"] = feed_id

    # OCC: single row (neutral)
    occ_xlsx = _make_occ_xlsx([{"Name": "Producto A", "SKU": "NEUTRAL1", "Supplier": "S1"}])
    occ_id = _upload_file(
        bdd_client, run_id, "occ_top", "occ.xlsx", occ_xlsx,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    ctx["occ_id"] = occ_id

    # Amazon report: single error row for neutral SKU
    amazon_xlsx = _make_amazon_report_xlsx([
        {
            "Código de error": "12345", "Categoría de error": "ERROR",
            "Mensaje de error": "Some error", "Campo afectado": "title",
            "SKU": "NEUTRAL1",
        },
    ])
    amazon_id = _upload_file(
        bdd_client, run_id, "amazon_report", "report.xlsx", amazon_xlsx,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    ctx["amazon_id"] = amazon_id

    # Confirm mappings
    # Feed: sku=col0, stock=col1
    _confirm_mapping(bdd_client, run_id, feed_id, [
        {"logical_field": "sku", "column_index": 0, "was_suggested": True},
        {"logical_field": "stock", "column_index": 1, "was_suggested": True},
    ])
    # OCC: sku=col1
    _confirm_mapping(bdd_client, run_id, occ_id, [
        {"logical_field": "sku", "column_index": 1, "was_suggested": True},
    ])
    # Amazon: confirm via preview suggestions
    _confirm_sku_by_preview(bdd_client, run_id, amazon_id)


@when("finaliza el procesamiento", target_fixture="process_resp")
def step_finaliza_procesamiento(bdd_client: TestClient, ctx: dict[str, Any]) -> dict[str, Any]:
    """POST /process and assert 202."""
    resp = bdd_client.post(f"/api/v1/runs/{ctx['run_id']}/process")
    assert resp.status_code == 202, (
        f"Expected 202, got {resp.status_code}: {resp.text}"
    )
    return resp.json()


@then(parsers.parse('"{sku}" aparece una sola vez en los resultados con stock {stock:d}'))
def step_s1_single_result_with_stock(ctx: dict[str, Any], sku: str, stock: int) -> None:
    """Assert exactly one run_items row for SKU with correct feed_stock."""
    db = _SessionLocal()
    try:
        rows = db.execute(
            text(
                "SELECT feed_stock FROM run_items "
                "WHERE run_id = :run_id AND sku_norm = :sku_norm"
            ),
            {"run_id": ctx["run_id"], "sku_norm": sku.upper()},
        ).fetchall()
        assert len(rows) == 1, (
            f"Expected exactly 1 run_items row for {sku}, found {len(rows)}"
        )
        assert rows[0][0] == stock, (
            f"Expected feed_stock={stock}, got {rows[0][0]}"
        )
    finally:
        db.close()


@then(
    parsers.parse(
        'la Vista 3 registra el hallazgo "{sku}: {count:d} ocurrencias, '
        'resolución {resolution}"'
    )
)
def step_s1_finding_registered(
    ctx: dict[str, Any], sku: str, count: int, resolution: str,
) -> None:
    """Assert a duplicate_findings row with the expected sku_norm, count and resolution."""
    db = _SessionLocal()
    try:
        row = db.execute(
            text(
                "SELECT occurrences, resolution FROM duplicate_findings "
                "WHERE sku_norm = :sku_norm"
            ),
            {"sku_norm": sku.upper()},
        ).fetchone()
        assert row is not None, (
            f"No duplicate_findings row for SKU '{sku}'"
        )
        assert row[0] == count, (
            f"Expected occurrences={count}, got {row[0]}"
        )
        assert row[1] == resolution, (
            f"Expected resolution='{resolution}', got '{row[1]}'"
        )
    finally:
        db.close()


# =============================================================================
# Escenario 2: Stock en conflicto en el feed — nunca se suma
# =============================================================================


@given(
    parsers.parse(
        'que el feed contiene el SKU "{sku}" con stock {stock_a:d} '
        'en una fila y stock {stock_b:d} en otra'
    )
)
def step_s2_feed_stock_conflict(
    bdd_client: TestClient, ctx: dict[str, Any], sku: str, stock_a: int, stock_b: int,
) -> None:
    """Create a run with a feed that has 2 rows for the same SKU with different stocks."""
    resp = bdd_client.post("/api/v1/runs", json={})
    assert resp.status_code == 201
    run_id = int(resp.json()["id"])
    ctx["run_id"] = run_id
    ctx["sku"] = sku
    ctx["stock_a"] = stock_a
    ctx["stock_b"] = stock_b

    # Feed: two rows for same SKU with different stocks
    feed_csv = _make_csv([
        {"sku": sku, "stock": str(stock_a), "site": "ES", "condition": "new"},
        {"sku": sku, "stock": str(stock_b), "site": "ES", "condition": "new"},
    ])
    feed_id = _upload_file(
        bdd_client, run_id, "wm_feed", "feed.csv", feed_csv, "text/csv"
    )
    ctx["feed_id"] = feed_id

    # OCC + Amazon: minimal neutral files
    occ_xlsx = _make_occ_xlsx([{"Name": "Prod", "SKU": "NEUTRAL2", "Supplier": "S1"}])
    occ_id = _upload_file(
        bdd_client, run_id, "occ_top", "occ.xlsx", occ_xlsx,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    amazon_xlsx = _make_amazon_report_xlsx([
        {
            "Código de error": "99001", "Categoría de error": "ERROR",
            "Mensaje de error": "err", "Campo afectado": "title", "SKU": "NEUTRAL2",
        },
    ])
    amazon_id = _upload_file(
        bdd_client, run_id, "amazon_report", "report.xlsx", amazon_xlsx,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    _confirm_mapping(bdd_client, run_id, feed_id, [
        {"logical_field": "sku", "column_index": 0, "was_suggested": True},
        {"logical_field": "stock", "column_index": 1, "was_suggested": True},
    ])
    _confirm_mapping(bdd_client, run_id, occ_id, [
        {"logical_field": "sku", "column_index": 1, "was_suggested": True},
    ])
    _confirm_sku_by_preview(bdd_client, run_id, amazon_id)


@then(
    parsers.parse(
        '"{sku}" queda con stock {stock:d} y stock_conflict verdadero'
    )
)
def step_s2_stock_conflict_true(ctx: dict[str, Any], sku: str, stock: int) -> None:
    """Assert run_items has MAX(stock) and stock_conflict=True for SKU."""
    db = _SessionLocal()
    try:
        row = db.execute(
            text(
                "SELECT feed_stock, stock_conflict FROM run_items "
                "WHERE run_id = :run_id AND sku_norm = :sku_norm"
            ),
            {"run_id": ctx["run_id"], "sku_norm": sku.upper()},
        ).fetchone()
        assert row is not None, f"No run_items row for SKU '{sku}'"
        assert row[0] == stock, (
            f"Expected feed_stock={stock} (MAX), got {row[0]} — stock was summed or wrong"
        )
        assert row[1] == 1, (
            f"Expected stock_conflict=1 (True), got {row[1]}"
        )
    finally:
        db.close()


@then(parsers.parse('la Vista 3 muestra los valores en conflicto "{val_a}" y "{val_b}"'))
def step_s2_conflict_values_recorded(
    ctx: dict[str, Any], val_a: str, val_b: str,
) -> None:
    """Assert duplicate_findings.discarded_values contains both conflicting stock values."""
    db = _SessionLocal()
    try:
        row = db.execute(
            text(
                "SELECT discarded_values FROM duplicate_findings "
                "WHERE sku_norm = :sku_norm AND resolution = 'kept_max_stock'"
            ),
            {"sku_norm": ctx["sku"].upper()},
        ).fetchone()
        assert row is not None, (
            f"No kept_max_stock finding for SKU '{ctx['sku']}'"
        )
        data = json.loads(row[0])
        # Normalise to float for comparison (stored as float internally)
        raw_stocks = data.get("stock_values", [])
        stock_values_f = {float(v) for v in raw_stocks}
        assert float(val_a) in stock_values_f, (
            f"Expected stock value '{val_a}' in {raw_stocks}"
        )
        assert float(val_b) in stock_values_f, (
            f"Expected stock value '{val_b}' in {raw_stocks}"
        )
    finally:
        db.close()


@then(
    parsers.parse(
        "en ningún caso el stock resultante es {bad_stock:d}"
    )
)
def step_s2_stock_not_summed(ctx: dict[str, Any], bad_stock: int) -> None:
    """Assert run_items.feed_stock is NOT the sum of the two conflicting stocks."""
    db = _SessionLocal()
    try:
        actual = db.execute(
            text(
                "SELECT feed_stock FROM run_items "
                "WHERE run_id = :run_id AND sku_norm = :sku_norm"
            ),
            {"run_id": ctx["run_id"], "sku_norm": ctx["sku"].upper()},
        ).scalar()
        assert actual != bad_stock, (
            f"Stock was summed! Expected != {bad_stock}, got {actual}"
        )
    finally:
        db.close()


# =============================================================================
# Escenario 3: Duplicado en Libro1 conserva la primera ocurrencia
# =============================================================================


@given(
    parsers.parse(
        'que "Libro1" contiene el SKU "{sku}" en la fila 3 con proveedor "{supplier_a}"'
    )
)
def step_s3_occ_first_occurrence(
    bdd_client: TestClient, ctx: dict[str, Any], sku: str, supplier_a: str,
) -> None:
    """Create a run and OCC file with first occurrence of the duplicated SKU."""
    resp = bdd_client.post("/api/v1/runs", json={})
    assert resp.status_code == 201
    run_id = int(resp.json()["id"])
    ctx["run_id"] = run_id
    ctx["sku"] = sku
    ctx["supplier_a"] = supplier_a
    # Store partial OCC rows; second row added in the next step
    ctx["occ_rows"] = [
        {"Name": f"Producto {sku}", "SKU": sku, "Supplier": supplier_a, "stock occ": "10"},
    ]


@given(
    parsers.parse(
        'el mismo SKU en la fila 900 con proveedor "{supplier_b}"'
    )
)
def step_s3_occ_second_occurrence(
    bdd_client: TestClient, ctx: dict[str, Any], supplier_b: str,
) -> None:
    """Append the second (duplicate) OCC row then upload all files + confirm mappings."""
    run_id = ctx["run_id"]
    ctx["supplier_b"] = supplier_b
    sku = ctx["sku"]

    # Second row — same SKU, different supplier
    ctx["occ_rows"].append(
        {"Name": f"Producto {sku} 2", "SKU": sku, "Supplier": supplier_b, "stock occ": "5"},
    )

    occ_xlsx = _make_occ_xlsx(ctx["occ_rows"])
    occ_id = _upload_file(
        bdd_client, run_id, "occ_top", "occ.xlsx", occ_xlsx,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    ctx["occ_id"] = occ_id

    # Minimal feed and amazon_report
    feed_csv = _make_csv([{"sku": "NEUTRAL3", "stock": "1", "site": "ES", "condition": "new"}])
    feed_id = _upload_file(
        bdd_client, run_id, "wm_feed", "feed.csv", feed_csv, "text/csv"
    )
    amazon_xlsx = _make_amazon_report_xlsx([
        {
            "Código de error": "11111", "Categoría de error": "ERROR",
            "Mensaje de error": "err", "Campo afectado": "x", "SKU": "NEUTRAL3",
        },
    ])
    amazon_id = _upload_file(
        bdd_client, run_id, "amazon_report", "report.xlsx", amazon_xlsx,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    # Confirm mappings: OCC sku=col1
    _confirm_mapping(bdd_client, run_id, occ_id, [
        {"logical_field": "sku", "column_index": 1, "was_suggested": True},
    ])
    _confirm_mapping(bdd_client, run_id, feed_id, [
        {"logical_field": "sku", "column_index": 0, "was_suggested": True},
        {"logical_field": "stock", "column_index": 1, "was_suggested": True},
    ])
    _confirm_sku_by_preview(bdd_client, run_id, amazon_id)


@then(parsers.parse('los datos asociados a "{sku}" son los de la fila 3'))
def step_s3_first_row_kept(ctx: dict[str, Any], sku: str) -> None:
    """Assert run_items has exactly 1 row for SKU with in_occ=True."""
    db = _SessionLocal()
    try:
        rows = db.execute(
            text(
                "SELECT id, in_occ FROM run_items "
                "WHERE run_id = :run_id AND sku_norm = :sku_norm"
            ),
            {"run_id": ctx["run_id"], "sku_norm": sku.upper()},
        ).fetchall()
        assert len(rows) == 1, (
            f"Expected 1 run_items row for '{sku}' after dedup, found {len(rows)}"
        )
        assert rows[0][1] == 1, "in_occ should be True"
    finally:
        db.close()


@then(
    parsers.parse(
        'la Vista 3 registra "{sku}: {count:d} ocurrencias, resolución {resolution}" '
        "con la fila descartada"
    )
)
def step_s3_finding_with_discarded(
    ctx: dict[str, Any], sku: str, count: int, resolution: str,
) -> None:
    """Assert a duplicate_findings row and that discarded_rows is non-empty."""
    db = _SessionLocal()
    try:
        row = db.execute(
            text(
                "SELECT occurrences, resolution, discarded_values "
                "FROM duplicate_findings WHERE sku_norm = :sku_norm"
            ),
            {"sku_norm": sku.upper()},
        ).fetchone()
        assert row is not None, f"No duplicate_findings row for SKU '{sku}'"
        assert row[0] == count, (
            f"Expected occurrences={count}, got {row[0]}"
        )
        assert row[1] == resolution, (
            f"Expected resolution='{resolution}', got '{row[1]}'"
        )
        data = json.loads(row[2])
        assert "discarded_rows" in data, (
            f"discarded_values should contain 'discarded_rows', got keys: {list(data.keys())}"
        )
        assert len(data["discarded_rows"]) >= 1, (
            "discarded_rows should contain at least 1 entry"
        )
    finally:
        db.close()


# =============================================================================
# Escenario 4: Múltiples errores por SKU no se tratan como duplicados
# =============================================================================


@given(
    parsers.parse(
        'que el reporte de Amazon contiene {count:d} filas de error distintas '
        'para "{sku}"'
    )
)
def step_s4_amazon_multiple_errors(
    bdd_client: TestClient, ctx: dict[str, Any], count: int, sku: str,
) -> None:
    """Create a run with 8 DIFFERENT error rows for the same SKU in amazon_report."""
    resp = bdd_client.post("/api/v1/runs", json={})
    assert resp.status_code == 201
    run_id = int(resp.json()["id"])
    ctx["run_id"] = run_id
    ctx["sku"] = sku
    ctx["error_count"] = count

    # Amazon report: 8 DISTINCT error rows (different codes and messages)
    error_rows = [
        {
            "Código de error": f"ERR{i:03d}",
            "Categoría de error": "ERROR",
            "Mensaje de error": f"Error description number {i} for SKU {sku}",
            "Campo afectado": f"field_{i}",
            "SKU": sku,
        }
        for i in range(1, count + 1)
    ]
    amazon_xlsx = _make_amazon_report_xlsx(error_rows)
    amazon_id = _upload_file(
        bdd_client, run_id, "amazon_report", "report.xlsx", amazon_xlsx,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    ctx["amazon_id"] = amazon_id

    # Minimal OCC and feed
    occ_xlsx = _make_occ_xlsx([{"Name": "Prod", "SKU": "NEUTRAL4", "Supplier": "S1"}])
    occ_id = _upload_file(
        bdd_client, run_id, "occ_top", "occ.xlsx", occ_xlsx,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    feed_csv = _make_csv([{"sku": "NEUTRAL4", "stock": "3", "site": "ES", "condition": "new"}])
    feed_id = _upload_file(
        bdd_client, run_id, "wm_feed", "feed.csv", feed_csv, "text/csv"
    )

    # Confirm mappings — amazon: confirm all error fields + SKU
    _confirm_sku_by_preview(bdd_client, run_id, amazon_id)
    _confirm_mapping(bdd_client, run_id, occ_id, [
        {"logical_field": "sku", "column_index": 1, "was_suggested": True},
    ])
    _confirm_mapping(bdd_client, run_id, feed_id, [
        {"logical_field": "sku", "column_index": 0, "was_suggested": True},
        {"logical_field": "stock", "column_index": 1, "was_suggested": True},
    ])


@then(parsers.parse('"{sku}" conserva sus {count:d} errores asociados'))
def step_s4_errors_preserved(ctx: dict[str, Any], sku: str, count: int) -> None:
    """Assert item_errors has exactly *count* rows for the SKU's run_item."""
    db = _SessionLocal()
    try:
        run_item = db.execute(
            text(
                "SELECT id FROM run_items "
                "WHERE run_id = :run_id AND sku_norm = :sku_norm"
            ),
            {"run_id": ctx["run_id"], "sku_norm": sku.upper()},
        ).fetchone()
        assert run_item is not None, (
            f"No run_items row found for SKU '{sku}'"
        )
        error_count = db.execute(
            text("SELECT COUNT(*) FROM item_errors WHERE run_item_id = :rid"),
            {"rid": run_item[0]},
        ).scalar()
        assert error_count == count, (
            f"Expected {count} item_errors for '{sku}', found {error_count}"
        )
    finally:
        db.close()


@then(parsers.parse('no figura en el reporte de duplicados'))
def step_s4_not_in_duplicates(ctx: dict[str, Any]) -> None:
    """Assert there is no duplicate_findings row for the SKU (1:N is not a duplicate)."""
    db = _SessionLocal()
    try:
        sku_norm = ctx["sku"].upper()
        row = db.execute(
            text(
                "SELECT id FROM duplicate_findings WHERE sku_norm = :sku_norm"
            ),
            {"sku_norm": sku_norm},
        ).fetchone()
        assert row is None, (
            f"SKU '{ctx['sku']}' should NOT appear in duplicate_findings "
            f"(1:N cardinality is legitimate, not a duplicate)"
        )
    finally:
        db.close()


# ── Module teardown ───────────────────────────────────────────────────────────


def teardown_module(module: object) -> None:  # noqa: ARG001
    shutil.rmtree(_STAGING, ignore_errors=True)
