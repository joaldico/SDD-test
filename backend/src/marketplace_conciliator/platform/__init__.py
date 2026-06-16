"""Platform module — FastAPI application shell (ADR-001).

Responsibility: FastAPI app factory, router wiring, cross-cutting middleware
(CORS, request-id, structured logging). The platform module is the only layer
allowed to import from sibling domain modules (it is the composition root).
"""

from __future__ import annotations

__all__: list[str] = []
