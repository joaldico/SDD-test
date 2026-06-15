"""Ingestion API router — POST /runs and POST /runs/{id}/files (T-3.6).

Endpoints:
  POST /api/v1/runs               Create a new reconciliation run.
  POST /api/v1/runs/{id}/files    Upload a source file for a run.

Auth: uses the dummy ``get_current_user`` dependency (M2 bypass, see platform/deps.py).
DB:   uses the synchronous ``get_db`` session dependency (overridable in tests).

Size limit: 50 MB per file (RNF-05). Enforced before any parsing.
SHA-256: computed from the raw upload bytes for integrity traceability (RNF-05).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session  # noqa: TC002

from marketplace_conciliator.platform.db.models.runs import ReconciliationRun, SourceFile
from marketplace_conciliator.platform.db.session import get_db
from marketplace_conciliator.platform.deps import CurrentUser, get_current_user

router = APIRouter(prefix="/runs", tags=["ingestion"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB

_VALID_ROLES: frozenset[str] = frozenset({"occ_top", "wm_feed", "amazon_report"})


# ---------------------------------------------------------------------------
# Request / Response schemas
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
# Endpoints
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
def upload_file(
    run_id: int,
    role: Annotated[str, Form(description="one of: occ_top, wm_feed, amazon_report")],
    file: Annotated[UploadFile, File(description="The source file to upload")],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],  # noqa: ARG001
    db: Annotated[Session, Depends(get_db)],
) -> SourceFileResponse:
    """Upload a source file and attach it to an existing run.

    Validates:
    - Run exists (404 if not found).
    - Role is one of the valid values (422 via Pydantic/query validation).
    - File size ≤ 50 MB (413 if exceeded).
    - No duplicate role for the same run (409 if violated).

    Returns metadata including the computed SHA-256 digest (RNF-05).
    """
    # 1. Validate role value before reading bytes (fast-fail)
    if role not in _VALID_ROLES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid role '{role}'. Must be one of: {sorted(_VALID_ROLES)}",
        )

    # 2. Verify the run exists
    run = db.get(ReconciliationRun, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found.",
        )

    # 3. Read all bytes and enforce size limit (RNF-05)
    raw_bytes: bytes = file.file.read()
    if len(raw_bytes) > _MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File size {len(raw_bytes):,} bytes exceeds the 50 MB limit "
                f"({_MAX_FILE_SIZE_BYTES:,} bytes)."
            ),
        )

    # 4. Compute SHA-256 integrity hash (RNF-05)
    sha256_hex: str = hashlib.sha256(raw_bytes).hexdigest()

    # 5. Persist source_file metadata
    source_file = SourceFile(
        run_id=run_id,
        role=role,
        original_filename=file.filename or "unknown",
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
