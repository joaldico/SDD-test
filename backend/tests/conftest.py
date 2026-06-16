"""Shared pytest configuration for backend tests."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from marketplace_conciliator.main import _build_task_runner
from marketplace_conciliator.platform.db.session import _get_session_factory
from marketplace_conciliator.settings import get_settings

# Valid in-memory SQLite URL for code paths that resolve Settings.database_url
# (e.g. get_db_factory → get_session_factory during POST /process).
# Integration/BDD tests still override get_db / get_db_factory with their own
# StaticPool engines; this prevents ArgumentError on an empty DATABASE_URL.
_TEST_DATABASE_URL = "sqlite://"
_TEST_STAGING_DIR = Path(tempfile.gettempdir()) / "conciliador_pytest_staging"


@pytest.fixture(scope="session", autouse=True)
def _configure_test_database_url() -> None:
    """Inject test-safe DATABASE_URL and STAGING_DIR for the whole session."""
    os.environ["DATABASE_URL"] = _TEST_DATABASE_URL
    os.environ["STAGING_DIR"] = str(_TEST_STAGING_DIR)
    _TEST_STAGING_DIR.mkdir(parents=True, exist_ok=True)
    get_settings.cache_clear()
    _get_session_factory.cache_clear()
    _build_task_runner.cache_clear()
