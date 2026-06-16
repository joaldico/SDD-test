"""FastAPI application factory (ADR-001 — composition root).

Usage:
  uvicorn marketplace_conciliator.main:app --reload   (development)
  uvicorn marketplace_conciliator.main:app            (production, via Dockerfile CMD)

Composition root responsibilities (T-4.1):
  - Wires the TaskRunner adapter with MySQL-backed phase/failure callbacks.
  - Runs startup recovery (stale processing runs → failed) via lifespan.
  - Exposes ``get_task_runner()`` as an overridable FastAPI dependency.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from fastapi import FastAPI

from marketplace_conciliator.ingestion.router import router as ingestion_router
from marketplace_conciliator.platform.db.models.runs import ReconciliationRun
from marketplace_conciliator.platform.db.session import get_session_factory
from marketplace_conciliator.platform.health import router as health_router
from marketplace_conciliator.platform.recovery import recover_stale_runs
from marketplace_conciliator.reconciliation.task_runner import ThreadPoolTaskRunner
from marketplace_conciliator.settings import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TaskRunner singleton — wired with MySQL-backed callbacks
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _build_task_runner() -> ThreadPoolTaskRunner:
    """Construct the singleton TaskRunner wired with the platform DB callbacks.

    Called lazily on first use so that the DB session factory is only created
    when the application actually starts (respects 12-factor configuration).
    """
    factory = get_session_factory()

    def _on_phase(run_id: int, phase: str) -> None:
        db = factory()
        try:
            run = db.get(ReconciliationRun, run_id)
            if run is not None:
                run.phase = phase
                db.commit()
        except Exception:  # noqa: BLE001
            logger.warning("TaskRunner: on_phase failed for run %d", run_id)
        finally:
            db.close()

    def _on_failed(run_id: int, reason: str) -> None:
        db = factory()
        try:
            run = db.get(ReconciliationRun, run_id)
            if run is not None:
                run.status = "failed"
                run.failure_reason = reason[:255]
                run.phase = None
                db.commit()
        except Exception:  # noqa: BLE001
            logger.warning("TaskRunner: on_failed failed for run %d", run_id)
        finally:
            db.close()

    return ThreadPoolTaskRunner(on_phase=_on_phase, on_failed=_on_failed)


def get_task_runner() -> ThreadPoolTaskRunner:
    """FastAPI dependency — returns the singleton TaskRunner.

    Override via ``app.dependency_overrides[get_task_runner]`` in tests.
    """
    return _build_task_runner()


# ---------------------------------------------------------------------------
# Application lifespan — startup recovery + graceful shutdown
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage startup and shutdown tasks for the FastAPI application.

    Startup: recover any runs left in 'processing' by a previous server instance.
    Shutdown: drain the ThreadPoolExecutor gracefully.
    """
    # ── Startup ────────────────────────────────────────────────────────────
    settings = get_settings()
    if settings.database_url:
        try:
            factory = get_session_factory()
            db = factory()
            try:
                recovered = recover_stale_runs(db)
                if recovered:
                    logger.warning(
                        "Startup recovery complete: %d run(s) marked failed.",
                        recovered,
                    )
            finally:
                db.close()
        except Exception:
            logger.exception("Startup recovery failed — continuing without it.")

    yield

    # ── Shutdown ───────────────────────────────────────────────────────────
    if settings.database_url:
        try:
            _build_task_runner().shutdown(wait=True)
        except Exception:
            logger.exception("TaskRunner shutdown raised — ignoring.")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application.

    Called by tests (which may override dependencies before use) and by the
    module-level ``app`` singleton used by Uvicorn.
    """
    application = FastAPI(
        title="Marketplace Conciliator API",
        version="0.1.0",
        description=(
            "Backend API for the marketplace publication error conciliator. "
            "Hexagonal architecture — ADR-001."
        ),
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    application.include_router(health_router, prefix="/api/v1")
    application.include_router(ingestion_router, prefix="/api/v1")

    return application


# Module-level singleton consumed by Uvicorn: uvicorn marketplace_conciliator.main:app
app = create_app()
