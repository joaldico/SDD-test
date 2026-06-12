"""Ingestion module — hexagonal boundary (ADR-001).

Responsibility: file parsing (CSV/TXT cascade-encoding, xlsx/xlsm read-only),
SKU normalisation (RN-01..RN-06), block localisation by title (EB-02/03/04).

Port defined here (T-3.x):
  - SourceParser  (parse file bytes → structured rows + metadata)

No imports from sibling domain modules (enforced by import-linter).
"""

from __future__ import annotations

__all__: list[str] = []
