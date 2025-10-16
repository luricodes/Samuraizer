"""Centralized runtime cache state management."""

from __future__ import annotations

import logging
import threading
from typing import Callable, List


logger = logging.getLogger(__name__)


class CacheStateManager:
    """Runtime manager for the cache enabled/disabled state.

    This component centralises cache state decisions that can originate from
    multiple places (CLI flags, persisted GUI settings, runtime toggles) and
    provides a lightweight observer mechanism for interested components such as
    the connection pool.
    """

    _disabled: bool = False
    _lock = threading.RLock()
    _listeners: List[Callable[[bool], None]] = []

    @classmethod
    def is_disabled(cls) -> bool:
        """Return whether the cache is currently disabled."""

        with cls._lock:
            return cls._disabled

    @classmethod
    def set_disabled(cls, disabled: bool) -> None:
        """Update cache disabled state and notify listeners if it changed."""

        with cls._lock:
            if cls._disabled == disabled:
                return

            cls._disabled = disabled
            listeners = list(cls._listeners)

        state = "disabled" if disabled else "enabled"
        logger.debug("Cache state changed: %s", state)

        for listener in listeners:
            try:
                listener(disabled)
            except Exception:  # pragma: no cover - defensive logging
                logger.exception("Cache state listener failed")

    @classmethod
    def register_listener(
        cls,
        listener: Callable[[bool], None],
        *,
        notify_immediately: bool = True,
    ) -> None:
        """Register a listener that is notified when the state changes."""

        with cls._lock:
            if listener in cls._listeners:
                return
            cls._listeners.append(listener)
            disabled = cls._disabled

        if notify_immediately:
            try:
                listener(disabled)
            except Exception:  # pragma: no cover - defensive logging
                logger.exception("Cache state listener failed during registration")


__all__ = ["CacheStateManager"]

