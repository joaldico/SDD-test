"""Reporting API router — T-5.1 dashboard metrics endpoint.

Endpoints:
  GET /api/v1/runs/{run_id}/metrics   Dashboard KPIs for a completed run.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — used at runtime in response mapping
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session  # noqa: TC002

from marketplace_conciliator.platform.db.models.runs import ReconciliationRun
from marketplace_conciliator.platform.db.session import get_db
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
