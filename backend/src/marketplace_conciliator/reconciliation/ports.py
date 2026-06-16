"""TaskRunner port — hexagonal boundary for async job execution (ADR-002, T-4.1).

Defines the abstract interface that any TaskRunner adapter must satisfy.
The ``ThreadPoolTaskRunner`` adapter is the default implementation (T-4.1).
Migrating to Celery later only requires swapping the adapter, not the port
(ADR-002: isolation via protocol).

Hexagonal constraint (ADR-001):
  This module intentionally has NO imports from ``platform`` or other domain
  modules.  All infrastructure dependencies are injected at the composition
  root (``main.py``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Callable


@runtime_checkable
class TaskRunnerPort(Protocol):
    """Port for scheduling background reconciliation jobs.

    Implementations must be non-blocking: ``submit()`` returns immediately
    and the ``work_fn`` executes in a background execution context.

    Concurrency control (e.g. semaphore) is implementation-specific.
    """

    def submit(self, run_id: int, work_fn: Callable[[int], None]) -> object:
        """Schedule ``work_fn(run_id)`` for background execution.

        Must return immediately (non-blocking).
        Returns an opaque handle (e.g. ``Future``) that callers may ignore.
        """
        ...

    def active_count(self) -> int:
        """Return the number of ``work_fn`` calls currently executing."""
        ...

    def shutdown(self, *, wait: bool = True) -> None:
        """Release executor resources.  Called once at application teardown."""
        ...
