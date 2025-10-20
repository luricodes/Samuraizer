"""Binary classification implemented via the Rust backend."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional, Tuple

try:  # pragma: no cover - ships with the wheel
    from samuraizer import _native
except ImportError:  # pragma: no cover - allow running without the native extension
    _native = None

logger = logging.getLogger(__name__)


def _stat_key(file_path: Path) -> Optional[Tuple[str, int, int]]:
    try:
        stat_result = file_path.stat()
    except OSError as exc:
        logger.warning("Failed to stat %s: %s", file_path, exc)
        return None

    mtime_ns = getattr(
        stat_result,
        "st_mtime_ns",
        int(stat_result.st_mtime * 1_000_000_000),
    )
    return (str(file_path.resolve()), stat_result.st_size, int(mtime_ns))


@lru_cache(maxsize=4096)
def _classify_cached(path_str: str, size: int, mtime_ns: int) -> bool:
    return _classify_uncached(path_str)


def _classify_uncached(path_str: str) -> bool:
    if _native is not None:
        try:
            result = _native.classify_binary(path_str)
        except Exception as exc:  # pragma: no cover - native errors surface rarely
            raise RuntimeError(f"Failed to classify {path_str}: {exc}") from exc
        return bool(result)

    try:
        with Path(path_str).open("rb") as handle:
            sample = handle.read(4096)
    except OSError as exc:
        logger.warning("Failed to open %s for binary detection: %s", path_str, exc)
        return True

    if not sample:
        return False

    if b"\x00" in sample:
        return True

    text_threshold = sum(1 for byte in sample if 32 <= byte <= 126 or byte in (9, 10, 13))
    return (text_threshold / len(sample)) < 0.7


def is_binary(file_path: Path) -> bool:
    """Return ``True`` if ``file_path`` should be treated as binary."""

    key = _stat_key(file_path)
    if key is None:
        return _classify_uncached(str(file_path))
    path_str, size, mtime_ns = key
    return _classify_cached(path_str, size, mtime_ns)
