import logging
from pathlib import Path
from typing import Any, Dict, Optional
from sqlite3 import Connection

from .connection_pool import get_cache_db_path, is_cache_disabled

logger = logging.getLogger(__name__)

try:
    from samuraizer import _native
except ImportError:  # pragma: no cover - optional native module
    _native = None


def _resolve_db_path() -> Optional[Path]:
    db_path = get_cache_db_path()
    if db_path:
        try:
            return Path(db_path)
        except Exception:  # pragma: no cover - defensive
            logger.error("Invalid cache database path: %s", db_path)
    return None


def get_cached_entry(conn: Connection, file_path: str) -> Optional[Dict[str, Any]]:
    """Fetch a cached entry for ``file_path`` using the native backend."""

    if conn is None or is_cache_disabled():
        logger.debug("Cache lookup skipped for %s (cache disabled)", file_path)
        return None

    if _native is None:
        logger.debug("Native cache module unavailable; skipping lookup for %s", file_path)
        return None

    db_path = _resolve_db_path()
    if db_path is None:
        logger.debug("Cache lookup skipped for %s (no database path)", file_path)
        return None

    try:
        result = _native.cache_get_entry(str(db_path), file_path)
    except Exception as exc:  # pragma: no cover - conversion safety
        logger.error("Error retrieving cache entry for %s: %s", file_path, exc)
        return None

    if not result:
        logger.debug("No cache entry found for: %s", file_path)
        return None

    if not isinstance(result, dict):
        logger.error("Unexpected cache payload for %s: %r", file_path, result)
        return None

    logger.debug("Cache hit for file: %s", file_path)
    return result


def set_cached_entry(
    conn: Connection,
    file_path: str,
    file_hash: Optional[str],
    file_info: Dict[str, Any],
    size: int,
    mtime: float,
    synchronous: bool = False,
) -> None:
    """Persist ``file_info`` to the cache via the native backend."""

    if conn is None or is_cache_disabled():
        logger.debug("Skipping cache persist for %s (cache disabled)", file_path)
        return

    if _native is None:
        logger.debug("Native cache module unavailable; skipping persist for %s", file_path)
        return

    db_path = _resolve_db_path()
    if db_path is None:
        logger.debug("Skipping cache persist for %s (no database path)", file_path)
        return

    try:
        _native.cache_set_entry(
            str(db_path),
            file_path,
            file_hash,
            file_info,
            int(size),
            float(mtime),
            synchronous=synchronous,
        )
        logger.debug("Persisted cache entry for: %s", file_path)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Error queueing cache entry for %s: %s", file_path, exc)
