import json
import logging
from typing import Dict, Any, Optional
from sqlite3 import Connection

from .connection_pool import is_cache_disabled, queue_write

logger = logging.getLogger(__name__)

def get_cached_entry(conn: Connection, file_path: str) -> Optional[Dict[str, Any]]:
    """
    Get a cached entry for a file path.

    Args:
        conn (Connection): SQLite connection
        file_path (str): Path to the file

    Returns:
        Optional[Dict[str, Any]]: Cached entry if found, None otherwise
    """
    # Skip if connection is None (cache disabled)
    if conn is None:
        logger.debug(f"Cache lookup skipped for {file_path} (cache disabled)")
        return None

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT file_hash, file_info, size, mtime
            FROM cache WHERE file_path = ?
            """,
            (file_path,),
        )

        result = cursor.fetchone()
        if result:
            file_hash, file_info_json, size, mtime = result
            try:
                file_info = json.loads(file_info_json)
                logger.debug(f"Cache hit for file: {file_path}")
                return {
                    "file_hash": file_hash,
                    "file_info": file_info,
                    "size": size,
                    "mtime": mtime
                }
            except json.JSONDecodeError:
                logger.error(f"Failed to decode cached file info for {file_path}")
                return None
        logger.debug(f"No cache entry found for: {file_path}")
        return None
        
    except Exception as e:
        logger.error(f"Error retrieving cache entry: {e}")
        return None

def set_cached_entry(
    conn: Connection,
    file_path: str,
    file_hash: Optional[str],
    file_info: Dict[str, Any],
    size: int,
    mtime: float,
    synchronous: bool = False,
) -> None:
    """
    Queue a cache entry for batch processing.

    Args:
        conn (Connection): SQLite connection (not used in batched operation)
        file_path (str): Path to the file
        file_hash (Optional[str]): xxHash of the file
        file_info (Dict[str, Any]): File information
        size (int): File size
        mtime (float): File modification time
        synchronous (bool): Whether to block until the entry is persisted
    """
    try:
        # Convert file_info to JSON string
        file_info_json = json.dumps(file_info)

        # Create entry tuple for batch processing
        entry = (file_path, file_hash, file_info_json, size, mtime)

        if is_cache_disabled():
            logger.debug("Skipping cache persist for %s (cache disabled)", file_path)
            return

        # Queue the write operation
        queue_write(entry, synchronous=synchronous)
        logger.debug(f"Queued cache entry for batch processing: {file_path}")
        
    except Exception as e:
        logger.error(f"Error queueing cache entry: {e}")
