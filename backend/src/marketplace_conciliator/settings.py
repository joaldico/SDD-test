"""12-factor application settings (ADR-001).

All values are read from environment variables (or a .env file in development).
No secrets or credentials are ever hard-coded here.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings resolved from the environment (12-factor, ADR-001)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    app_env: str = "development"
    debug: bool = False

    # ── Database ──────────────────────────────────────────────────────────────
    # Full SQLAlchemy URL, e.g. "mysql+aiomysql://user:pass@host/db"
    # Left empty so the health probe reports "unconfigured" until T-1.4 wires it.
    database_url: str = ""


@lru_cache
def get_settings() -> Settings:
    """Return the cached singleton Settings instance."""
    return Settings()
