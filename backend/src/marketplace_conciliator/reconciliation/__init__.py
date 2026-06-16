"""Reconciliation module — hexagonal boundary (ADR-001).

Responsibility: the 5-stage Pandas pipeline (spec 3.4):
  Validating → Normalising → Deduplicating → Crossing → Persisting

Port defined here (T-4.1):
  - TaskRunnerPort  — abstract interface (Protocol)
  - ThreadPoolTaskRunner — default adapter; semaphore-protected ThreadPoolExecutor

Migration path (ADR-002): swapping the adapter (e.g. to Celery) only requires
updating the composition root (``main.py``); no port change needed.

Hexagonal constraint (ADR-001):
  No imports from ``platform`` or sibling domain modules (enforced by import-linter).
"""

from __future__ import annotations

from marketplace_conciliator.reconciliation.ports import TaskRunnerPort
from marketplace_conciliator.reconciliation.task_runner import (
    MAX_CONCURRENT_JOBS,
    ThreadPoolTaskRunner,
)

__all__: list[str] = [
    "MAX_CONCURRENT_JOBS",
    "TaskRunnerPort",
    "ThreadPoolTaskRunner",
]
