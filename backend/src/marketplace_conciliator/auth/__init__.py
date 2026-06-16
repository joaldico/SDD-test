"""Auth module — hexagonal boundary (ADR-001).

Responsibility: JWT RS256 issuance/verification (ADR-003), Argon2id password
hashing, refresh-token rotation with family-level revocation.

Ports defined here (T-2.x):
  - UserRepository (load user by email, persist)
  - TokenStore    (persist / revoke refresh tokens)

No imports from sibling domain modules (enforced by import-linter).
"""

from __future__ import annotations

__all__: list[str] = []
