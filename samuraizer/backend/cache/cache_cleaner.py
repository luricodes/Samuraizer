# samuraizer/backend/cache/cache_cleaner.py

import logging
from pathlib import Path
from typing import Any, Dict, Set
import sqlite3
import time

from samuraizer.backend.services.config_services import (
    CACHE_DB_FILE,
    get_default_analysis_settings,
    get_default_cache_settings,
)
from .connection_pool import (
    close_all_connections,
    get_connection_context,
    initialize_connection_pool,
    is_cache_disabled,
)

logger = logging.getLogger(__name__)

def check_and_vacuum_if_needed(db_path: Path) -> None:
    """Check if cache size exceeds max limit and vacuum if needed."""
    try:
        cache_settings = get_default_cache_settings()
        max_cache_size = int(cache_settings.get("size_limit_mb", 1000) or 1000)
        
        if db_path.exists():
            # Calculate total size including WAL and SHM files
            size_mb = db_path.stat().st_size / (1024 * 1024)  # Main DB file
            
            # Check WAL and SHM files
            wal_path = db_path.with_suffix('.db-wal')
            shm_path = db_path.with_suffix('.db-shm')
            
            if wal_path.exists():
                size_mb += wal_path.stat().st_size / (1024 * 1024)
            if shm_path.exists():
                size_mb += shm_path.stat().st_size / (1024 * 1024)
            
            if size_mb > max_cache_size:
                logger.info(f"Cache size ({size_mb:.2f}MB) exceeds maximum ({max_cache_size}MB). Running cleanup...")
                
                # First, close all existing connections to ensure exclusive access
                close_all_connections()
                
                # Use a direct connection for cleanup
                with sqlite3.connect(str(db_path)) as conn:
                    try:
                        # Temporarily disable WAL mode for cleanup
                        conn.execute("PRAGMA journal_mode = DELETE;")
                        
                        # Get total number of entries
                        cursor = conn.execute("SELECT COUNT(*) FROM cache")
                        total_entries = cursor.fetchone()[0]
                        
                        # Calculate how many entries to keep (aim for 75% of max size)
                        target_entries = int(total_entries * (max_cache_size * 0.75) / size_mb)
                        
                        # Delete oldest entries based on mtime
                        conn.execute("""
                            DELETE FROM cache 
                            WHERE file_path IN (
                                SELECT file_path 
                                FROM cache 
                                ORDER BY mtime ASC 
                                LIMIT ?
                            )
                        """, (total_entries - target_entries,))
                        
                        # Commit the deletions
                        conn.commit()
                        
                        # Perform VACUUM
                        conn.execute("VACUUM;")
                        logger.info("VACUUM completed successfully.")
                        
                        # Re-enable WAL mode
                        conn.execute("PRAGMA journal_mode = WAL;")
                        conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                        
                    except sqlite3.Error as e:
                        logger.error(f"Error during cleanup: {e}")
                        # Ensure WAL mode is re-enabled even if cleanup fails
                        try:
                            conn.execute("PRAGMA journal_mode = WAL;")
                        except:
                            pass
                
                # Reinitialize the connection pool
                analysis_settings = get_default_analysis_settings()
                thread_count = int(analysis_settings.get("threads", 4) or 4)
                initialize_connection_pool(
                    str(db_path),
                    thread_count,
                    force_disable_cache=is_cache_disabled(),
                )
                
                # Log new size after cleanup
                new_size_mb = db_path.stat().st_size / (1024 * 1024)
                if wal_path.exists():
                    new_size_mb += wal_path.stat().st_size / (1024 * 1024)
                if shm_path.exists():
                    new_size_mb += shm_path.stat().st_size / (1024 * 1024)
                logger.info(f"New cache size after cleanup: {new_size_mb:.2f}MB")
                
    except Exception as e:
        logger.error(f"Error checking cache size: {e}")

def clean_cache(root_dir: Path) -> None:
    # Check if cache is disabled
    with get_connection_context() as conn:
        if conn is None:
            logger.debug("Cache cleanup skipped (caching disabled)")
            return

        try:
            included_files: Set[str] = set()
            for p in root_dir.rglob("*"):
                if p.is_file():
                    included_files.add(str(p.resolve()))
        except Exception as e:
            logger.error(f"Error when scanning the root directory {root_dir}: {e}")
            return

        try:
            cursor = conn.execute("SELECT file_path FROM cache")
            cached_files = {row[0] for row in cursor.fetchall()}
        except sqlite3.Error as e:
            logger.error(
                f"Error when retrieving the cached file paths: {e}"
            )
            return

        files_to_remove = cached_files - included_files

        if files_to_remove:
            try:
                conn.executemany(
                    "DELETE FROM cache WHERE file_path = ?",
                    ((fp,) for fp in files_to_remove),
                )
                conn.commit()

                message = (
                    f"Cache cleared. {len(files_to_remove)} Entries removed."
                )
                logger.info(message)
            except sqlite3.Error as e:
                logger.error(f"Error when clearing the cache: {e}")
        else:
            logger.info(
                "No cache clean-up required. All entries are up to date."
            )

        # Get cache path from settings
        cache_settings = get_default_cache_settings()
        cache_path_value = cache_settings.get("path", "~/.cache/samurai")
        cache_path = Path(str(cache_path_value)).expanduser()
        
        # Check cache size and vacuum if needed
        db_path = cache_path / CACHE_DB_FILE
        check_and_vacuum_if_needed(db_path)
