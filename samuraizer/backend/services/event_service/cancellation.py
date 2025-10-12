"""Cancellation primitives used to coordinate concurrent operations.

This module provides lightweight abstractions around ``threading.Event``
objects so that each long-running operation can be cancelled independently
without relying on any shared global state.  A ``CancellationTokenSource``
owns the underlying event while ``CancellationToken`` exposes a read-only
view that can safely be shared with worker threads.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Optional


class OperationCancelledError(RuntimeError):
    """Raised when an operation is cancelled via a :class:`CancellationToken`."""


@dataclass(frozen=True)
class CancellationToken:
    """Read-only cancellation signal shared with worker threads.

    Instances of this class should be created by
    :class:`CancellationTokenSource`.  Consumers can observe whether
    cancellation has been requested without being able to cancel the
    operation themselves.
    """

    _event: threading.Event

    def is_cancellation_requested(self) -> bool:
        """Return ``True`` if cancellation has been requested."""

        return self._event.is_set()

    def wait(self, timeout: Optional[float] = None) -> bool:
        """Block until cancellation is requested or ``timeout`` elapses."""

        return self._event.wait(timeout)

    def throw_if_cancellation_requested(self) -> None:
        """Raise :class:`OperationCancelledError` when cancelled."""

        if self.is_cancellation_requested():
            raise OperationCancelledError()


class CancellationTokenSource:
    """Factory and controller for :class:`CancellationToken` instances."""

    def __init__(self) -> None:
        self._event = threading.Event()
        self._token = CancellationToken(self._event)

    @property
    def token(self) -> CancellationToken:
        """Return the read-only cancellation token."""

        return self._token

    def cancel(self) -> None:
        """Signal cancellation to all observers."""

        self._event.set()

    def reset(self) -> None:
        """Clear the cancellation signal for re-use."""

        self._event.clear()

    def is_cancelled(self) -> bool:
        """Return ``True`` if cancellation has already been requested."""

        return self._event.is_set()


__all__ = [
    "CancellationToken",
    "CancellationTokenSource",
    "OperationCancelledError",
]

