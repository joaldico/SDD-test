"""12-factor application settings (ADR-001).

All values are read from environment variables (or a .env file in development).
No secrets or credentials are ever hard-coded here.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

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

    # ── File staging (T-3.6 / T-3.7) ─────────────────────────────────────────
    # Directory where uploaded source files are persisted for later parsing.
    # Overridable via STAGING_DIR env var; created automatically if absent.
    #
    # IMPORTANT: Do NOT derive this from __file__ — when the package is installed
    # as a wheel, __file__ resolves inside site-packages (e.g.
    # /usr/local/lib/python3.12/site-packages/…), not the project tree.
    # The default below is the canonical path inside the Docker container.
    # For local development outside Docker, set STAGING_DIR in your .env file.
    staging_dir: Path = Path("/app/data/staging")


@lru_cache
def get_settings() -> Settings:
    """Return the cached singleton Settings instance."""
    return Settings()
