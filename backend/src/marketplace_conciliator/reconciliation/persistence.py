"""Transactional batch persistence — T-4.5 (RF-10, plan 3.4).

Single responsibility: write ``run_items`` + ``item_errors`` as one atomic
unit and transition the run to ``completed`` with ``summary_metrics``.

Guarantee:
  If ANY write step raises, the session is rolled back completely.
  The run is then marked ``failed`` with a ``failure_reason`` (at most 255 chars).
  No orphan rows are left in ``run_items`` or ``item_errors``.

Hexagonal constraint (ADR-001):
  Imports only ``sqlalchemy``, stdlib, and the ``error_classifier`` sibling
  module.  No ``platform.*`` or ``ingestion.*`` imports.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import text as sa_text

from marketplace_conciliator.reconciliation.error_classifier import (
    ErrorRow,
    classify_and_insert_errors,
    insert_ignore_into,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


@dataclass
class RunItemData:
    """All data for a single reconciled SKU, ready to write to the DB.

    ``error_rows`` contains the 0‥N errors from the Amazon report for this
    SKU (legitimate 1:N cardinality — spec 2.2.3).
    """

    sku_norm: str
    sku_raw: str
    in_occ: bool
    in_feed: bool
    in_amazon_report: bool
    sync_status: str
    feed_stock: int | None
    occ_stock: int | None
    stock_conflict: bool
    error_rows: list[ErrorRow] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def persist_run_results(
    db: Session,
    run_id: int,
    items: list[RunItemData],
) -> None:
    """Write all reconciliation results atomically, then mark the run completed.

    Uses a SAVEPOINT (``db.begin_nested()``) to wrap the batch write so that
    only the batch is rolled back on failure — the outer transaction (which
    owns the run row itself) survives and can record the failure reason.

    Steps:
      1. SAVEPOINT: batch-insert ``run_items`` + ``item_errors``.
         If this raises → ROLLBACK TO SAVEPOINT (no orphan rows), mark run
         as ``failed``, commit, re-raise.
      2. Compute ``summary_metrics`` JSON from the written items.
      3. Update the run: status→completed, completed_at, summary_metrics.
      4. Final COMMIT.

    Args:
        db:     Active SQLAlchemy session (caller controls the connection).
        run_id: ID of the run whose results are being persisted.
        items:  One ``RunItemData`` per reconciled SKU.

    """
    try:
        # ── SAVEPOINT wraps the entire batch write ───────────────────────
        with db.begin_nested():
            # Step 1a: batch-insert run_items
            _write_run_items_batch(db, run_id, items)
            db.flush()

            # Step 1b: classify + insert item_errors
            all_error_rows: list[ErrorRow] = []
            for item in items:
                all_error_rows.extend(item.error_rows)

            if all_error_rows:
                classify_and_insert_errors(db, run_id, all_error_rows)
                db.flush()
        # SAVEPOINT RELEASE — batch is now visible in the outer transaction

        # ── Step 2: compute summary_metrics ─────────────────────────────
        metrics = _compute_summary_metrics(items)

        # ── Step 3: transition run to completed ──────────────────────────
        db.execute(
            sa_text("""
                UPDATE reconciliation_runs
                SET
                    status          = 'completed',
                    phase           = NULL,
                    completed_at    = :completed_at,
                    summary_metrics = :summary_metrics
                WHERE id = :run_id
            """),
            {
                "run_id": run_id,
                "completed_at": datetime.now(tz=UTC).isoformat(),
                "summary_metrics": json.dumps(metrics),
            },
        )
        db.commit()

    except Exception as exc:
        # SAVEPOINT was already rolled back by the context manager.
        # The outer transaction still holds the run row — update to failed.
        reason = str(exc)[:255]
        try:
            db.execute(
                sa_text("""
                    UPDATE reconciliation_runs
                    SET status = 'failed', failure_reason = :reason, phase = NULL
                    WHERE id = :run_id
                """),
                {"run_id": run_id, "reason": reason},
            )
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()

        raise


# ---------------------------------------------------------------------------
# Internal helpers (named so tests can patch them via their fully-qualified path)
# ---------------------------------------------------------------------------


def _write_run_items_batch(
    db: Session,
    run_id: int,
    items: list[RunItemData],
) -> None:
    """Insert all run_items rows using INSERT IGNORE / OR IGNORE for idempotency.

    Named as a standalone function so unit tests can patch it to simulate
    write failures and verify rollback behaviour (T-4.5 DoD).
    """
    insert_prefix = insert_ignore_into(db)
    for item in items:
        db.execute(
            sa_text(f"""
                {insert_prefix} run_items
                    (run_id, sku_norm, sku_raw,
                     in_occ, in_feed, in_amazon_report,
                     feed_stock, occ_stock, stock_conflict, sync_status)
                VALUES
                    (:run_id, :sku_norm, :sku_raw,
                     :in_occ, :in_feed, :in_amazon,
                     :feed_stock, :occ_stock, :stock_conflict, :sync_status)
            """),
            {
                "run_id": run_id,
                "sku_norm": item.sku_norm,
                "sku_raw": item.sku_raw,
                "in_occ": 1 if item.in_occ else 0,
                "in_feed": 1 if item.in_feed else 0,
                "in_amazon": 1 if item.in_amazon_report else 0,
                "feed_stock": item.feed_stock,
                "occ_stock": item.occ_stock,
                "stock_conflict": 1 if item.stock_conflict else 0,
                "sync_status": item.sync_status,
            },
        )


def _compute_summary_metrics(items: list[RunItemData]) -> dict[str, int]:
    """Aggregate counts by sync_status and total errors for summary_metrics JSON.

    Keys follow the spec 2.7 vocabulary so the frontend and Vista 1 can consume
    them directly without translation.
    """
    counters: dict[str, int] = {
        "total_skus": len(items),
        "sent_with_error": 0,
        "sent_ok": 0,
        "not_sent": 0,
        "desync_feed_only": 0,
        "desync_amazon_only": 0,
        "total_errors": 0,
    }
    _status_map: dict[str, str] = {
        "SENT_WITH_ERROR": "sent_with_error",
        "SENT_OK": "sent_ok",
        "NOT_SENT": "not_sent",
        "DESYNC_FEED_ONLY": "desync_feed_only",
        "DESYNC_AMAZON_ONLY": "desync_amazon_only",
    }
    for item in items:
        key = _status_map.get(item.sync_status)
        if key:
            counters[key] += 1
        counters["total_errors"] += len(item.error_rows)
    return counters
