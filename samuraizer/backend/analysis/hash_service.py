"""Thin Python shim around the Rust hashing backend."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

try:  # pragma: no cover - the module is bundled with the wheel
    from samuraizer import _native
except ImportError as exc:  # pragma: no cover - defensive guard for type checkers
    raise RuntimeError(
        "The samuraizer native extension is not available. "
        "Build it with `maturin develop` or install the wheel."
    ) from exc


class HashService:
    """Service facade that delegates hashing to the Rust backend."""

    @staticmethod
    def compute_file_hash(file_path: Path) -> Optional[str]:
        """Return the xxHash64 digest for ``file_path`` using the native engine."""

        result = _native.compute_hash(str(file_path))
        if result is None:
            return None
        if not isinstance(result, str):  # pragma: no cover - native contract
            raise TypeError("Native compute_hash returned an unexpected payload")
        return result


compute_file_hash = HashService.compute_file_hash