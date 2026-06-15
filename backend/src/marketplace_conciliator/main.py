"""FastAPI application factory (ADR-001 — composition root).

Usage:
  uvicorn marketplace_conciliator.main:app --reload   (development)
  uvicorn marketplace_conciliator.main:app            (production, via Dockerfile CMD)
"""

from __future__ import annotations

from fastapi import FastAPI

from marketplace_conciliator.ingestion.router import router as ingestion_router
from marketplace_conciliator.platform.health import router as health_router


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
    )

    application.include_router(health_router, prefix="/api/v1")
    application.include_router(ingestion_router, prefix="/api/v1")

    return application


# Module-level singleton consumed by Uvicorn: uvicorn marketplace_conciliator.main:app
app = create_app()
