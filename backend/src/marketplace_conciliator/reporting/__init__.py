"""Reporting module — hexagonal boundary (ADR-001).

Responsibility: three report views (families drill-down, SKU detail,
catalogue health), xlsx/csv export, run history (T-5.x).

No imports from sibling domain modules (enforced by import-linter).
"""

from __future__ import annotations

__all__: list[str] = []
