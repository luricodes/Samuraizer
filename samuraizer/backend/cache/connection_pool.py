# samuraizer/backend/cache/connection_pool.py

import atexit
import logging
import queue
import sqlite3
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, Optional, List, Tuple
from collections import deque
import time

from PyQt6.QtCore import QSettings

logger = logging.getLogger(__name__)

def calculate_pool_size(thread_count: int) -> int:
    """
    Calculate optimal connection pool size based on thread count.
    
    Args:
        thread_count: Number of worker threads
        
    Returns:
        Optimal pool size considering SQLite's single-writer limitation
    """
    # Keep pool size small due to SQLite's single-writer limitation
    # One dedicated writer connection, rest for reads
    return min(3, thread_count)  # Maximum 3 connections (1 writer, 2 readers)

class ConnectionPool:
    """Management of a pool of SQLite connections with write queue"""

    _instance_lock = threading.Lock()
    _instance: Optional['ConnectionPool'] = None
    _current_settings: Dict[str, Any] = {}
    _initialized = False
    _write_queue = deque()
    _write_lock = threading.Lock()
    _write_batch_size = 100  # Number of writes to batch together
    _write_batch_timeout = 1.0  # Maximum time to wait for batch to fill

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super(ConnectionPool, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str, thread_count: int, force_disable_cache: bool = False) -> None:
        pool_size = calculate_pool_size(thread_count)
        
        if self._initialized and self._current_settings and all(
            self._current_settings.get(key) == value 
            for key, value in {
                'db_path': db_path,
                'thread_count': thread_count,
                'force_disable_cache': force_disable_cache,
            }.items()
        ):
            return

        settings = QSettings()
        current_cache_disabled = settings.value("settings/disable_cache", False, bool)
        
        new_settings = {
            'db_path': db_path,
            'thread_count': thread_count,
            'force_disable_cache': force_disable_cache,
            'gui_cache_disabled': current_cache_disabled
        }
        
        if self._initialized:
            self._cleanup()

        self._current_settings = new_settings
        self.db_path = db_path
        self.pool_size = pool_size
        self._cache_disabled = force_disable_cache or current_cache_disabled

        if self._cache_disabled:
            logger.warning("Cache operations will be skipped. This may impact performance.")
            self.pool = None
            self._initialized = True
            return

        logger.debug(f"Cache is enabled. Initializing connection pool at: {self.db_path}")
        self._initialize_pool()
        self._start_write_worker()
        self._initialized = True
        logger.debug(f"Cache initialization completed successfully with pool size: {self.pool_size}")

    def _start_write_worker(self):
        """Start the background worker for processing write operations"""
        self._write_worker_thread = threading.Thread(target=self._write_worker, daemon=True)
        self._write_worker_thread.start()

    def _write_worker(self):
        """Background worker that processes batched write operations"""
        while True:
            batch = []
            batch_start_time = time.time()
            
            # Collect items for the batch
            while len(batch) < self._write_batch_size and \
                  time.time() - batch_start_time < self._write_batch_timeout:
                try:
                    item = self._write_queue.popleft()
                    batch.append(item)
                except IndexError:
                    if batch:  # If we have items but queue is empty, process what we have
                        break
                    time.sleep(0.1)  # Short sleep if queue is empty
                    continue

            if batch:
                with self._write_lock:
                    try:
                        with self.get_connection_context() as conn:
                            if conn:
                                self._process_write_batch(conn, batch)
                    except Exception as e:
                        logger.error(f"Error processing write batch: {e}")

    def _process_write_batch(self, conn: sqlite3.Connection, batch: List[Tuple]):
        """Process a batch of write operations"""
        cursor = conn.cursor()
        try:
            cursor.executemany("""
                INSERT OR REPLACE INTO cache 
                (file_path, file_hash, hash_algorithm, file_info, size, mtime)
                VALUES (?, ?, ?, ?, ?, ?)
            """, batch)
            conn.commit()
            logger.debug(f"Successfully processed batch of {len(batch)} cache entries")
        except sqlite3.Error as e:
            logger.error(f"Database error during batch processing: {e}")
            conn.rollback()

    def queue_write(self, entry: Tuple):
        """Queue a write operation to be processed by the write worker"""
        if not self._cache_disabled:
            self._write_queue.append(entry)

    def _cleanup(self) -> None:
        if hasattr(self, 'pool') and self.pool is not None:
            logger.debug("Cleaning up existing connections...")
            while not self.pool.empty():
                try:
                    conn = self.pool.get_nowait()
                    conn.close()
                except (queue.Empty, sqlite3.Error) as e:
                    logger.error(f"Error during connection cleanup: {e}")
        self._initialized = False
        logger.debug("Connection cleanup completed.")

    def _initialize_pool(self) -> None:
        db_dir = Path(self.db_path).parent
        try:
            db_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured cache directory exists: {db_dir}")
        except Exception as e:
            logger.error(f"Failed to create cache directory: {e}")
            raise
        
        logger.debug(f"Initializing SQLite database at: {self.db_path}")
        self.pool = queue.Queue(maxsize=self.pool_size)
        
        for i in range(self.pool_size):
            try:
                conn = sqlite3.connect(
                    self.db_path,
                    check_same_thread=False,
                    timeout=20.0  # Increased timeout for busy waiting
                )
                conn.execute("PRAGMA foreign_keys = ON;")
                conn.execute("PRAGMA journal_mode = WAL;")
                conn.execute("PRAGMA busy_timeout = 20000;")  # 20 second busy timeout
                
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cache (
                        file_path TEXT PRIMARY KEY,
                        file_hash TEXT,
                        hash_algorithm TEXT,
                        file_info TEXT,
                        size INTEGER,
                        mtime REAL
                    )
                    """
                )
                
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_hash_algorithm
                    ON cache(hash_algorithm);
                    """
                )
                
                conn.commit()
                
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cache';")
                if cursor.fetchone() is None:
                    raise Exception("Cache table was not created successfully")
                
                self.pool.put(conn)
                logger.debug(f"Initialized connection {i+1}/{self.pool_size}")
            except sqlite3.Error as e:
                logger.error(f"SQLite error during database initialization: {e}")
                sys.exit(1)
            except Exception as e:
                logger.error(f"Error initialising database connection: {e}")
                sys.exit(1)

    def _reinitialize_if_needed(self) -> None:
        settings = QSettings()
        current_cache_disabled = settings.value("settings/disable_cache", False, bool)
        
        if (not self._initialized or 
            current_cache_disabled != self._current_settings.get('gui_cache_disabled')):
            logger.debug(f"Cache state changed or not initialized. Reinitializing connection pool.")
            self.__init__(
                self.db_path,
                self._current_settings.get('thread_count', 4),
                self._current_settings.get('force_disable_cache', False)
            )

    @contextmanager
    def get_connection_context(self) -> Generator[Optional[sqlite3.Connection], None, None]:
        self._reinitialize_if_needed()
        
        if self._cache_disabled:
            logger.debug("Cache access skipped (caching disabled)")
            yield None
            return

        conn: Optional[sqlite3.Connection] = None
        try:
            conn = self.pool.get(timeout=20.0)  # Increased timeout
            if not self._validate_connection(conn):
                logger.warning("Connection is invalid. Creating a new connection.")
                conn = self._create_new_connection(conn)
            yield conn
        except queue.Empty:
            logger.error("No available database connections in the pool. Timeout reached.")
            raise
        finally:
            if conn:
                try:
                    conn.commit()
                except sqlite3.Error as e:
                    logger.error(f"Error committing transaction: {e}")
                    try:
                        conn.rollback()
                    except:
                        pass
                self.pool.put(conn)
                logger.debug("Connection returned to pool")

    def _validate_connection(self, conn: sqlite3.Connection) -> bool:
        try:
            conn.execute("SELECT 1;")
            return True
        except sqlite3.Error:
            return False

    def _create_new_connection(self, old_conn: sqlite3.Connection) -> sqlite3.Connection:
        try:
            old_conn.close()
            new_conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=20.0
            )
            new_conn.execute("PRAGMA foreign_keys = ON;")
            new_conn.execute("PRAGMA journal_mode = WAL;")
            new_conn.execute("PRAGMA busy_timeout = 20000;")
            logger.debug("Created new database connection")
            return new_conn
        except sqlite3.Error as e:
            logger.error(f"Error creating new database connection: {e}")
            sys.exit(1)

    def close_all_connections(self, exclude_conn: Optional[sqlite3.Connection] = None) -> None:
        if self._cache_disabled or not hasattr(self, 'pool') or self.pool is None:
            return
        
        closed_connections = 0
        while not self.pool.empty():
            try:
                conn = self.pool.get_nowait()
                if conn != exclude_conn:
                    try:
                        conn.commit()
                    except sqlite3.Error:
                        pass
                    conn.close()
                    closed_connections += 1
                else:
                    self.pool.put(conn)
            except queue.Empty:
                break
            except sqlite3.Error as e:
                logger.error(f"Error closing database connection: {e}")
        if closed_connections > 0:
            logger.debug(f"Closed {closed_connections} database connections.")

_connection_pool_instance: Optional[ConnectionPool] = None
_pool_lock = threading.Lock()

def initialize_connection_pool(
    db_path: str,
    thread_count: int,
    force_disable_cache: bool = False
) -> None:
    global _connection_pool_instance
    with _pool_lock:
        _connection_pool_instance = ConnectionPool(db_path, thread_count, force_disable_cache)
        logger.debug("Connection pool initialized with current settings.")

@contextmanager
def get_connection_context() -> Generator[Optional[sqlite3.Connection], None, None]:
    if _connection_pool_instance is None:
        logger.error("Connection pool is not initialised. Please call initialize_connection_pool.")
        raise RuntimeError("Connection pool not initialised.")
    with _connection_pool_instance.get_connection_context() as conn:
        yield conn

def queue_write(entry: Tuple) -> None:
    """Queue a write operation to be processed in batch"""
    if _connection_pool_instance is not None:
        _connection_pool_instance.queue_write(entry)
    else:
        logger.warning("Connection pool not initialized. Write operation skipped.")

def close_all_connections(exclude_conn: Optional[sqlite3.Connection] = None) -> None:
    if _connection_pool_instance is not None:
        _connection_pool_instance.close_all_connections(exclude_conn)
    else:
        logger.warning("Connection pool was not initialised. No connections to close.")

def _shutdown():
    try:
        if _connection_pool_instance:
            _connection_pool_instance.close_all_connections()
    except Exception as e:
        logger.error(f"Error during connection pool shutdown: {e}")

atexit.unregister(_shutdown)
atexit.register(_shutdown)
