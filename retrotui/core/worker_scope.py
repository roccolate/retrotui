"""Owned background worker lifecycle primitives.

A ``WorkerScope`` gives one component explicit ownership of every thread it
starts. Shutdown closes the scope, signals cooperative cancellation, prevents
new workers, and performs a bounded join. Workers that cannot be interrupted
must still consult ``cancel_event`` before publishing results back to their
owner.
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any


LOGGER = logging.getLogger(__name__)


class WorkerScope:
    """Track worker threads owned by one runtime component."""

    def __init__(self, name: str, *, join_timeout: float = 0.25):
        self.name = str(name or "worker-scope")
        self.join_timeout = max(0.0, float(join_timeout))
        self._lock = threading.RLock()
        self._cancel_event = threading.Event()
        self._threads: set[threading.Thread] = set()
        self._closed = False

    @property
    def cancel_event(self) -> threading.Event:
        return self._cancel_event

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    @property
    def active_count(self) -> int:
        with self._lock:
            return sum(thread.is_alive() for thread in self._threads)

    def start(
        self,
        target: Callable[..., Any],
        *args: Any,
        name: str | None = None,
        daemon: bool = True,
        **kwargs: Any,
    ) -> threading.Thread | None:
        """Start and track a worker, passing ``cancel_event`` first."""
        if not callable(target):
            raise TypeError("worker target must be callable")

        with self._lock:
            if self._closed:
                return None

            def _runner() -> None:
                current = threading.current_thread()
                try:
                    target(self._cancel_event, *args, **kwargs)
                except Exception:  # Worker boundary: isolate and retain diagnostics.
                    LOGGER.exception("Unhandled worker failure in scope %s", self.name)
                finally:
                    with self._lock:
                        self._threads.discard(current)

            thread = threading.Thread(
                target=_runner,
                name=name or f"retrotui-{self.name}",
                daemon=daemon,
            )
            self._threads.add(thread)
            try:
                thread.start()
            except Exception:
                self._threads.discard(thread)
                raise
            return thread

    def cancel(self) -> None:
        """Close the scope and signal cooperative cancellation once."""
        with self._lock:
            self._closed = True
            self._cancel_event.set()

    def join(self, timeout: float | None = None) -> tuple[threading.Thread, ...]:
        """Join owned workers within one shared deadline; return survivors."""
        wait_for = self.join_timeout if timeout is None else max(0.0, float(timeout))
        deadline = time.monotonic() + wait_for
        current = threading.current_thread()
        with self._lock:
            threads = tuple(self._threads)

        for thread in threads:
            if thread is current or not thread.is_alive():
                continue
            remaining = max(0.0, deadline - time.monotonic())
            if remaining <= 0.0:
                break
            thread.join(timeout=remaining)

        with self._lock:
            return tuple(
                thread
                for thread in self._threads
                if thread is not current and thread.is_alive()
            )

    def shutdown(
        self,
        timeout: float | None = None,
        *,
        require_stopped: bool = False,
    ) -> bool:
        """Cancel and bounded-join workers.

        ``require_stopped=False`` is appropriate for read-only window workers:
        the owner is logically closed immediately and late results are rejected.
        Global side-effecting operations use ``require_stopped=True`` so the app
        can report an incomplete physical shutdown.
        """
        self.cancel()
        survivors = self.join(timeout=timeout)
        if survivors:
            LOGGER.warning(
                "Worker scope %s still has %d live thread(s) after shutdown: %s",
                self.name,
                len(survivors),
                ", ".join(thread.name for thread in survivors),
            )
        return not survivors if require_stopped else True
