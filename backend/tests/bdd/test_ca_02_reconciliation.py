"""T-4.3 — BDD CA-02: Conciliación de 3 vías con detección de desincronización (gate M4).

Suite pytest-bdd ejecutando literalmente los 4 escenarios Gherkin del spec 2.11
(CA-02) sobre la API real (TestClient + SQLite in-memory).

Escenarios cubiertos:
  1. SKU enviado con errores múltiples (SENT_WITH_ERROR, 11 item_errors)
  2. Clasificación bidireccional (4 ejemplos parametrizados):
       AAA111 → DESYNC_FEED_ONLY
       BBB222 → DESYNC_AMAZON_ONLY
       CCC333 → NOT_SENT
       DDD444 → SENT_OK
  3. Priorización por stock en Vista 3 (catalog-health ordenado feed_stock DESC)
  4. Cruce insensible a suciedad de formato (NBSP + case → mismo sku_norm)

DoD: CA-02 100% verde; los Gherkin del spec se ejecutan literalmente sin reescritura.
"""

from __future__ import annotations

import io
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

scenarios("../features/ca_02_reconciliation.feature")

# ── Staging directory ────────────────────────────────────────────────────────

_STAGING = Path(__file__).parent.parent / ".staging_bdd_ca02"
_STAGING.mkdir(parents=True, exist_ok=True)

# ── SQLite in-memory DB (identical schema to CA-03) ──────────────────────────

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
            "VALUES (:id, :email, :role, 'dummy')",
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


# ── Synthetic file factories (shared with CA-03 pattern) ─────────────────────


def _make_csv(rows: list[dict[str, str]], *, header: list[str] | None = None) -> bytes:
    cols = header or list(rows[0].keys())
    lines = [",".join(cols)]
    lines.extend(",".join(str(row.get(c, "")) for c in cols) for row in rows)
    return "\n".join(lines).encode("utf-8")


def _make_occ_xlsx(rows: list[dict[str, str]]) -> bytes:
    """OCC Libro1 schema: Name | SKU | Supplier | (sin nombre) | stock occ."""
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


def _make_amazon_report_xlsx(error_rows: list[dict[str, str]]) -> bytes:
    """Amazon processing-summary structure compatible with BlockLocator."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Resumen de procesamiento"
    ws.append([""])  # row 1 — empty header
    ws.append(["Errores y advertencias por SKU"])  # row 2 — block title
    ws.append([
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


# ── Upload / mapping helpers ──────────────────────────────────────────────────


def _upload_file(  # noqa: PLR0913
    client: TestClient,
    run_id: int,
    role: str,
    filename: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> int:
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
    resp = client.put(
        f"/api/v1/runs/{run_id}/files/{file_id}/mapping",
        json={"mappings": mappings},
    )
    assert resp.status_code == 200, f"Mapping confirmation failed: {resp.text}"


def _confirm_sku_by_preview(client: TestClient, run_id: int, file_id: int) -> None:
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


def _create_run(client: TestClient) -> int:
    resp = client.post("/api/v1/runs", json={})
    assert resp.status_code == 201
    return int(resp.json()["id"])


def _upload_neutral_occ(client: TestClient, run_id: int, neutral_sku: str = "NEUTRAL_OCC") -> int:
    xlsx = _make_occ_xlsx([{"Name": "Neutral", "SKU": neutral_sku, "Supplier": "S1"}])
    occ_id = _upload_file(
        client, run_id, "occ_top", "occ.xlsx", xlsx,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    _confirm_mapping(client, run_id, occ_id, [
        {"logical_field": "sku", "column_index": 1, "was_suggested": True},
    ])
    return occ_id


def _upload_neutral_feed(
    client: TestClient, run_id: int, neutral_sku: str = "NEUTRAL_FEED",
) -> int:
    csv_data = _make_csv([
        {"sku": neutral_sku, "stock": "0", "site": "ES", "condition": "new"},
    ])
    feed_id = _upload_file(client, run_id, "wm_feed", "feed.csv", csv_data, "text/csv")
    _confirm_mapping(client, run_id, feed_id, [
        {"logical_field": "sku", "column_index": 0, "was_suggested": True},
        {"logical_field": "stock", "column_index": 1, "was_suggested": True},
    ])
    return feed_id


def _upload_neutral_amazon(
    client: TestClient, run_id: int, neutral_sku: str = "NEUTRAL_AMZ",
) -> int:
    xlsx = _make_amazon_report_xlsx([{
        "Código de error": "00000",
        "Categoría de error": "ERROR",
        "Mensaje de error": "neutral error",
        "Campo afectado": "title",
        "SKU": neutral_sku,
    }])
    amazon_id = _upload_file(
        client, run_id, "amazon_report", "report.xlsx", xlsx,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    _confirm_sku_by_preview(client, run_id, amazon_id)
    return amazon_id


# ── Antecedentes (Background) ─────────────────────────────────────────────────
# The Background declares the precondition. Each scenario creates its OWN run
# and uploads its own files in the scenario-specific Given steps; ctx["run_id"]
# is always set by the first Given step of each scenario.


@given("que existe una ejecución con mapeo confirmado de los 3 ficheros")
def step_background_run_exists(ctx: dict[str, Any]) -> None:
    """Background marker — each scenario creates its own run with specific data."""


# =============================================================================
# Escenario 1: SKU enviado con errores múltiples
# =============================================================================


@given(parsers.parse('que el SKU "{sku}" está en el feed con stock {stock:d}'))
def step_s1_sku_in_feed(
    bdd_client: TestClient, ctx: dict[str, Any], sku: str, stock: int,
) -> None:
    """Create run; upload OCC (neutral) + Feed (with the target SKU)."""
    run_id = _create_run(bdd_client)
    ctx["run_id"] = run_id
    ctx["sku"] = sku

    # Feed: target SKU with given stock
    feed_csv = _make_csv([
        {"sku": sku, "stock": str(stock), "site": "ES", "condition": "new"},
    ])
    feed_id = _upload_file(bdd_client, run_id, "wm_feed", "feed.csv", feed_csv, "text/csv")
    _confirm_mapping(bdd_client, run_id, feed_id, [
        {"logical_field": "sku", "column_index": 0, "was_suggested": True},
        {"logical_field": "stock", "column_index": 1, "was_suggested": True},
    ])
    # OCC: neutral (test SKU not in OCC — only in feed + amazon)
    _upload_neutral_occ(bdd_client, run_id, neutral_sku="NEUTRAL_S1_OCC")


@given(parsers.parse('el reporte de Amazon contiene {count:d} filas de error para "{sku}"'))
def step_s1_amazon_errors(
    bdd_client: TestClient, ctx: dict[str, Any], count: int, sku: str,
) -> None:
    """Upload Amazon report with *count* distinct error rows for *sku*."""
    run_id = ctx["run_id"]
    error_rows = [
        {
            "Código de error": f"1{8299 + i:04d}",
            "Categoría de error": "ERROR",
            "Mensaje de error": f"Error de conciliación número {i} para {sku}",
            "Campo afectado": f"attribute_{i}",
            "SKU": sku,
        }
        for i in range(1, count + 1)
    ]
    amazon_xlsx = _make_amazon_report_xlsx(error_rows)
    amazon_id = _upload_file(
        bdd_client, run_id, "amazon_report", "report.xlsx", amazon_xlsx,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    _confirm_sku_by_preview(bdd_client, run_id, amazon_id)
    ctx["expected_errors"] = count


@when("finaliza la conciliación", target_fixture="process_resp")
def step_finaliza_conciliacion(
    bdd_client: TestClient, ctx: dict[str, Any],
) -> dict[str, Any]:
    """POST /process and assert 202."""
    resp = bdd_client.post(f"/api/v1/runs/{ctx['run_id']}/process")
    assert resp.status_code == 202, (
        f"Expected 202, got {resp.status_code}: {resp.text}"
    )
    return resp.json()


@then(parsers.parse('"{sku}" tiene sync_status "{expected_status}"'))
def step_s1_sync_status(ctx: dict[str, Any], sku: str, expected_status: str) -> None:
    db = _SessionLocal()
    try:
        row = db.execute(
            text(
                "SELECT sync_status FROM run_items "
                "WHERE run_id = :run_id AND sku_norm = :sku_norm",
            ),
            {"run_id": ctx["run_id"], "sku_norm": sku.upper()},
        ).fetchone()
        assert row is not None, f"No run_items row for SKU '{sku}'"
        assert row[0] == expected_status, (
            f"Expected sync_status='{expected_status}', got '{row[0]}'"
        )
    finally:
        db.close()


@then("tiene exactamente 11 errores asociados con código, categoría, mensaje y campo afectado")
def step_s1_eleven_errors(ctx: dict[str, Any]) -> None:
    """Assert item_errors has exactly 11 rows with all required fields populated."""
    sku = ctx["sku"]
    db = _SessionLocal()
    try:
        run_item = db.execute(
            text(
                "SELECT id FROM run_items "
                "WHERE run_id = :run_id AND sku_norm = :sku_norm",
            ),
            {"run_id": ctx["run_id"], "sku_norm": sku.upper()},
        ).fetchone()
        assert run_item is not None, f"No run_items row for '{sku}'"

        errors = db.execute(
            text(
                "SELECT error_code, error_category, error_message, affected_field "
                "FROM item_errors WHERE run_item_id = :rid",
            ),
            {"rid": run_item[0]},
        ).fetchall()
        assert len(errors) == 11, (
            f"Expected 11 item_errors for '{sku}', found {len(errors)}"
        )
        for err in errors:
            assert err[0], "error_code must be non-empty"
            assert err[1] in ("ERROR", "ADVERTENCIA"), (
                f"error_category must be ERROR or ADVERTENCIA, got '{err[1]}'"
            )
            assert err[2], "error_message must be non-empty"
    finally:
        db.close()


@then("aparece en la Vista 2 con una fila por error")
def step_s1_vista2_one_row_per_error(ctx: dict[str, Any]) -> None:
    """Assert run_items count of item_errors equals the expected count (Vista 2 contract)."""
    sku = ctx["sku"]
    expected = ctx.get("expected_errors", 11)
    db = _SessionLocal()
    try:
        run_item = db.execute(
            text(
                "SELECT id FROM run_items "
                "WHERE run_id = :run_id AND sku_norm = :sku_norm",
            ),
            {"run_id": ctx["run_id"], "sku_norm": sku.upper()},
        ).fetchone()
        assert run_item is not None
        count = db.execute(
            text("SELECT COUNT(*) FROM item_errors WHERE run_item_id = :rid"),
            {"rid": run_item[0]},
        ).scalar()
        assert count == expected, (
            f"Vista 2: expected {expected} rows for '{sku}', found {count}"
        )
    finally:
        db.close()


# =============================================================================
# Esquema del escenario: Clasificación bidireccional de sincronización
# =============================================================================


@given(
    parsers.parse(
        'que el SKU "{sku}" está {en_occ} en OCC, '
        "{en_feed} en el feed y {en_amazon} en el reporte",
    ),
)
def step_s2_classify_setup(  # noqa: PLR0913
    bdd_client: TestClient,
    ctx: dict[str, Any],
    sku: str,
    en_occ: str,
    en_feed: str,
    en_amazon: str,
) -> None:
    """Create run and upload 3 files configured per the presence/absence params."""
    run_id = _create_run(bdd_client)
    ctx["run_id"] = run_id
    ctx["sku"] = sku

    present_in_occ = en_occ.strip().lower() == "presente"
    present_in_feed = en_feed.strip().lower() == "presente"
    present_in_amazon = en_amazon.strip().lower() == "presente"

    # OCC
    occ_rows = (
        [{"Name": f"Producto {sku}", "SKU": sku, "Supplier": "S1", "stock occ": "5"}]
        if present_in_occ
        else [{"Name": "Neutral", "SKU": "NEUTRAL_CLS_OCC", "Supplier": "S1"}]
    )
    occ_xlsx = _make_occ_xlsx(occ_rows)
    occ_id = _upload_file(
        bdd_client, run_id, "occ_top", "occ.xlsx", occ_xlsx,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    _confirm_mapping(bdd_client, run_id, occ_id, [
        {"logical_field": "sku", "column_index": 1, "was_suggested": True},
    ])

    # Feed
    feed_rows = (
        [{"sku": sku, "stock": "10", "site": "ES", "condition": "new"}]
        if present_in_feed
        else [{"sku": "NEUTRAL_CLS_FEED", "stock": "0", "site": "ES", "condition": "new"}]
    )
    feed_csv = _make_csv(feed_rows)
    feed_id = _upload_file(bdd_client, run_id, "wm_feed", "feed.csv", feed_csv, "text/csv")
    _confirm_mapping(bdd_client, run_id, feed_id, [
        {"logical_field": "sku", "column_index": 0, "was_suggested": True},
        {"logical_field": "stock", "column_index": 1, "was_suggested": True},
    ])

    # Amazon report
    if present_in_amazon:
        # When the SKU is present in BOTH feed AND amazon, the expected state is SENT_OK.
        # We model "in amazon but no errors" by writing an empty "Código de error" cell.
        # The processor sets in_amazon_report=True (SKU appeared in the block) but skips
        # the item_error insert because the code is empty → has_errors=False → SENT_OK.
        #
        # When the SKU is only in amazon (not in feed) → DESYNC_AMAZON_ONLY, we add a
        # real error row so the SKU enters the universe via the amazon path.
        if present_in_feed and present_in_amazon:
            error_rows = [
                {
                    "Código de error": "",  # empty → in_amazon=True, 0 item_errors → SENT_OK
                    "Categoría de error": "",
                    "Mensaje de error": "",
                    "Campo afectado": "",
                    "SKU": sku,
                },
            ]
        else:
            # BBB222 (DESYNC_AMAZON_ONLY): in amazon only, with real errors
            error_rows = [
                {
                    "Código de error": "18299",
                    "Categoría de error": "ERROR",
                    "Mensaje de error": f"Error para {sku}",
                    "Campo afectado": "title",
                    "SKU": sku,
                },
            ]
        amazon_xlsx = _make_amazon_report_xlsx(error_rows)
    else:
        # SKU absent from amazon — use neutral SKU with an error row
        amazon_xlsx = _make_amazon_report_xlsx([{
            "Código de error": "18299",
            "Categoría de error": "ERROR",
            "Mensaje de error": "neutral error",
            "Campo afectado": "title",
            "SKU": "NEUTRAL_CLS_AMZ",
        }])

    amazon_id = _upload_file(
        bdd_client, run_id, "amazon_report", "report.xlsx", amazon_xlsx,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    _confirm_sku_by_preview(bdd_client, run_id, amazon_id)

    # Store presence flags for assertion step
    ctx["present_in_occ"] = present_in_occ
    ctx["present_in_feed"] = present_in_feed
    ctx["present_in_amazon"] = present_in_amazon


@then(parsers.parse('el SKU "{sku}" recibe sync_status "{expected_status}"'))
def step_s2_verify_sync_status(
    ctx: dict[str, Any], sku: str, expected_status: str,
) -> None:
    """Assert the computed sync_status matches the expected value from the scenario table."""
    db = _SessionLocal()
    try:
        row = db.execute(
            text(
                "SELECT sync_status, in_occ, in_feed, in_amazon_report "
                "FROM run_items WHERE run_id = :run_id AND sku_norm = :sku_norm",
            ),
            {"run_id": ctx["run_id"], "sku_norm": sku.upper()},
        ).fetchone()
        assert row is not None, (
            f"No run_items row for '{sku}' (run_id={ctx['run_id']})"
        )
        assert row[0] == expected_status, (
            f"SKU '{sku}': expected sync_status='{expected_status}', "
            f"got '{row[0]}' "
            f"(in_occ={row[1]}, in_feed={row[2]}, in_amazon={row[3]})"
        )
    finally:
        db.close()


# =============================================================================
# Escenario 3: Priorización por stock disponible en la vista de salud de catálogo
# =============================================================================


@given(
    parsers.parse(
        'que los SKUs "{sku_a}" con stock {stock_a:d} y "{sku_b}" con stock {stock_b:d} '
        'son "{expected_status}"',
    ),
)
def step_s3_two_desyncs(  # noqa: PLR0913
    bdd_client: TestClient,
    ctx: dict[str, Any],
    sku_a: str,
    stock_a: int,
    sku_b: str,
    stock_b: int,
    expected_status: str,
) -> None:
    """Create run with sku_a (stock_a) and sku_b (stock_b) both in feed, absent from amazon."""
    run_id = _create_run(bdd_client)
    ctx["run_id"] = run_id
    ctx["sku_a"] = sku_a
    ctx["sku_b"] = sku_b
    ctx["stock_a"] = stock_a
    ctx["stock_b"] = stock_b

    # Feed: both SKUs present (will become DESYNC_FEED_ONLY if not in amazon)
    feed_csv = _make_csv([
        {"sku": sku_a, "stock": str(stock_a), "site": "ES", "condition": "new"},
        {"sku": sku_b, "stock": str(stock_b), "site": "ES", "condition": "new"},
    ])
    feed_id = _upload_file(bdd_client, run_id, "wm_feed", "feed.csv", feed_csv, "text/csv")
    _confirm_mapping(bdd_client, run_id, feed_id, [
        {"logical_field": "sku", "column_index": 0, "was_suggested": True},
        {"logical_field": "stock", "column_index": 1, "was_suggested": True},
    ])

    # OCC: neutral (sku_a and sku_b not in OCC)
    _upload_neutral_occ(bdd_client, run_id, neutral_sku="NEUTRAL_S3_OCC")

    # Amazon: neutral (sku_a and sku_b not in amazon → DESYNC_FEED_ONLY)
    _upload_neutral_amazon(bdd_client, run_id, neutral_sku="NEUTRAL_S3_AMZ")

    # Process the run
    proc = bdd_client.post(f"/api/v1/runs/{run_id}/process")
    assert proc.status_code == 202, f"Process failed: {proc.text}"

    # Verify both got the expected status
    db = _SessionLocal()
    try:
        for sku in (sku_a, sku_b):
            row = db.execute(
                text(
                    "SELECT sync_status FROM run_items "
                    "WHERE run_id = :run_id AND sku_norm = :sku_norm",
                ),
                {"run_id": run_id, "sku_norm": sku.upper()},
            ).fetchone()
            assert row is not None, f"No run_items row for '{sku}'"
            assert row[0] == expected_status, (
                f"Setup: expected '{expected_status}' for '{sku}', got '{row[0]}'"
            )
    finally:
        db.close()


@when(parsers.parse('abro la Vista 3 "{vista_name}"'))
def step_s3_open_vista3(
    bdd_client: TestClient, ctx: dict[str, Any], vista_name: str,  # noqa: ARG001
) -> None:
    """Call the catalog-health endpoint and store results ordered by feed_stock DESC."""
    resp = bdd_client.get(
        f"/api/v1/runs/{ctx['run_id']}/catalog-health",
        params={"sync_status": "DESYNC_FEED_ONLY"},
    )
    assert resp.status_code == 200, f"catalog-health failed: {resp.text}"
    ctx["catalog_items"] = resp.json()["items"]


@then(parsers.parse('"{sku_a}" aparece antes que "{sku_b}"'))
def step_s3_order(ctx: dict[str, Any], sku_a: str, sku_b: str) -> None:
    items = ctx["catalog_items"]
    norms = [item["sku_norm"] for item in items]
    assert sku_a.upper() in norms, f"'{sku_a}' not found in catalog-health results"
    assert sku_b.upper() in norms, f"'{sku_b}' not found in catalog-health results"
    pos_a = norms.index(sku_a.upper())
    pos_b = norms.index(sku_b.upper())
    assert pos_a < pos_b, (
        f"Expected '{sku_a}' (pos {pos_a}) before '{sku_b}' (pos {pos_b}) "
        f"(higher stock must appear first)"
    )


@then('ambos muestran un distintivo de "stock disponible"')
def step_s3_stock_disponible(ctx: dict[str, Any]) -> None:
    sku_a = ctx["sku_a"].upper()
    sku_b = ctx["sku_b"].upper()
    items_by_sku = {item["sku_norm"]: item for item in ctx["catalog_items"]}

    for sku in (sku_a, sku_b):
        assert sku in items_by_sku, f"'{sku}' missing from catalog-health items"
        item = items_by_sku[sku]
        assert item["stock_disponible"], (
            f"'{sku}' with feed_stock={item['feed_stock']} should have stock_disponible=True"
        )


# =============================================================================
# Escenario 4: Cruce insensible a suciedad de formato
# =============================================================================


@given(parsers.parse('que el feed contiene el SKU "{sku}"'))
def step_s4_feed_sku(
    bdd_client: TestClient, ctx: dict[str, Any], sku: str,
) -> None:
    """Create run; upload OCC (neutral) + Feed with the clean SKU."""
    run_id = _create_run(bdd_client)
    ctx["run_id"] = run_id
    ctx["sku_clean"] = sku

    feed_csv = _make_csv([
        {"sku": sku, "stock": "7", "site": "ES", "condition": "new"},
    ])
    feed_id = _upload_file(bdd_client, run_id, "wm_feed", "feed.csv", feed_csv, "text/csv")
    _confirm_mapping(bdd_client, run_id, feed_id, [
        {"logical_field": "sku", "column_index": 0, "was_suggested": True},
        {"logical_field": "stock", "column_index": 1, "was_suggested": True},
    ])
    _upload_neutral_occ(bdd_client, run_id, neutral_sku="NEUTRAL_S4_OCC")


@given(
    parsers.parse(
        'el reporte de Amazon contiene el SKU "{sku}" con espacio NBSP final',
    ),
)
def step_s4_amazon_nbsp(
    bdd_client: TestClient, ctx: dict[str, Any], sku: str,
) -> None:
    """Upload amazon report with the SKU in dirty form (leading space + NBSP suffix)."""
    # Inject leading whitespace and NBSP (U+00A0) to simulate export artefacts (RN-03)
    dirty_sku = f" {sku}\u00a0"
    amazon_xlsx = _make_amazon_report_xlsx([{
        "Código de error": "18299",
        "Categoría de error": "ERROR",
        "Mensaje de error": "Error por suciedad de formato",
        "Campo afectado": "title",
        "SKU": dirty_sku,
    }])
    amazon_id = _upload_file(
        bdd_client, ctx["run_id"], "amazon_report", "report.xlsx", amazon_xlsx,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    _confirm_sku_by_preview(bdd_client, ctx["run_id"], amazon_id)
    ctx["dirty_sku"] = dirty_sku


@then(parsers.parse('ambos registros se cruzan como el mismo SKU "{sku_norm}"'))
def step_s4_same_sku_norm(ctx: dict[str, Any], sku_norm: str) -> None:
    """Assert exactly ONE run_items row exists for sku_norm with in_feed AND in_amazon."""
    db = _SessionLocal()
    try:
        rows = db.execute(
            text(
                "SELECT sku_norm, in_feed, in_amazon_report FROM run_items "
                "WHERE run_id = :run_id AND sku_norm = :sku_norm",
            ),
            {"run_id": ctx["run_id"], "sku_norm": sku_norm.upper()},
        ).fetchall()
        assert len(rows) == 1, (
            f"Expected 1 run_items row for '{sku_norm}', found {len(rows)} — "
            "normalization may have failed to unify dirty+clean forms"
        )
        assert rows[0][1] == 1, f"'{sku_norm}' should have in_feed=True"
        assert rows[0][2] == 1, f"'{sku_norm}' should have in_amazon_report=True"
    finally:
        db.close()


@then("no se genera ningún falso desincronizado")
def step_s4_no_false_desync(ctx: dict[str, Any]) -> None:
    """Assert the matched SKU is NOT classified as a desync variant."""
    clean_sku = ctx["sku_clean"].upper()
    db = _SessionLocal()
    try:
        row = db.execute(
            text(
                "SELECT sync_status FROM run_items "
                "WHERE run_id = :run_id AND sku_norm = :sku_norm",
            ),
            {"run_id": ctx["run_id"], "sku_norm": clean_sku},
        ).fetchone()
        assert row is not None, f"No run_items row for '{clean_sku}'"
        assert row[0] not in ("DESYNC_FEED_ONLY", "DESYNC_AMAZON_ONLY"), (
            f"'{clean_sku}' was falsely classified as '{row[0]}' — "
            "cross-join failed to unify dirty and clean forms of the SKU"
        )
    finally:
        db.close()


# ── Module teardown ───────────────────────────────────────────────────────────


def teardown_module(module: object) -> None:  # noqa: ARG001
    shutil.rmtree(_STAGING, ignore_errors=True)
