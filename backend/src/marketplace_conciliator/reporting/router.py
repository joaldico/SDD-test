"""Reporting API router — T-5.1 dashboard metrics + T-5.2 report views.

Endpoints:
  GET /api/v1/runs/{run_id}/metrics          Dashboard KPIs for a completed run.
  GET /api/v1/runs/{run_id}/report/families  Vista 1 — errors grouped by family.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — used at runtime in response mapping
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session  # noqa: TC002

from marketplace_conciliator.platform.db.models.runs import ReconciliationRun
from marketplace_conciliator.platform.db.session import get_db
from marketplace_conciliator.reporting.families import RawFamilyRow, build_families_report
from marketplace_conciliator.reporting.metrics import (
    MetricsNotReadyError,
    build_dashboard_metrics,
)

router = APIRouter(prefix="/runs", tags=["reporting"])


class DashboardSummaryResponse(BaseModel):
    """Primary KPI cards for the dashboard shell."""

    total_skus: int
    total_errors: int
    desynchronized: int


class SyncStatusBreakdownResponse(BaseModel):
    """Detailed sync_status counters for future report tabs."""

    sent_with_error: int
    sent_ok: int
    not_sent: int
    desync_feed_only: int
    desync_amazon_only: int


class RunMetricsResponse(BaseModel):
    """Response body for GET /runs/{run_id}/metrics (T-5.1 dashboard shell)."""

    run_id: int
    status: str
    completed_at: datetime | None
    summary: DashboardSummaryResponse
    by_sync_status: SyncStatusBreakdownResponse


def _format_completed_at(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


@router.get(
    "/{run_id}/metrics",
    response_model=RunMetricsResponse,
    summary="Dashboard KPI metrics for a completed reconciliation run (T-5.1)",
)
def get_run_metrics(
    run_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> RunMetricsResponse:
    """Return structured dashboard metrics for the main report shell.

    Only available once the run has reached ``completed`` status and
    ``summary_metrics`` has been persisted (plan 3.4, T-4.5).
    """
    run = db.get(ReconciliationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")

    if run.status != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Metrics not ready for run {run_id} (status={run.status}).",
        )

    try:
        metrics = build_dashboard_metrics(
            run_id=run_id,
            status=run.status,
            completed_at=_format_completed_at(run.completed_at),
            summary_metrics=run.summary_metrics,
        )
    except MetricsNotReadyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return RunMetricsResponse(
        run_id=metrics.run_id,
        status=metrics.status,
        completed_at=run.completed_at,
        summary=DashboardSummaryResponse(
            total_skus=metrics.summary.total_skus,
            total_errors=metrics.summary.total_errors,
            desynchronized=metrics.summary.desynchronized,
        ),
        by_sync_status=SyncStatusBreakdownResponse(
            sent_with_error=metrics.by_sync_status.sent_with_error,
            sent_ok=metrics.by_sync_status.sent_ok,
            not_sent=metrics.by_sync_status.not_sent,
            desync_feed_only=metrics.by_sync_status.desync_feed_only,
            desync_amazon_only=metrics.by_sync_status.desync_amazon_only,
        ),
    )


class ErrorCodeBreakdownResponse(BaseModel):
    """One error code row within a family breakdown."""

    code: str
    message: str
    count: int


class FamilyBreakdownResponse(BaseModel):
    """Aggregated family with nested code counts."""

    code: str
    display_name: str
    unique_skus: int
    total_errors: int
    codes: list[ErrorCodeBreakdownResponse]


class FamiliesReportResponse(BaseModel):
    """Response body for GET /runs/{run_id}/report/families (Vista 1, T-5.2)."""

    run_id: int
    families: list[FamilyBreakdownResponse]
    sin_clasificar_warning: bool = Field(
        description="True when SIN_CLASIFICAR family has errors — requires operator review.",
    )


def _require_completed_run(db: Session, run_id: int) -> ReconciliationRun:
    run = db.get(ReconciliationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")
    if run.status != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Report not ready for run {run_id} (status={run.status}).",
        )
    return run


_FAMILIES_QUERY = sa_text("""
    SELECT
        ef.code AS family_code,
        ef.display_name,
        ef.sort_order,
        ec.code AS error_code,
        COALESCE(ec.canonical_message, MIN(ie.error_message)) AS message,
        COUNT(ie.id) AS error_count,
        (
            SELECT COUNT(DISTINCT ri2.sku_norm)
            FROM item_errors ie2
            JOIN run_items ri2 ON ri2.id = ie2.run_item_id
            JOIN error_codes ec2 ON ec2.code = ie2.error_code
            WHERE ri2.run_id = :run_id
              AND ec2.family_code = ef.code
        ) AS family_unique_skus
    FROM item_errors ie
    JOIN run_items ri ON ri.id = ie.run_item_id
    JOIN error_codes ec ON ec.code = ie.error_code
    JOIN error_families ef ON ef.code = ec.family_code
    WHERE ri.run_id = :run_id
    GROUP BY ef.code, ef.display_name, ef.sort_order, ec.code
    ORDER BY ef.sort_order ASC, error_count DESC
""")


@router.get(
    "/{run_id}/report/families",
    response_model=FamiliesReportResponse,
    summary="Vista 1 — Errores agrupados por familia (T-5.2)",
)
def get_families_report(
    run_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> FamiliesReportResponse:
    """Return error aggregation by business family with code drill-down."""
    _require_completed_run(db, run_id)

    rows = db.execute(_FAMILIES_QUERY, {"run_id": run_id}).fetchall()
    raw_rows = [
        RawFamilyRow(
            family_code=str(row[0]),
            display_name=str(row[1]),
            sort_order=int(row[2]),
            error_code=str(row[3]),
            message=str(row[4]),
            error_count=int(row[5]),
            family_unique_skus=int(row[6]),
        )
        for row in rows
    ]
    report = build_families_report(run_id=run_id, rows=raw_rows)

    return FamiliesReportResponse(
        run_id=report.run_id,
        sin_clasificar_warning=report.sin_clasificar_warning,
        families=[
            FamilyBreakdownResponse(
                code=f.code,
                display_name=f.display_name,
                unique_skus=f.unique_skus,
                total_errors=f.total_errors,
                codes=[
                    ErrorCodeBreakdownResponse(
                        code=c.code,
                        message=c.message,
                        count=c.count,
                    )
                    for c in f.codes
                ],
            )
            for f in report.families
        ],
    )
