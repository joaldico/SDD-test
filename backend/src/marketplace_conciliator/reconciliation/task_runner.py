"""ThreadPool-based TaskRunner adapter (T-4.1, ADR-002).

Implements ``TaskRunnerPort`` backed by a ``ThreadPoolExecutor``:

  * Semaphore (``MAX_CONCURRENT_JOBS = 2``) caps simultaneous executions to
    protect server memory (RF-06).  Excess jobs block on the semaphore inside
    their thread-pool slot — the ASGI event loop is NEVER blocked.

  * Phase callbacks (``on_phase``, ``on_failed``) are injected at construction
    time.  The composition root (``main.py``) wires them to the MySQL adapter;
    tests pass spy callables.  This keeps the reconciliation module free of
    platform imports (ADR-001 / import-linter).

  * Pool size: ``_POOL_SIZE = MAX_CONCURRENT_JOBS + 4`` so that threads queued
    waiting for the semaphore still have a pool slot and cannot deadlock.

Phase lifecycle managed by this adapter:

  submitted  →  on_phase(run_id, "initializing")   (before calling work_fn)
  work_fn raises  →  on_failed(run_id, str(exc))
  work_fn succeeds  →  caller's work_fn is responsible for marking completed
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

MAX_CONCURRENT_JOBS: int = 2
_POOL_SIZE: int = MAX_CONCURRENT_JOBS + 4


class ThreadPoolTaskRunner:
    """Non-blocking TaskRunner backed by ``ThreadPoolExecutor`` + ``threading.Semaphore``.

    Args:
        on_phase: Called as ``on_phase(run_id, phase_label)`` right before
            ``work_fn`` is invoked.  Provided by the composition root.
        on_failed: Called as ``on_failed(run_id, reason)`` if ``work_fn``
            raises an unhandled exception.  Provided by the composition root.

    """

    def __init__(
        self,
        on_phase: Callable[[int, str], None],
        on_failed: Callable[[int, str], None],
    ) -> None:
        """Initialise the runner with phase/failure callbacks."""
        self._on_phase = on_phase
        self._on_failed = on_failed
        self._semaphore = threading.Semaphore(MAX_CONCURRENT_JOBS)
        self._executor = ThreadPoolExecutor(
            max_workers=_POOL_SIZE,
            thread_name_prefix="task_runner",
        )
        self._active: int = 0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public port interface
    # ------------------------------------------------------------------

    def submit(self, run_id: int, work_fn: Callable[[int], None]) -> Future[None]:
        """Schedule ``work_fn(run_id)`` for async execution.

        Returns a ``Future`` immediately; never blocks the caller.
        """
        return self._executor.submit(self._guarded_run, run_id, work_fn)

    def active_count(self) -> int:
        """Return the number of ``work_fn`` calls currently executing."""
        with self._lock:
            return self._active

    def shutdown(self, *, wait: bool = True) -> None:
        """Drain the thread pool gracefully.  Called at application teardown."""
        self._executor.shutdown(wait=wait)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _guarded_run(self, run_id: int, work_fn: Callable[[int], None]) -> None:
        """Acquire semaphore, fire phase callback, run work_fn, handle errors."""
        self._semaphore.acquire()
        try:
            with self._lock:
                self._active += 1

            self._safe_call(self._on_phase, run_id, "initializing")

            try:
                work_fn(run_id)
            except Exception as exc:
                logger.exception("TaskRunner: job %d raised", run_id)
                self._safe_call(self._on_failed, run_id, str(exc))
            finally:
                with self._lock:
                    self._active -= 1
        finally:
            self._semaphore.release()

    @staticmethod
    def _safe_call(fn: Callable[[int, str], None], run_id: int, arg: str) -> None:
        """Invoke callback; swallow and log any exception so the job never crashes."""
        try:
            fn(run_id, arg)
        except Exception:  # noqa: BLE001
            logger.warning(
                "TaskRunner: callback %s(run_id=%d, %r) raised — ignoring",
                fn.__name__,
                run_id,
                arg,
            )
