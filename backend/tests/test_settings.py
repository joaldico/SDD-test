"""Unit tests for the 12-factor Settings — T-1.3."""

from __future__ import annotations

import os

from marketplace_conciliator.settings import Settings, get_settings


def test_settings_default_app_env() -> None:
    assert Settings().app_env == "development"


def test_settings_default_debug_is_false() -> None:
    assert Settings().debug is False


def test_settings_default_database_url_is_empty() -> None:
    """database_url is empty until T-1.4 wires the real MySQL connection string."""
    saved = os.environ.pop("DATABASE_URL", None)
    try:
        assert Settings().database_url == ""
    finally:
        if saved is not None:
            os.environ["DATABASE_URL"] = saved


def test_settings_override_via_env() -> None:
    """Environment variables are picked up (12-factor)."""
    os.environ["APP_ENV"] = "production"
    os.environ["DEBUG"] = "true"
    try:
        s = Settings()
        assert s.app_env == "production"
        assert s.debug is True
    finally:
        os.environ.pop("APP_ENV", None)
        os.environ.pop("DEBUG", None)


def test_get_settings_returns_settings_instance() -> None:
    get_settings.cache_clear()
    s = get_settings()
    assert isinstance(s, Settings)


def test_get_settings_is_cached() -> None:
    get_settings.cache_clear()
    assert get_settings() is get_settings()
