# samuraizer/backend/cache/connection_pool.py

import atexit
import logging
import queue
import sqlite3
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

from .cache_state import CacheStateManager

logger = logging.getLogger(__name__)


class CacheIntegrityError(Exception):
    """Raised when the cache database fails an integrity check."""


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
    _write_batch_size = 100  # Number of writes to batch together
    _write_batch_timeout = 1.0  # Maximum time to wait for batch to fill

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super(ConnectionPool, cls).__new__(cls)
                    cls._instance._initialized = False
                    cls._instance._state_listener_registered = False
                    cls._instance._state_lock = threading.RLock()
        return cls._instance

    def __init__(self, db_path: str, thread_count: int, force_disable_cache: bool = False) -> None:
        pool_size = calculate_pool_size(thread_count)
        new_settings = {
            'db_path': db_path,
            'thread_count': thread_count,
        }

        with self._state_lock:
            if (
                self._initialized
                and self._current_settings
                and all(self._current_settings.get(k) == v for k, v in new_settings.items())
            ):
                self._ensure_state_listener()
                self._reinitialize_if_needed()
                return

            if self._initialized:
                self._cleanup(force=True)

            self._current_settings = new_settings
            self.db_path = db_path
            self.pool_size = pool_size

            if force_disable_cache:
                CacheStateManager.set_disabled(True)

            self._cache_disabled = CacheStateManager.is_disabled()

            self._reset_worker_state()

            if self._cache_disabled:
                logger.warning("Cache operations will be skipped. This may impact performance.")
                self.pool = None
                self._initialized = True
                self._ensure_state_listener()
                return

            logger.debug("Cache is enabled. Initializing connection pool at: %s", self.db_path)
            self._initialize_pool()
            self._start_write_worker()
            self._initialized = True
            self._ensure_state_listener()
            logger.debug(
                "Cache initialization completed successfully with pool size: %s",
                self.pool_size,
            )

    def _ensure_state_listener(self) -> None:
        if not getattr(self, "_state_listener_registered", False):
            CacheStateManager.register_listener(
                self._handle_external_state_change,
                notify_immediately=False,
            )
            self._state_listener_registered = True

    def _reset_worker_state(self) -> None:
        self._write_lock = threading.Lock()
        self._pending_lock = threading.Lock()
        self._pending_event = threading.Event()
        self._pending_event.set()
        self._pending_writes = 0
        self._stop_event = threading.Event()
        self._integrity_checked = False
        self._write_queue: Optional[queue.Queue] = queue.Queue()

    def _start_write_worker(self):
        """Start the background worker for processing write operations"""
        self._write_worker_thread = threading.Thread(target=self._write_worker, daemon=True)
        self._write_worker_thread.start()

    def _handle_external_state_change(self, disabled: bool) -> None:
        with self._state_lock:
            if disabled:
                self._transition_to_disabled()
            else:
                self._transition_to_enabled()

    def _transition_to_disabled(self) -> None:
        if self._cache_disabled:
            return

        self._cache_disabled = True
        logger.info("Disabling cache and shutting down connection pool")

        if hasattr(self, "_stop_event"):
            self._stop_event.set()

        if hasattr(self, "_write_worker_thread") and self._write_worker_thread.is_alive():
            self._write_worker_thread.join(timeout=2.0)

        discarded = self._discard_queue_entries()
        if discarded:
            logger.debug("Discarded %s pending cache writes", discarded)

        if hasattr(self, "_pending_event"):
            self._pending_event.set()
        self._pending_writes = 0
        self._write_queue = None

        if hasattr(self, "pool") and self.pool is not None:
            while not self.pool.empty():
                try:
                    conn = self.pool.get_nowait()
                    conn.close()
                except queue.Empty:
                    break
                except sqlite3.Error as exc:
                    logger.error("Error closing connection during disable: %s", exc)
            self.pool = None

    def _transition_to_enabled(self) -> None:
        if not self._cache_disabled:
            return

        if not self._current_settings:
            logger.warning("Cannot enable cache: no previous configuration available")
            return

        self._cache_disabled = False
        logger.info("Reinitializing cache subsystem after enable request")

        self._reset_worker_state()
        self._initialize_pool()
        self._start_write_worker()
        self._initialized = True

    def _discard_queue_entries(self) -> int:
        if not hasattr(self, "_write_queue") or self._write_queue is None:
            return 0

        discarded = 0
        while True:
            try:
                self._write_queue.get_nowait()
            except queue.Empty:
                break
            else:
                discarded += 1
                self._write_queue.task_done()

        if discarded:
            self._mark_writes_completed(discarded)

        return discarded

    def _write_worker(self):
        """Background worker that processes batched write operations"""
        while not self._stop_event.is_set() or (
            hasattr(self, "_write_queue") and self._write_queue and not self._write_queue.empty()
        ):
            if not hasattr(self, "_write_queue") or self._write_queue is None:
                time.sleep(self._write_batch_timeout)
                continue

            batch: List[Tuple] = []

            try:
                item = self._write_queue.get(timeout=self._write_batch_timeout)
                batch.append(item)
            except queue.Empty:
                continue

            batch_start_time = time.time()
            while (
                len(batch) < self._write_batch_size
                and (time.time() - batch_start_time) < self._write_batch_timeout
            ):
                try:
                    batch.append(self._write_queue.get_nowait())
                except queue.Empty:
                    break

            if batch:
                if CacheStateManager.is_disabled():
                    logger.debug("Dropping cache write batch because caching is disabled")
                    self._mark_writes_completed(len(batch))
                    for _ in batch:
                        self._write_queue.task_done()
                    continue

                with self._write_lock:
                    try:
                        with self.get_connection_context() as conn:
                            if conn:
                                self._process_write_batch(conn, batch)
                    except Exception as e:
                        logger.error(f"Error processing write batch: {e}")
                    finally:
                        for _ in batch:
                            self._write_queue.task_done()

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
        except Exception as e:
            logger.error(f"Unexpected error during batch processing: {e}")
            conn.rollback()
        finally:
            self._mark_writes_completed(len(batch))

    def _mark_writes_completed(self, count: int) -> None:
        with self._pending_lock:
            self._pending_writes = max(0, self._pending_writes - count)
            queue_empty = (
                not hasattr(self, "_write_queue")
                or self._write_queue is None
                or self._write_queue.empty()
            )
            if self._pending_writes == 0 and queue_empty:
                self._pending_event.set()

    def queue_write(self, entry: Tuple, synchronous: bool = False):
        """Queue a write operation to be processed by the write worker"""
        if CacheStateManager.is_disabled():
            self._cache_disabled = True
            logger.debug("Skipping cache write because caching is disabled")
            return

        if not hasattr(self, "_write_queue") or self._write_queue is None:
            self._write_queue = queue.Queue()

        with self._pending_lock:
            self._pending_writes += 1
            self._pending_event.clear()

        self._write_queue.put(entry)

        if synchronous:
            self.flush()

    def flush(self, timeout: Optional[float] = None) -> bool:
        """Wait until all pending writes are processed."""
        if CacheStateManager.is_disabled():
            self._cache_disabled = True
            return True

        logger.debug("Flushing pending cache writes...")
        finished = self._pending_event.wait(timeout)
        if finished:
            logger.debug("All pending cache writes have been flushed")
        else:
            logger.warning("Timeout reached while waiting for cache writes to flush")
        return finished

    def _drain_queue_synchronously(self) -> None:
        """Process any remaining items in the write queue synchronously."""
        if not hasattr(self, "_write_queue") or self._write_queue is None:
            return

        if CacheStateManager.is_disabled():
            self._discard_queue_entries()
            return

        drained = 0
        while not self._write_queue.empty():
            batch: List[Tuple] = []
            try:
                batch.append(self._write_queue.get_nowait())
            except queue.Empty:
                break

            while len(batch) < self._write_batch_size:
                try:
                    batch.append(self._write_queue.get_nowait())
                except queue.Empty:
                    break

            if not batch:
                break

            processed = False
            try:
                with self.get_connection_context() as conn:
                    if conn:
                        self._process_write_batch(conn, batch)
                        processed = True
            except Exception as e:
                logger.error(f"Error during synchronous cache flush: {e}")
            finally:
                for _ in batch:
                    self._write_queue.task_done()
                if not processed:
                    self._mark_writes_completed(len(batch))
                drained += len(batch)

        if drained:
            logger.debug(f"Synchronously processed {drained} pending cache writes")

    def shutdown(self, timeout: Optional[float] = 5.0, force: bool = False) -> None:
        """Flush remaining writes and stop the worker thread."""
        if not hasattr(self, "_stop_event"):
            return

        if CacheStateManager.is_disabled() and not force:
            return

        try:
            self._stop_event.set()
            if force or not CacheStateManager.is_disabled():
                self.flush(timeout)
            if hasattr(self, "_write_worker_thread") and self._write_worker_thread.is_alive():
                self._write_worker_thread.join(timeout)
        except Exception as e:
            logger.error(f"Error while shutting down write worker: {e}")
        finally:
            self._drain_queue_synchronously()
            if hasattr(self, "_pending_event"):
                self._pending_event.set()

    def _cleanup(self, force: bool = False) -> None:
        self.shutdown(force=force)
        if hasattr(self, 'pool') and self.pool is not None:
            logger.debug("Cleaning up existing connections...")
            while not self.pool.empty():
                try:
                    conn = self.pool.get_nowait()
                    conn.close()
                except (queue.Empty, sqlite3.Error) as e:
                    logger.error(f"Error during connection cleanup: {e}")
        self.pool = None
        self._initialized = False
        logger.debug("Connection cleanup completed.")

    def _verify_database_integrity(self, conn: sqlite3.Connection) -> None:
        """Run SQLite integrity check to ensure cache consistency."""
        try:
            cursor = conn.execute("PRAGMA integrity_check;")
            result = cursor.fetchone()
            if not result:
                raise CacheIntegrityError("Integrity check returned no result")
            status = result[0]
            if not isinstance(status, str) or status.lower() != "ok":
                raise CacheIntegrityError(status)
            logger.debug("Cache database integrity check passed")
        except sqlite3.Error as e:
            raise CacheIntegrityError(str(e)) from e

    def _handle_corrupt_cache(self) -> None:
        """Backup and reset a corrupt cache database."""
        try:
            db_path = Path(self.db_path)
            if db_path.exists():
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                backup_path = db_path.with_suffix(db_path.suffix + f".corrupt_{timestamp}")
                db_path.rename(backup_path)
                logger.warning(
                    "Corrupt cache database moved to backup location: %s", backup_path
                )
        except Exception as e:
            logger.error(f"Failed to backup corrupt cache database: {e}")
        finally:
            try:
                Path(self.db_path).unlink(missing_ok=True)
            except Exception:
                pass
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

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
        self._write_queue = queue.Queue()

        attempted_reset = False

        while True:
            try:
                for i in range(self.pool_size):
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

                    if not self._integrity_checked:
                        try:
                            self._verify_database_integrity(conn)
                            self._integrity_checked = True
                        except CacheIntegrityError:
                            conn.close()
                            raise

                    self.pool.put(conn)
                    logger.debug(f"Initialized connection {i+1}/{self.pool_size}")
                break
            except CacheIntegrityError as integrity_error:
                logger.warning(
                    "Cache database integrity check failed (%s). Attempting to rebuild cache database.",
                    integrity_error,
                )
                if attempted_reset:
                    logger.error("Cache database integrity check failed after reset attempt.")
                    raise
                attempted_reset = True
                while not self.pool.empty():
                    try:
                        self.pool.get_nowait().close()
                    except Exception:
                        pass
                self._handle_corrupt_cache()
                self._integrity_checked = False
                self.pool = queue.Queue(maxsize=self.pool_size)
                continue
            except sqlite3.Error as e:
                logger.error(f"SQLite error during database initialization: {e}")
                sys.exit(1)
            except Exception as e:
                logger.error(f"Error initialising database connection: {e}")
                sys.exit(1)

    def _reinitialize_if_needed(self) -> None:
        desired_disabled = CacheStateManager.is_disabled()

        if desired_disabled and not self._cache_disabled:
            self._transition_to_disabled()
        elif not desired_disabled and self._cache_disabled:
            self._transition_to_enabled()

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

    def close_all_connections(
        self,
        exclude_conn: Optional[sqlite3.Connection] = None,
        drain_timeout: Optional[float] = 5.0,
    ) -> None:
        if not hasattr(self, 'pool') or self.pool is None:
            return

        self.shutdown(timeout=drain_timeout, force=True)

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
    desired_state = force_disable_cache or CacheStateManager.is_disabled()
    CacheStateManager.set_disabled(desired_state)
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

def queue_write(entry: Tuple, synchronous: bool = False) -> None:
    """Queue a write operation to be processed in batch"""
    if _connection_pool_instance is not None:
        _connection_pool_instance.queue_write(entry, synchronous=synchronous)
    else:
        logger.warning("Connection pool not initialized. Write operation skipped.")


def queue_write_sync(entry: Tuple) -> None:
    """Queue a write operation and wait for it to complete."""
    queue_write(entry, synchronous=True)


def flush_pending_writes(timeout: Optional[float] = None) -> bool:
    """Flush pending write operations."""
    if _connection_pool_instance is not None:
        return _connection_pool_instance.flush(timeout)
    return True

def close_all_connections(
    exclude_conn: Optional[sqlite3.Connection] = None,
    drain_timeout: Optional[float] = 5.0,
) -> None:
    if _connection_pool_instance is not None:
        _connection_pool_instance.close_all_connections(exclude_conn, drain_timeout)
    else:
        logger.warning("Connection pool was not initialised. No connections to close.")


def set_cache_disabled(disabled: bool) -> None:
    CacheStateManager.set_disabled(disabled)


def is_cache_disabled() -> bool:
    return CacheStateManager.is_disabled()


def _shutdown():
    try:
        if _connection_pool_instance:
            _connection_pool_instance.close_all_connections()
    except Exception as e:
        logger.error(f"Error during connection pool shutdown: {e}")

atexit.unregister(_shutdown)
atexit.register(_shutdown)
