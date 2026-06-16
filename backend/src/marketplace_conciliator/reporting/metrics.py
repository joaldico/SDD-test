"""Dashboard metrics builder — pure domain logic (T-5.1).

Transforms persisted ``summary_metrics`` JSON into the structured response
consumed by the React dashboard shell. No I/O or framework imports.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

_REQUIRED_KEYS: frozenset[str] = frozenset(
    {
        "total_skus",
        "sent_with_error",
        "sent_ok",
        "not_sent",
        "desync_feed_only",
        "desync_amazon_only",
        "total_errors",
    },
)


class MetricsNotReadyError(Exception):
    """Raised when summary_metrics is absent or incomplete for a run."""


@dataclass(frozen=True, slots=True)
class DashboardSummary:
    """Top-level KPI cards for the dashboard shell."""

    total_skus: int
    total_errors: int
    desynchronized: int


@dataclass(frozen=True, slots=True)
class SyncStatusBreakdown:
    """Full sync_status counters — reused by future report tabs (T-5.2+)."""

    sent_with_error: int
    sent_ok: int
    not_sent: int
    desync_feed_only: int
    desync_amazon_only: int


@dataclass(frozen=True, slots=True)
class RunDashboardMetrics:
    """Structured dashboard payload for GET /runs/{id}/metrics."""

    run_id: int
    status: str
    completed_at: str | None
    summary: DashboardSummary
    by_sync_status: SyncStatusBreakdown


def parse_summary_metrics(raw: dict[str, Any] | str | None) -> dict[str, Any] | None:
    """Normalise summary_metrics from ORM (dict or JSON string) to a dict."""
    if raw is None:
        return None
    if isinstance(raw, str):
        parsed: dict[str, Any] = json.loads(raw)
        return parsed
    return raw


def build_dashboard_metrics(
    *,
    run_id: int,
    status: str,
    completed_at: str | None,
    summary_metrics: dict[str, Any] | str | None,
) -> RunDashboardMetrics:
    """Build the dashboard metrics response from persisted run data."""
    parsed = parse_summary_metrics(summary_metrics)
    if parsed is None:
        msg = f"Metrics not ready for run {run_id} (status={status})."
        raise MetricsNotReadyError(msg)

    missing = _REQUIRED_KEYS - parsed.keys()
    if missing:
        msg = f"Metrics not ready for run {run_id}: missing keys {sorted(missing)}."
        raise MetricsNotReadyError(msg)

    desync_feed = int(parsed["desync_feed_only"])
    desync_amazon = int(parsed["desync_amazon_only"])

    return RunDashboardMetrics(
        run_id=run_id,
        status=status,
        completed_at=completed_at,
        summary=DashboardSummary(
            total_skus=int(parsed["total_skus"]),
            total_errors=int(parsed["total_errors"]),
            desynchronized=desync_feed + desync_amazon,
        ),
        by_sync_status=SyncStatusBreakdown(
            sent_with_error=int(parsed["sent_with_error"]),
            sent_ok=int(parsed["sent_ok"]),
            not_sent=int(parsed["not_sent"]),
            desync_feed_only=desync_feed,
            desync_amazon_only=desync_amazon,
        ),
    )
