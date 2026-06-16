"""T-5.1 — Unit tests for reporting.metrics (pure domain logic, TDD)."""

from __future__ import annotations

import json

import pytest

from marketplace_conciliator.reporting.metrics import (
    MetricsNotReadyError,
    build_dashboard_metrics,
    parse_summary_metrics,
)

_FULL_METRICS: dict[str, int] = {
    "total_skus": 4094,
    "sent_with_error": 120,
    "sent_ok": 3200,
    "not_sent": 708,
    "desync_feed_only": 62,
    "desync_amazon_only": 4,
    "total_errors": 845,
}


class TestParseSummaryMetrics:
    def test_parses_dict_as_is(self) -> None:
        raw = {"total_skus": 10, "total_errors": 3}
        assert parse_summary_metrics(raw) == raw

    def test_parses_json_string(self) -> None:
        raw = {"total_skus": 42, "total_errors": 7}
        assert parse_summary_metrics(json.dumps(raw)) == raw

    def test_none_returns_none(self) -> None:
        assert parse_summary_metrics(None) is None


class TestBuildDashboardMetrics:
    def test_builds_summary_cards_for_dashboard(self) -> None:
        result = build_dashboard_metrics(
            run_id=7,
            status="completed",
            completed_at="2026-06-16T12:00:00",
            summary_metrics=_FULL_METRICS,
        )

        assert result.run_id == 7
        assert result.status == "completed"
        assert result.completed_at == "2026-06-16T12:00:00"
        assert result.summary.total_skus == 4094
        assert result.summary.total_errors == 845
        assert result.summary.desynchronized == 66

    def test_exposes_full_sync_status_breakdown(self) -> None:
        result = build_dashboard_metrics(
            run_id=1,
            status="completed",
            completed_at=None,
            summary_metrics=_FULL_METRICS,
        )

        assert result.by_sync_status.sent_with_error == 120
        assert result.by_sync_status.sent_ok == 3200
        assert result.by_sync_status.not_sent == 708
        assert result.by_sync_status.desync_feed_only == 62
        assert result.by_sync_status.desync_amazon_only == 4

    def test_raises_when_metrics_missing(self) -> None:
        with pytest.raises(MetricsNotReadyError):
            build_dashboard_metrics(
                run_id=1,
                status="processing",
                completed_at=None,
                summary_metrics=None,
            )

    def test_raises_when_required_key_missing(self) -> None:
        incomplete = {"total_skus": 1}
        with pytest.raises(MetricsNotReadyError):
            build_dashboard_metrics(
                run_id=1,
                status="completed",
                completed_at=None,
                summary_metrics=incomplete,
            )
