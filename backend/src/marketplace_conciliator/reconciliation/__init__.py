"""Reconciliation module — hexagonal boundary (ADR-001).

Responsibility: the 5-stage Pandas pipeline (spec 3.4):
  Validating → Normalising → Deduplicating → Crossing → Persisting

Port defined here (T-4.x):
  - TaskRunner  (submit(run_id) / status(run_id), backed by BackgroundTasks/ThreadPool,
                 migratable to Celery without changing the port — ADR-002)

No imports from sibling domain modules (enforced by import-linter).
"""

from __future__ import annotations

__all__: list[str] = []
