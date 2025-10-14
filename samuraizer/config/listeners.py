from __future__ import annotations

import weakref
from typing import Any, Callable, Optional


class _Listener:
    """Wrapper that stores callbacks via weak references when possible."""

    __slots__ = ("_ref", "_strong")

    def __init__(self, callback: Callable[[], None]) -> None:
        self._ref: Any
        try:
            if hasattr(callback, "__self__") and hasattr(callback, "__func__"):
                self._ref = weakref.WeakMethod(callback)  # type: ignore[arg-type]
            else:
                self._ref = weakref.ref(callback)
            self._strong: Optional[Callable[[], None]] = None
        except TypeError:
            # Fallback for callables that do not support weak references.
            self._ref = None
            self._strong = callback

    def get(self) -> Optional[Callable[[], None]]:
        if self._ref is None:
            return self._strong
        return self._ref()

    def matches(self, callback: Callable[[], None]) -> bool:
        if self._ref is None:
            return self._strong is callback
        target = self._ref()
        return target is callback


__all__ = ["_Listener"]
