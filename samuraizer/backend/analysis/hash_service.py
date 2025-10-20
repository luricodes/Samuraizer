"""Thin Python shim around the Rust hashing backend."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

try:  # pragma: no cover - the module is bundled with the wheel
    from samuraizer import _native
except ImportError:  # pragma: no cover - fall back to the Python implementation
    _native = None

_HASH_CHUNK_SIZE = 64 * 1024


class HashService:
    """Service facade that delegates hashing to the Rust backend."""

    @staticmethod
    def compute_file_hash(file_path: Path) -> Optional[str]:
        """Return the xxHash64 digest for ``file_path`` using the native engine."""

        if _native is not None:
            result = _native.compute_hash(str(file_path))
            if result is None:
                return None
            if not isinstance(result, str):  # pragma: no cover - native contract
                raise TypeError("Native compute_hash returned an unexpected payload")
            return result

        try:
            with file_path.open("rb") as handle:
                import hashlib

                hasher = hashlib.blake2b(digest_size=8)
                while True:
                    chunk = handle.read(_HASH_CHUNK_SIZE)
                    if not chunk:
                        break
                    hasher.update(chunk)
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise RuntimeError(f"Failed to hash {file_path}: {exc}") from exc

        return hasher.hexdigest()


compute_file_hash = HashService.compute_file_hash
