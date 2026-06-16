"""Error classifier — T-4.4 (spec 2.8, RF-07, RF-14, EB-10).

Responsibilities:
  1. Normalise error messages: strip NBSP (U+00A0) and collapse whitespace (EB-05).
  2. Classify error rows by looking up ``error_codes.family_code`` in the DB.
  3. Auto-insert unknown error codes with ``family_code='SIN_CLASIFICAR'`` and
     ``first_seen_at=<now>`` (EB-10, RF-14).
  4. Insert ``item_errors`` rows linked to the correct ``run_item_id``.

Hexagonal constraint (ADR-001):
  This module ONLY imports from ``platform.db.session`` (via the injected
  ``Session``) and the stdlib.  No cross-module imports except ``sqlalchemy``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import text as sa_text

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Matches one or more whitespace chars (including NBSP U+00A0) for collapse
_WS_RE: re.Pattern[str] = re.compile(r"[\s\u00a0]+")


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ErrorRow:
    """One error row from the Amazon processing report (spec 2.2.3).

    All string fields are expected to be pre-extracted from the DataFrame
    (dtype=str, values may still contain NBSP artefacts — EB-05).
    """

    sku_norm: str
    error_code: str
    error_category: str  # raw value — normalised by classifier to ERROR/ADVERTENCIA
    error_message: str
    affected_field: str | None = field(default=None)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def normalise_error_message(msg: str) -> str:
    """Replace NBSP (U+00A0) with a regular space and collapse whitespace.

    EB-05: Amazon export files contain NBSP inside error message text.
    We normalise before persistence so that string comparisons and full-text
    search work correctly in all downstream consumers.
    """
    return _WS_RE.sub(" ", msg).strip()


def classify_and_insert_errors(
    db: Session,
    run_id: int,
    rows: list[ErrorRow],
) -> None:
    """Classify error rows, auto-insert unknown codes, and persist item_errors.

    For each ``ErrorRow``:
      1. The error_code is looked up against ``error_codes``.
         - If found: reuse the existing family (no modification).
         - If missing: INSERT with ``family_code='SIN_CLASIFICAR'`` and
           ``first_seen_at=now()`` (INSERT OR IGNORE to prevent races).
      2. The ``run_item_id`` for the SKU is resolved from ``run_items``.
      3. An ``item_errors`` row is inserted with the normalised message.

    The caller is responsible for the outer transaction / session lifecycle.

    Args:
        db:     Active SQLAlchemy session (write access expected).
        run_id: ID of the current reconciliation run.
        rows:   List of error rows extracted from the Amazon report.

    """
    known_codes: set[str] = set()
    now_iso = datetime.now(tz=UTC).isoformat()

    for row in rows:
        code = row.error_code or "UNKNOWN"
        category = _normalise_category(row.error_category)
        message = normalise_error_message(row.error_message)
        affected = row.affected_field or None

        # ── Auto-insert unknown code (INSERT OR IGNORE) ───────────────────
        if code not in known_codes:
            db.execute(
                sa_text("""
                    INSERT OR IGNORE INTO error_codes
                        (code, family_code, first_seen_at)
                    VALUES
                        (:code, 'SIN_CLASIFICAR', :first_seen_at)
                """),
                {"code": code, "first_seen_at": now_iso},
            )
            known_codes.add(code)

        # ── Resolve run_item_id ────────────────────────────────────────────
        run_item_row = db.execute(
            sa_text(
                "SELECT id FROM run_items "
                "WHERE run_id = :run_id AND sku_norm = :sku_norm",
            ),
            {"run_id": run_id, "sku_norm": row.sku_norm},
        ).fetchone()

        if run_item_row is None:
            continue  # SKU not in universe — skip silently

        # ── Insert item_error ─────────────────────────────────────────────
        db.execute(
            sa_text("""
                INSERT INTO item_errors
                    (run_item_id, error_code, error_category,
                     error_message, affected_field)
                VALUES
                    (:run_item_id, :error_code, :error_category,
                     :error_message, :affected_field)
            """),
            {
                "run_item_id": run_item_row[0],
                "error_code": code,
                "error_category": category,
                "error_message": message,
                "affected_field": affected,
            },
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _normalise_category(raw: str) -> str:
    """Normalise to ``ERROR`` or ``ADVERTENCIA`` (spec 2.2.3, EB-05)."""
    up = raw.strip().upper()
    if "ADVERTENCIA" in up or "WARNING" in up or "WARN" in up:
        return "ADVERTENCIA"
    return "ERROR"
