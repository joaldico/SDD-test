#!/usr/bin/env python3
"""Insert the auth-bypass dummy admin user into the database.

Run once after applying Alembic migrations:

    python scripts/seed_dummy_user.py

The user inserted here (id=1, email='dev@local.test', role='admin') matches
the constant defined in ``marketplace_conciliator.platform.deps.DUMMY_USER``
and satisfies the FK constraints on ``reconciliation_runs.created_by`` and
``source_files`` during the M3–M5 development phase.

Remove or gate this script behind an env-check before going to production.
"""

from __future__ import annotations

import sys

import sqlalchemy as sa

# ---------------------------------------------------------------------------
# Bootstrap path so this script can be run from the repo root without install
# ---------------------------------------------------------------------------
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from marketplace_conciliator.settings import get_settings  # noqa: E402

_DUMMY_EMAIL = "dev@local.test"
_DUMMY_HASH = (
    # Argon2id hash of the literal string "devpassword" — never used in prod.
    "$argon2id$v=19$m=65536,t=3,p=4"
    "$AAAAAAAAAAAAAAAAAAAAAA"
    "$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
)


def main() -> None:
    settings = get_settings()
    if not settings.database_url:
        print("ERROR: DATABASE_URL is not configured. Aborting.", file=sys.stderr)
        sys.exit(1)

    # Use synchronous URL for this one-shot script (avoids async boilerplate).
    sync_url = settings.database_url.replace(
        "mysql+aiomysql://", "mysql+pymysql://"
    ).replace(
        "mysql+asyncmy://", "mysql+pymysql://"
    )

    engine = sa.create_engine(sync_url, echo=False)
    with engine.begin() as conn:
        existing = conn.execute(
            sa.text("SELECT id FROM users WHERE email = :email"),
            {"email": _DUMMY_EMAIL},
        ).fetchone()

        if existing:
            print(f"Dummy user '{_DUMMY_EMAIL}' already exists (id={existing[0]}). Skipping.")
            return

        conn.execute(
            sa.text(
                "INSERT INTO users (email, password_hash, role, created_at) "
                "VALUES (:email, :hash, 'admin', NOW(6))"
            ),
            {"email": _DUMMY_EMAIL, "hash": _DUMMY_HASH},
        )

    print(f"Dummy user '{_DUMMY_EMAIL}' inserted successfully.")


if __name__ == "__main__":
    main()
