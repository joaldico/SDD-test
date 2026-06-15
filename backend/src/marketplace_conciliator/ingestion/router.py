"""Ingestion API router — T-3.6, T-3.7, T-3.8, T-3.10 (gate BDD CA-01).

Endpoints:
  POST /api/v1/runs                              Create a new reconciliation run.
  POST /api/v1/runs/{run_id}/files               Upload a source file (+ save to staging).
  GET  /api/v1/runs/{run_id}/files/{file_id}/preview   Parse & preview a staged file.
  PUT  /api/v1/runs/{run_id}/files/{file_id}/mapping   Confirm column mapping.
  POST /api/v1/runs/{run_id}/process             Trigger reconciliation (gate RNF-08).

Auth: uses the dummy ``get_current_user`` dependency (M2 bypass — see platform/deps.py).
DB:   uses the synchronous ``get_db`` session dependency (overridable in tests).

Staging: uploaded bytes are persisted to ``get_staging_dir()`` so the preview and
mapping endpoints can re-parse the same file without a second upload (RNF-05, T-3.7).
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import openpyxl
import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import text as sa_text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session  # noqa: TC002

from marketplace_conciliator.ingestion.block_locator import BlockLocator, BlockNotFoundError
from marketplace_conciliator.ingestion.column_suggester import ColumnSuggester
from marketplace_conciliator.ingestion.csv_parser import CsvParser
from marketplace_conciliator.ingestion.excel_parser import ExcelParser
from marketplace_conciliator.ingestion.sku_normalizer import normalise_sku
from marketplace_conciliator.platform.db.models.runs import (
    ColumnMapping,
    ReconciliationRun,
    SourceFile,
)
from marketplace_conciliator.platform.db.session import get_db
from marketplace_conciliator.platform.deps import CurrentUser, get_current_user
from marketplace_conciliator.settings import get_settings

router = APIRouter(prefix="/runs", tags=["ingestion"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB

_VALID_ROLES: frozenset[str] = frozenset({"occ_top", "wm_feed", "amazon_report"})

_EXCEL_EXTENSIONS: frozenset[str] = frozenset({".xlsx", ".xlsm", ".xltx", ".xltm"})
_CSV_EXTENSIONS: frozenset[str] = frozenset({".csv", ".txt", ".tsv"})

# Fraction of values that must be numeric for stock validation (mirrors column_suggester)
_STOCK_NUMERIC_THRESHOLD: float = 0.70
_NUMERIC_RE: re.Pattern[str] = re.compile(r"^[+-]?\d+([.,]\d+)?$")

# Number of sample rows returned in the preview response
_PREVIEW_SAMPLE_ROWS: int = 5


# ---------------------------------------------------------------------------
# Staging directory dependency
# ---------------------------------------------------------------------------


def get_staging_dir() -> Path:
    """Return the staging directory path, creating it if necessary.

    Overridable in tests via ``app.dependency_overrides[get_staging_dir]``.
    """
    d = get_settings().staging_dir
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Request / Response schemas — T-3.6
# ---------------------------------------------------------------------------


class CreateRunRequest(BaseModel):
    """Request body for creating a new reconciliation run."""

    marketplace: str = "amazon_es"


class RunResponse(BaseModel):
    """Response schema for a reconciliation run."""

    id: int
    user_id: int
    marketplace: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SourceFileResponse(BaseModel):
    """Response schema for an uploaded source file."""

    id: int
    run_id: int
    role: str
    original_filename: str
    sha256: str
    total_rows: int
    discarded_rows: int
    uploaded_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Request / Response schemas — T-3.7 (Preview contract, plan 3.7)
# ---------------------------------------------------------------------------


class SheetInfo(BaseModel):
    """Sheet name and approximate row count for an Excel workbook."""

    name: str
    rows: int


class BlockInfo(BaseModel):
    """Location metadata for a structured block inside a sheet (EB-02/03)."""

    title_matched: str
    header_row: int
    data_start_row: int


class HeaderInfo(BaseModel):
    """One column header descriptor."""

    index: int
    name: str
    technical_name: str | None = None


class ColumnSuggestionSchema(BaseModel):
    """Serializable form of a :class:`ColumnSuggestion`."""

    column_index: int
    confidence: float
    reason: str


class PreviewWarning(BaseModel):
    """Non-fatal issue encountered during preview parsing."""

    code: str
    message: str
    row: int | None = None


class PreviewResponse(BaseModel):
    """Contract for GET .../preview — plan 3.7."""

    file_role: str
    sheet: str | None
    available_sheets: list[SheetInfo] | None
    block: BlockInfo | None
    headers: list[HeaderInfo]
    sample_rows: list[list[str]]
    suggestions: dict[str, ColumnSuggestionSchema]
    warnings: list[PreviewWarning]
    discarded_rows: int


# ---------------------------------------------------------------------------
# Request / Response schemas — T-3.8 (Mapping)
# ---------------------------------------------------------------------------


class MappingItem(BaseModel):
    """A single logical-field → physical-column mapping."""

    logical_field: str
    column_index: int
    was_suggested: bool = False


class MappingRequest(BaseModel):
    """Request body for PUT .../mapping."""

    mappings: list[MappingItem]


class MappingWarning(BaseModel):
    """Warning issued during mapping validation."""

    code: str
    message: str
    sample: list[str] | None = None


class MappingResponse(BaseModel):
    """Response for PUT .../mapping."""

    status: str  # "ok" | "warnings"
    warnings: list[MappingWarning]


# ---------------------------------------------------------------------------
# Endpoints — T-3.6
# ---------------------------------------------------------------------------


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=RunResponse,
    summary="Create a new reconciliation run",
)
def create_run(
    body: CreateRunRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> RunResponse:
    """Create a new reconciliation run and return its metadata."""
    run = ReconciliationRun(
        user_id=current_user.id,
        marketplace=body.marketplace,
        status="uploaded",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return RunResponse(
        id=run.id,
        user_id=run.user_id,
        marketplace=run.marketplace,
        status=run.status,
        created_at=run.created_at,
    )


@router.post(
    "/{run_id}/files",
    status_code=status.HTTP_201_CREATED,
    response_model=SourceFileResponse,
    summary="Upload a source file for a run",
)
def upload_file(  # noqa: PLR0913
    run_id: int,
    role: Annotated[str, Form(description="one of: occ_top, wm_feed, amazon_report")],
    file: Annotated[UploadFile, File(description="The source file to upload")],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],  # noqa: ARG001
    db: Annotated[Session, Depends(get_db)],
    staging_dir: Annotated[Path, Depends(get_staging_dir)],
) -> SourceFileResponse:
    """Upload a source file and attach it to an existing run.

    Validates:
    - Run exists (404 if not found).
    - Role is one of the valid values (422).
    - File size ≤ 50 MB (413).
    - No duplicate role for the same run (409).

    Side-effect: raw bytes are saved to staging_dir/{id}{ext} so that the
    preview and mapping endpoints can re-parse without a second upload.
    """
    if role not in _VALID_ROLES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid role '{role}'. Must be one of: {sorted(_VALID_ROLES)}",
        )

    run = db.get(ReconciliationRun, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found.",
        )

    raw_bytes: bytes = file.file.read()
    if len(raw_bytes) > _MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File size {len(raw_bytes):,} bytes exceeds the 50 MB limit "
                f"({_MAX_FILE_SIZE_BYTES:,} bytes)."
            ),
        )

    sha256_hex: str = hashlib.sha256(raw_bytes).hexdigest()
    original_filename = file.filename or "unknown"

    source_file = SourceFile(
        run_id=run_id,
        role=role,
        original_filename=original_filename,
        sha256=sha256_hex,
        detected_encoding=None,
        detected_delimiter=None,
        sheet_name=None,
        data_start_row=None,
        total_rows=0,
        discarded_rows=0,
        uploaded_at=datetime.now(tz=UTC),
    )
    db.add(source_file)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A file with role '{role}' already exists for run {run_id}.",
        ) from None

    db.refresh(source_file)

    # Persist raw bytes to staging volume (enables preview / mapping without re-upload)
    ext = Path(original_filename).suffix.lower()
    staging_path = staging_dir / f"{source_file.id}{ext}"
    staging_path.write_bytes(raw_bytes)

    return SourceFileResponse(
        id=source_file.id,
        run_id=source_file.run_id,
        role=source_file.role,
        original_filename=source_file.original_filename,
        sha256=source_file.sha256,
        total_rows=source_file.total_rows,
        discarded_rows=source_file.discarded_rows,
        uploaded_at=source_file.uploaded_at,
    )


# ---------------------------------------------------------------------------
# Endpoint — T-3.7: GET preview
# ---------------------------------------------------------------------------


@router.get(
    "/{run_id}/files/{file_id}/preview",
    response_model=PreviewResponse,
    summary="Preview a staged source file with column suggestions",
)
def preview_file(
    run_id: int,
    file_id: int,
    db: Annotated[Session, Depends(get_db)],
    staging_dir: Annotated[Path, Depends(get_staging_dir)],
    sheet: Annotated[str | None, Query(description="Sheet name to preview (Excel only)")] = None,
) -> PreviewResponse:
    """Parse and preview a previously uploaded source file.

    Returns the exact preview contract from plan 3.7:
    - available_sheets with row counts (Excel only)
    - block location info (amazon_report only)
    - column headers and sample data rows
    - heuristic column suggestions with confidence + reason (OBJ-03)
    - warnings for non-fatal issues (discarded rows, missing blocks, etc.)
    """
    run = db.get(ReconciliationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")

    source_file = db.get(SourceFile, file_id)
    if source_file is None or source_file.run_id != run_id:
        raise HTTPException(status_code=404, detail=f"File {file_id} not found for run {run_id}.")

    ext = Path(source_file.original_filename).suffix.lower()
    staging_path = staging_dir / f"{file_id}{ext}"
    if not staging_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"Staged file for source_file {file_id} not found. "
                "Re-upload the file to regenerate the preview."
            ),
        )

    if ext in _EXCEL_EXTENSIONS:
        return _preview_excel(source_file, staging_path, sheet)
    if ext in _CSV_EXTENSIONS:
        return _preview_csv(source_file, staging_path)

    raise HTTPException(
        status_code=422,
        detail=f"Unsupported file extension '{ext}' for preview.",
    )


# ---------------------------------------------------------------------------
# Endpoint — T-3.8: PUT mapping
# ---------------------------------------------------------------------------


@router.put(
    "/{run_id}/files/{file_id}/mapping",
    response_model=MappingResponse,
    summary="Confirm column mapping for a source file",
)
def create_mapping(  # noqa: PLR0913
    run_id: int,
    file_id: int,
    body: MappingRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    staging_dir: Annotated[Path, Depends(get_staging_dir)],
) -> MappingResponse:
    """Confirm the column mapping for a source file and persist it.

    Validates:
    - Run exists (404).
    - File belongs to the run (404).
    - Stock column has ≥ 70% numeric values — if not, issues STOCK_NOT_NUMERIC warning
      but still persists the mapping (CA-04: degradación explícita, no hard rejection).
    - Out-of-range column indices: issues INVALID_COLUMN_INDEX warning, skips that entry.

    Upsert behaviour: a second PUT for the same (source_file_id, logical_field) replaces
    the previous row (UNIQUE constraint satisfied by delete-before-insert).

    Side-effect: run status advances to 'mapping' if still 'uploaded'.
    """
    run = db.get(ReconciliationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")

    source_file = db.get(SourceFile, file_id)
    if source_file is None or source_file.run_id != run_id:
        raise HTTPException(status_code=404, detail=f"File {file_id} not found for run {run_id}.")

    # Load the DataFrame for validation (same parse logic as preview)
    ext = Path(source_file.original_filename).suffix.lower()
    staging_path = staging_dir / f"{file_id}{ext}"
    if not staging_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"Staged file for source_file {file_id} not found. "
                "Re-upload the file before mapping."
            ),
        )

    df = _load_dataframe(source_file, staging_path)
    n_cols = len(df.columns)

    warnings: list[MappingWarning] = []
    now = datetime.now(tz=UTC)

    for item in body.mappings:
        # Validate column index range
        if item.column_index < 0 or item.column_index >= n_cols:
            warnings.append(
                MappingWarning(
                    code="INVALID_COLUMN_INDEX",
                    message=(
                        f"Column index {item.column_index} is out of range "
                        f"(file has {n_cols} columns)."
                    ),
                ),
            )
            continue

        col_name = str(df.columns[item.column_index])

        # Validate numeric ratio for stock fields (CA-04)
        if item.logical_field == "stock":
            ratio = _numeric_ratio(df, col_name)
            if ratio < _STOCK_NUMERIC_THRESHOLD:
                sample = (
                    df[col_name].dropna().astype(str).head(3).tolist()
                    if col_name in df.columns
                    else []
                )
                warnings.append(
                    MappingWarning(
                        code="STOCK_NOT_NUMERIC",
                        message=(
                            f"Column '{col_name}' has only {ratio:.0%} numeric values. "
                            "Stock quantities may be incorrect (degraded mode)."
                        ),
                        sample=sample,
                    ),
                )

        # Upsert: remove existing mapping for (source_file_id, logical_field) before inserting
        existing = (
            db.query(ColumnMapping)
            .filter(
                ColumnMapping.source_file_id == file_id,
                ColumnMapping.logical_field == item.logical_field,
            )
            .first()
        )
        if existing is not None:
            db.delete(existing)
            db.flush()

        db.add(
            ColumnMapping(
                source_file_id=file_id,
                logical_field=item.logical_field,
                source_column_name=col_name,
                source_column_index=item.column_index,
                was_suggested=item.was_suggested,
                confirmed_by=current_user.id,
                confirmed_at=now,
            ),
        )

    # Advance run status: uploaded → mapping (first time any mapping is confirmed)
    if run.status == "uploaded" and body.mappings:
        run.status = "mapping"

    db.commit()

    return MappingResponse(
        status="warnings" if warnings else "ok",
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Endpoint — T-3.10 / Gate CA-01: POST /runs/{run_id}/process
# ---------------------------------------------------------------------------


class ProcessResponse(BaseModel):
    """202 response body for POST /runs/{run_id}/process."""

    status_url: str


@router.post(
    "/{run_id}/process",
    status_code=202,
    response_model=ProcessResponse,
    summary="Trigger reconciliation processing for a run (gate RNF-08)",
)
def trigger_process(  # noqa: C901
    run_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],  # noqa: ARG001
    db: Annotated[Session, Depends(get_db)],
    staging_dir: Annotated[Path, Depends(get_staging_dir)],
) -> ProcessResponse:
    """Gate check (RNF-08) and minimal ingestion for the M3 BDD CA-01 gate.

    Returns 409 if any of the 3 required files is missing its SKU mapping.
    On success: reads all mapped SKU columns, normalises the values, inserts
    ``run_items`` rows with ``sku_raw`` / ``sku_norm`` for CA-01 scenario 3
    verification, and returns 202.

    NOTE: Full 3-way reconciliation pipeline (M4 — T-4.1..T-4.6) will extend
    this stub with deduplication, cross-join, error classification, and async
    execution.  The gate logic (409 on incomplete mapping) and the 202 contract
    do NOT change between M3 and M4 (ADR-002).
    """
    run = db.get(ReconciliationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")

    files = db.query(SourceFile).filter(SourceFile.run_id == run_id).all()
    file_by_role: dict[str, SourceFile] = {sf.role: sf for sf in files}

    required_roles: frozenset[str] = frozenset({"occ_top", "wm_feed", "amazon_report"})
    missing_roles = required_roles - set(file_by_role.keys())
    if missing_roles:
        raise HTTPException(
            status_code=409,
            detail=(
                f"mapeo pendiente de confirmación: "
                f"ficheros no cargados: {', '.join(sorted(missing_roles))}"
            ),
        )

    # Validate SKU mapping confirmed for every file (RNF-08 gate)
    for role, source_file in file_by_role.items():
        sku_mapping = (
            db.query(ColumnMapping)
            .filter(
                ColumnMapping.source_file_id == source_file.id,
                ColumnMapping.logical_field == "sku",
            )
            .first()
        )
        if sku_mapping is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"mapeo pendiente de confirmación: "
                    f"fichero '{role}' sin campo SKU confirmado"
                ),
            )

    # Gate passed — mark run as processing
    run.status = "processing"
    db.commit()

    # Minimal ingestion: parse each file's mapped SKU column → insert run_items
    seen_norms: set[str] = set()

    for role, source_file in file_by_role.items():
        sku_mapping = (
            db.query(ColumnMapping)
            .filter(
                ColumnMapping.source_file_id == source_file.id,
                ColumnMapping.logical_field == "sku",
            )
            .first()
        )
        if sku_mapping is None:  # already validated above — defensive guard
            continue

        ext = Path(source_file.original_filename).suffix.lower()
        staging_path = staging_dir / f"{source_file.id}{ext}"
        if not staging_path.exists():
            continue

        df = _load_dataframe(source_file, staging_path)
        col_idx = sku_mapping.source_column_index
        if col_idx >= len(df.columns):
            continue

        col_name = str(df.columns[col_idx])
        in_occ: int = 1 if role == "occ_top" else 0
        in_feed: int = 1 if role == "wm_feed" else 0
        in_amazon: int = 1 if role == "amazon_report" else 0

        for raw_val in df[col_name].tolist():
            raw_str = str(raw_val) if raw_val is not None else ""
            norm_result = normalise_sku(raw_str)
            if not norm_result.is_valid or norm_result.value is None:
                continue
            sku_norm = norm_result.value
            if sku_norm in seen_norms:
                continue
            seen_norms.add(sku_norm)

            db.execute(
                sa_text("""
                    INSERT OR IGNORE INTO run_items
                        (run_id, sku_norm, sku_raw, in_occ, in_feed, in_amazon_report,
                         sync_status, stock_conflict)
                    VALUES
                        (:run_id, :sku_norm, :sku_raw, :in_occ, :in_feed, :in_amazon,
                         'NOT_SENT', 0)
                """),
                {
                    "run_id": run_id,
                    "sku_norm": sku_norm,
                    "sku_raw": raw_str,
                    "in_occ": in_occ,
                    "in_feed": in_feed,
                    "in_amazon": in_amazon,
                },
            )

    run.status = "completed"
    db.commit()

    return ProcessResponse(status_url=f"/api/v1/runs/{run_id}/status")


# ---------------------------------------------------------------------------
# Private parsing helpers
# ---------------------------------------------------------------------------


def _staging_path(staging_dir: Path, file_id: int, original_filename: str) -> Path:
    ext = Path(original_filename).suffix.lower()
    return staging_dir / f"{file_id}{ext}"


def _count_sheet_rows(path: Path) -> dict[str, int]:
    """Return {sheet_name: max_row} for all sheets without reading cell data."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True, keep_vba=False)
    try:
        return {name: wb[name].max_row or 0 for name in wb.sheetnames}
    finally:
        wb.close()


def _default_sheet_for_role(role: str, all_sheets: list[str]) -> str | None:
    """Pick the most relevant sheet for a given file role heuristically."""
    if not all_sheets:
        return None
    role_lower = role.lower()
    hints: list[str]
    if "amazon_report" in role_lower:
        hints = ["resumen", "summary", "processing"]
    elif "occ_top" in role_lower:
        hints = ["plantilla", "template", "datos", "data"]
    else:
        hints = []
    for hint in hints:
        for name in all_sheets:
            if hint in name.lower():
                return name
    return all_sheets[0]


def _build_suggestions(df: pd.DataFrame) -> dict[str, ColumnSuggestionSchema]:
    """Run ColumnSuggester and return the top suggestion per logical field."""
    suggestions_list = ColumnSuggester().suggest(df)
    best: dict[str, ColumnSuggestionSchema] = {}
    for s in suggestions_list:
        key = s.logical_field.value
        if key not in best or s.confidence > best[key].confidence:
            best[key] = ColumnSuggestionSchema(
                column_index=s.column_index,
                confidence=s.confidence,
                reason=s.reason,
            )
    return best


def _dataframe_to_sample(df: pd.DataFrame, n: int = _PREVIEW_SAMPLE_ROWS) -> list[list[str]]:
    """Convert the first n rows of a DataFrame to a list-of-lists of strings."""
    return [
        [str(v) if v is not None else "" for v in row]
        for row in df.head(n).to_numpy(dtype=object).tolist()
    ]


def _headers_from_df(df: pd.DataFrame) -> list[HeaderInfo]:
    return [HeaderInfo(index=i, name=str(col)) for i, col in enumerate(df.columns)]


def _numeric_ratio(df: pd.DataFrame, col_name: str) -> float:
    """Return fraction of non-empty values in col_name that match a numeric pattern."""
    try:
        series = df[col_name].dropna().astype(str)
        series = series[series.str.strip() != ""]
        if len(series) == 0:
            return 0.0
        count = series.apply(lambda v: bool(_NUMERIC_RE.match(v.strip()))).sum()
        return float(count) / len(series)
    except Exception:  # noqa: BLE001
        return 0.0


def _preview_csv(source_file: SourceFile, path: Path) -> PreviewResponse:
    """Build preview response for a flat CSV/TXT file."""
    parsed = CsvParser().parse(path)
    df = parsed.dataframe
    suggestions = _build_suggestions(df)

    return PreviewResponse(
        file_role=source_file.role,
        sheet=None,
        available_sheets=None,
        block=None,
        headers=_headers_from_df(df),
        sample_rows=_dataframe_to_sample(df),
        suggestions=suggestions,
        warnings=[],
        discarded_rows=0,
    )


def _preview_excel(
    source_file: SourceFile,
    path: Path,
    sheet_param: str | None,
) -> PreviewResponse:
    """Build preview response for an XLSX/XLSM file."""
    excel_parser = ExcelParser()
    all_sheet_names: list[str] = excel_parser.list_sheets(path) or []

    # Row counts (fast — reads worksheet dimension XML, not all cells)
    row_counts: dict[str, int] = {}
    try:
        row_counts = _count_sheet_rows(path)
    except Exception:  # noqa: BLE001
        row_counts = dict.fromkeys(all_sheet_names, 0)

    available_sheets = [
        SheetInfo(name=name, rows=row_counts.get(name, 0))
        for name in all_sheet_names
    ]

    # Determine target sheet
    target_sheet: str = (
        sheet_param
        if sheet_param and sheet_param in all_sheet_names
        else (_default_sheet_for_role(source_file.role, all_sheet_names) or "")
    )

    parsed = excel_parser.parse(path, sheet_name=target_sheet)
    df = parsed.dataframe

    block_info: BlockInfo | None = None
    preview_warnings: list[PreviewWarning] = []
    discarded = 0

    role = source_file.role
    locator = BlockLocator()

    if role == "amazon_report":
        try:
            located = locator.locate_errors_block(df)
            df = located.dataframe
            discarded = located.discarded_rows
            block_info = BlockInfo(
                title_matched="Errores y advertencias por SKU",
                header_row=located.title_row,
                data_start_row=located.data_start_row,
            )
            preview_warnings.extend(
                PreviewWarning(code="BLOCK_WARNING", message=w) for w in located.warnings
            )
        except BlockNotFoundError as exc:
            preview_warnings.append(
                PreviewWarning(code="BLOCK_NOT_FOUND", message=str(exc)),
            )

    elif role == "occ_top" and "plantilla" in target_sheet.lower():
        located = locator.parse_plantilla(df)
        df = located.dataframe
        discarded = located.discarded_rows
        if discarded > 0:
            preview_warnings.append(
                PreviewWarning(
                    code="EXAMPLE_ROW_DISCARDED",
                    message=(
                        f"Fila(s) de ejemplo de Amazon descartada(s) (EB-04): {discarded} fila(s)."
                    ),
                    row=6,
                ),
            )

    suggestions = _build_suggestions(df)

    return PreviewResponse(
        file_role=source_file.role,
        sheet=target_sheet,
        available_sheets=available_sheets,
        block=block_info,
        headers=_headers_from_df(df),
        sample_rows=_dataframe_to_sample(df),
        suggestions=suggestions,
        warnings=preview_warnings,
        discarded_rows=discarded,
    )


def _load_dataframe(source_file: SourceFile, path: Path) -> pd.DataFrame:
    """Parse the staged file and return the relevant DataFrame for mapping validation.

    Applies the same role-based logic as _preview_excel / _preview_csv so that
    the mapping validates against the SAME data that the user sees in the preview.
    """
    ext = path.suffix.lower()

    if ext in _CSV_EXTENSIONS:
        return CsvParser().parse(path).dataframe

    if ext in _EXCEL_EXTENSIONS:
        excel_parser = ExcelParser()
        all_sheets = excel_parser.list_sheets(path) or []
        target = _default_sheet_for_role(source_file.role, all_sheets) or ""
        df = excel_parser.parse(path, sheet_name=target).dataframe

        role = source_file.role
        locator = BlockLocator()

        if role == "amazon_report":
            try:
                return locator.locate_errors_block(df).dataframe
            except BlockNotFoundError:
                return df

        if role == "occ_top" and "plantilla" in target.lower():
            return locator.parse_plantilla(df).dataframe

        return df

    return pd.DataFrame()
