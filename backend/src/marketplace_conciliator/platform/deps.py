"""FastAPI shared dependencies.

AUTH BYPASS (M2 deferred):
``get_current_user`` returns a hard-coded dummy admin so that M3-M5 endpoints
can be developed without the full ADR-003 auth stack.  Replace this with the
real JWT-verification dependency when M2 is implemented before M6.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, HTTPException

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True)
class CurrentUser:
    """Minimal user context passed by the auth dependency to route handlers."""

    id: int
    email: str
    role: str


# ---------------------------------------------------------------------------
# Dummy admin - satisfies FK references during M3-M5 development.
# This constant must match the user inserted by scripts/seed_dummy_user.py.
# ---------------------------------------------------------------------------
DUMMY_USER = CurrentUser(id=1, email="dev@local.test", role="admin")


def get_current_user() -> CurrentUser:
    """Return a static admin user (auth bypass active while M2 is deferred).

    Replace the body of this function with the real JWT-verification logic
    (T-2.2) once M2 is implemented.
    """
    return DUMMY_USER


def require_role(*allowed_roles: str) -> Callable[..., CurrentUser]:
    """FastAPI dependency factory — restrict endpoint to given roles (T-5.6 / RF-14)."""

    def _check(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions for this operation.",
            )
        return current_user

    return _check
