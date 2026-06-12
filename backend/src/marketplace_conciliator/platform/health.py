"""Health probe endpoint — GET /api/v1/health (plan 3.7).

The DB liveness check is injected as a FastAPI dependency so that:
  - Tests override it without touching the router code.
  - T-1.4 replaces it with a real MySQL ping without changing the contract.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter(tags=["platform"])


async def check_db_health() -> str:
    """DB liveness probe — port to be replaced by the MySQL adapter in T-1.4.

    Returns "unconfigured" until a real DB connection pool is wired in.
    Override via ``app.dependency_overrides[check_db_health]`` in tests.
    """
    return "unconfigured"


class HealthResponse(BaseModel):
    """Response schema for GET /health."""

    status: str
    db: str


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness / readiness probe",
    description=(
        "Returns the application status and the result of the DB liveness probe. "
        "Used by Docker healthchecks and the smoke test in CI/CD (plan 3.8.2/3.8.3)."
    ),
)
async def get_health(
    db: Annotated[str, Depends(check_db_health)],
) -> HealthResponse:
    """Return application and database health."""
    return HealthResponse(status="ok", db=db)
