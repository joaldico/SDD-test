"""Taxonomy admin API — error family catalog and code reassignment (T-5.6, RF-14).

Endpoints:
  GET   /api/v1/error-families       List families and error codes (catalog).
  PATCH /api/v1/error-codes/{code}   Reassign a code to a family (admin only).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session  # noqa: TC002

from marketplace_conciliator.platform.db.models.taxonomy import ErrorCode, ErrorFamily
from marketplace_conciliator.platform.db.session import get_db
from marketplace_conciliator.platform.deps import require_role

router = APIRouter(tags=["taxonomy"])


class ErrorFamilyItemResponse(BaseModel):
    """One business family in the taxonomy catalog."""

    code: str
    display_name: str
    sort_order: int


class ErrorCodeCatalogItemResponse(BaseModel):
    """One Amazon error code with its current family assignment."""

    code: str
    family_code: str
    default_category: str | None
    canonical_message: str | None


class ErrorTaxonomyResponse(BaseModel):
    """Response for GET /error-families — full maintainable catalog."""

    families: list[ErrorFamilyItemResponse]
    codes: list[ErrorCodeCatalogItemResponse]


class PatchErrorCodeRequest(BaseModel):
    """Body for PATCH /error-codes/{code}."""

    family_code: str = Field(min_length=1, max_length=32)


class ErrorCodeResponse(BaseModel):
    """Updated error code after reassignment."""

    code: str
    family_code: str
    default_category: str | None
    canonical_message: str | None


@router.get(
    "/error-families",
    response_model=ErrorTaxonomyResponse,
    summary="Taxonomy catalog — families and error codes (T-5.6, RF-14)",
)
def list_error_taxonomy(
    db: Annotated[Session, Depends(get_db)],
) -> ErrorTaxonomyResponse:
    """Return all error families and codes for the taxonomy admin UI."""
    families = db.query(ErrorFamily).order_by(ErrorFamily.sort_order.asc()).all()
    codes = db.query(ErrorCode).order_by(ErrorCode.code.asc()).all()

    return ErrorTaxonomyResponse(
        families=[
            ErrorFamilyItemResponse(
                code=f.code,
                display_name=f.display_name,
                sort_order=f.sort_order,
            )
            for f in families
        ],
        codes=[
            ErrorCodeCatalogItemResponse(
                code=c.code,
                family_code=c.family_code,
                default_category=c.default_category,
                canonical_message=c.canonical_message,
            )
            for c in codes
        ],
    )


@router.patch(
    "/error-codes/{code}",
    response_model=ErrorCodeResponse,
    summary="Reassign error code to a family (admin only, T-5.6)",
)
def patch_error_code_family(
    code: str,
    body: PatchErrorCodeRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[object, Depends(require_role("admin"))],
) -> ErrorCodeResponse:
    """Update ``family_code`` for an existing error code without redeployment."""
    error_code = db.get(ErrorCode, code)
    if error_code is None:
        raise HTTPException(status_code=404, detail=f"Error code '{code}' not found.")

    family_exists = db.execute(
        sa_text("SELECT 1 FROM error_families WHERE code = :code LIMIT 1"),
        {"code": body.family_code},
    ).scalar_one_or_none()
    if family_exists is None:
        raise HTTPException(
            status_code=422,
            detail=f"Family '{body.family_code}' does not exist.",
        )

    error_code.family_code = body.family_code
    db.commit()
    db.refresh(error_code)

    return ErrorCodeResponse(
        code=error_code.code,
        family_code=error_code.family_code,
        default_category=error_code.default_category,
        canonical_message=error_code.canonical_message,
    )
