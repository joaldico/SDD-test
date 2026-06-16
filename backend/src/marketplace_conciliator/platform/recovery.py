"""Startup recovery for stale reconciliation runs (T-4.1, RF-06).

Called once during application lifespan startup to handle server crashes
mid-pipeline.  Any run left in ``status='processing'`` by a previous
server instance is transitioned to ``status='failed'`` with a diagnostic
``failure_reason`` so the user understands the run must be restarted.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from marketplace_conciliator.platform.db.models.runs import ReconciliationRun

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_RESTART_REASON: str = "restart_during_processing"


def recover_stale_runs(db: Session) -> int:
    """Mark all ``processing`` runs as ``failed`` with the restart reason.

    Args:
        db: An active synchronous SQLAlchemy session.  Caller is responsible
            for closing it after this function returns.

    Returns:
        Number of runs recovered (0 when the server shut down cleanly).

    """
    stale: list[ReconciliationRun] = (
        db.query(ReconciliationRun)
        .filter(ReconciliationRun.status == "processing")
        .all()
    )

    for run in stale:
        run.status = "failed"
        run.failure_reason = _RESTART_REASON
        run.phase = None

    if stale:
        db.commit()
        logger.warning(
            "Startup recovery: marked %d stale run(s) as failed "
            "(failure_reason='%s')",
            len(stale),
            _RESTART_REASON,
        )

    return len(stale)
