"""Integration tests for GET /api/v1/health — T-1.3 DoD gate.

TDD: these tests are written before the implementation.
They verify the contract from plan 3.7:
  GET /health → 200 {"status": str, "db": str}
"""

from __future__ import annotations

from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from marketplace_conciliator.main import create_app
from marketplace_conciliator.platform.health import check_db_health


@pytest.fixture
def client_with_db_ok() -> TestClient:
    """TestClient with the DB health probe overridden to simulate a healthy DB."""
    app = create_app()
    app.dependency_overrides[check_db_health] = lambda: "ok"
    return TestClient(app)


def test_health_returns_200(client_with_db_ok: TestClient) -> None:
    response = client_with_db_ok.get("/api/v1/health")
    assert response.status_code == HTTPStatus.OK


def test_health_response_has_status_ok(client_with_db_ok: TestClient) -> None:
    body = client_with_db_ok.get("/api/v1/health").json()
    assert body["status"] == "ok"


def test_health_response_has_db_ok(client_with_db_ok: TestClient) -> None:
    """DB field is present and reports the probe result (overridden to 'ok')."""
    body = client_with_db_ok.get("/api/v1/health").json()
    assert body["db"] == "ok"


def test_health_response_shape_is_exact(client_with_db_ok: TestClient) -> None:
    """Response has exactly {status, db} — no extra or missing keys."""
    body = client_with_db_ok.get("/api/v1/health").json()
    assert set(body.keys()) == {"status", "db"}


def test_health_db_unconfigured_without_real_db() -> None:
    """Without a DB adapter, the probe returns 'unconfigured' but still 200."""
    client = TestClient(create_app())
    response = client.get("/api/v1/health")
    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "unconfigured"
