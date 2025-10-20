import base64
import logging
import os
from codecs import getincrementaldecoder
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from samuraizer.backend.cache.cache_operations import get_cached_entry, set_cached_entry
from samuraizer.backend.cache.connection_pool import get_connection_context, is_cache_disabled
from samuraizer.backend.cache.cache_cleaner import clean_cache
from ..analysis.hash_service import HashService
from ...utils.file_utils.mime_detection import is_binary
from ...config.timezone_service import TimezoneService

import charset_normalizer

try:
    from samuraizer import _native
except ImportError:  # pragma: no cover - optional native module
    _native = None

_STREAM_READ_CHUNK_SIZE = 256 * 1024  # 256 KiB keeps memory usage low while remaining efficient
_MAX_BINARY_CONTENT_BYTES = 3 * 1024 * 1024  # 3 MiB preview for binary files
_MAX_TEXT_CONTENT_BYTES = 5 * 1024 * 1024  # 5 MiB preview for text files
_ENCODING_SAMPLE_BYTES = 512 * 1024  # up to 512 KiB of data for encoding detection

logger = logging.getLogger(__name__)

def process_file(
    file_path: Path,
    max_file_size: int,
    include_binary: bool,
    image_extensions: Set[str],
    encoding: Optional[str] = None,
    hashing_enabled: bool = True,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    filename = file_path.name
    logger.debug(
        "Processing file: %s (hashing_enabled=%s)",
        file_path,
        hashing_enabled,
    )

    cache_active = hashing_enabled and not is_cache_disabled()
    if hashing_enabled and not cache_active:
        logger.debug("Cache disabled at runtime; skipping hashing")

    try:
        stat = file_path.stat()
        current_size = stat.st_size
        current_mtime = stat.st_mtime
    except OSError as e:
        logger.error(f"Failed to get file stats for {file_path}: {e}")
        return filename, {
            "type": "error",
            "content": f"Failed to get file stats: {str(e)}",
            "exception_type": type(e).__name__,
            "exception_message": str(e)
        }

    if current_size > max_file_size:
        logger.info(f"File too large and will be excluded: {file_path} ({current_size} bytes)")
        return filename, {
            "type": "excluded",
            "reason": "file_size",
            "size": current_size
        }

    # Only check cache if caching is enabled
    cached_entry = None
    file_hash = None
    if cache_active:
        logger.debug(f"Cache enabled, checking cache for file: {file_path}")
        # Check cache using xxHash
        with get_connection_context() as conn:
            if conn is not None:  # Only proceed if connection is available (cache enabled)
                logger.debug("Got valid connection from pool")
                cached_entry = get_cached_entry(conn, str(file_path.resolve()))
                logger.debug(f"Cache lookup result for {file_path}: {'hit' if cached_entry else 'miss'}")
            else:
                logger.warning("Connection is None despite hashing being enabled")

        if cached_entry:
            cached_size = cached_entry.get("size")
            cached_mtime = cached_entry.get("mtime")

            logger.debug(
                "Comparing cache: size=%s==%s, mtime=%s==%s",
                cached_size,
                current_size,
                cached_mtime,
                current_mtime,
            )

            # Only use cache if size and mtime match
            if cached_size == current_size and cached_mtime == current_mtime:
                logger.debug(f"Cache hit for file: {file_path}")
                return filename, cached_entry.get("file_info")

        # Compute hash for cache validation
        logger.debug(f"Computing hash for file: {file_path}")
        file_hash = HashService.compute_file_hash(file_path)
        logger.debug(f"Computed hash: {file_hash}")
        if isinstance(file_hash, dict) and file_hash.get("type") == "error":
            return filename, file_hash

    file_info = _process_file_content(file_path, include_binary, image_extensions, max_file_size, encoding)
    if file_info.get("type") in ["error", "excluded"]:
        return filename, file_info

    _add_metadata(file_info, stat)

    # Update cache only if caching is enabled and we have a valid hash
    if cache_active and file_hash:
        logger.debug(f"Attempting to update cache for file: {file_path}")
        with get_connection_context() as conn:
            if conn is not None:  # Only proceed if connection is available (cache enabled)
                try:
                    logger.debug(
                        "Got valid connection, writing to cache. Hash: %s",
                        file_hash,
                    )
                    set_cached_entry(
                        conn,
                        str(file_path.resolve()),
                        file_hash,
                        file_info,
                        current_size,
                        current_mtime,
                    )
                    logger.debug(f"Cache updated successfully for: {file_path}")
                except Exception as e:
                    logger.error(f"Failed to update cache for {file_path}: {e}", exc_info=True)
            else:
                logger.warning("Connection is None when trying to write to cache")

    return filename, file_info

def _process_file_content(
    file_path: Path,
    include_binary: bool,
    image_extensions: Set[str],
    max_file_size: int,
    encoding: Optional[str],
) -> Dict[str, Any]:
    file_extension = file_path.suffix.lower()
    is_image = file_extension in image_extensions

    try:
        binary = is_binary(file_path)

        if (binary or is_image) and not include_binary:
            logger.debug(f"Excluding {'binary' if binary else 'image'} file: {file_path}")
            return {
                "type": "excluded",
                "reason": "binary_or_image"
            }

        if binary:
            return _read_binary_file(file_path, max_file_size)
        else:
            return _read_text_file(file_path, max_file_size, encoding)

    except PermissionError as e:
        logger.error(f"Permission denied when reading file: {file_path}")
        return {
            "type": "error",
            "content": f"Permission denied: {str(e)}",
            "exception_type": type(e).__name__,
            "exception_message": str(e)
        }
    except IsADirectoryError:
        logger.error(f"Attempted to process a directory as a file: {file_path}")
        return {
            "type": "error",
            "content": "Is a directory"
        }
    except OSError as e:
        logger.error(f"OS error when processing file {file_path}: {e}")
        return {
            "type": "error",
            "content": f"OS error: {str(e)}",
            "exception_type": type(e).__name__,
            "exception_message": str(e)
        }
    except Exception as e:
        logger.error(f"Unexpected error when processing file {file_path}: {e}")
        return {
            "type": "error",
            "content": f"Unexpected error: {str(e)}",
            "exception_type": type(e).__name__,
            "exception_message": str(e)
        }

def _read_binary_file(file_path: Path, max_file_size: int) -> Dict[str, Any]:
    """Read binary file content without exhausting memory."""

    if _native is not None:
        try:
            preview_limit = min(max_file_size, _MAX_BINARY_CONTENT_BYTES)
            result = _native.read_binary_preview(str(file_path), preview_limit)
            if isinstance(result, dict):
                return result
        except Exception:
            logger.exception("Native binary preview failed; falling back to Python implementation")

    try:
        file_size = file_path.stat().st_size
        if file_size > max_file_size:
            logger.info(f"Binary file too large to include: {file_path} ({file_size} bytes)")
            return {
                "type": "excluded",
                "reason": "binary_too_large",
                "size": file_size
            }

        read_limit = min(max_file_size, _MAX_BINARY_CONTENT_BYTES)
        preview_size = min(file_size, read_limit)

        buffer = bytearray()
        with open(file_path, 'rb') as f:
            while len(buffer) < preview_size:
                chunk = f.read(min(_STREAM_READ_CHUNK_SIZE, preview_size - len(buffer)))
                if not chunk:
                    break
                buffer.extend(chunk)

        content = base64.b64encode(bytes(buffer)).decode('ascii')
        result: Dict[str, Any] = {
            "type": "binary",
            "content": content,
            "encoding": "base64",
            "preview_bytes": len(buffer)
        }

        if file_size > preview_size:
            logger.debug(f"Binary file {file_path} truncated to {preview_size} bytes")
            result["truncated"] = True

        logger.debug(f"Included binary file: {file_path} ({len(buffer)} preview bytes)")
        return result
    except Exception as e:
        logger.error(f"Error reading binary file {file_path}: {e}")
        return {
            "type": "error",
            "content": f"Failed to read binary file: {str(e)}",
            "exception_type": type(e).__name__,
            "exception_message": str(e)
        }

def _read_text_file(file_path: Path, max_file_size: int, encoding: Optional[str]) -> Dict[str, Any]:
    if _native is not None:
        try:
            preview_limit = min(max_file_size, _MAX_TEXT_CONTENT_BYTES)
            result = _native.read_text_preview(str(file_path), preview_limit, encoding)
            if isinstance(result, dict):
                return result
        except Exception:
            logger.exception("Native text preview failed; falling back to Python implementation")

    try:
        read_limit = min(max_file_size, _MAX_TEXT_CONTENT_BYTES)

        with open(file_path, 'rb') as f:
            sample = f.read(min(read_limit, _ENCODING_SAMPLE_BYTES))

            if encoding is None:
                matches = charset_normalizer.from_bytes(sample)
                best_match = matches.best()
                if best_match and best_match.encoding:
                    encoding_to_use = best_match.encoding
                    logger.debug(f"Detected encoding '{encoding_to_use}' for file {file_path}")
                else:
                    encoding_to_use = 'utf-8'
                    logger.warning(f"Could not detect encoding for {file_path}. Falling back to 'utf-8'.")
            else:
                encoding_to_use = encoding
                logger.debug(f"Using provided encoding '{encoding}' for file {file_path}")

            f.seek(0)
            decoder = getincrementaldecoder(encoding_to_use)(errors='replace')
            text_chunks: List[str] = []
            bytes_read = 0

            while bytes_read < read_limit:
                chunk = f.read(min(_STREAM_READ_CHUNK_SIZE, read_limit - bytes_read))
                if not chunk:
                    break
                bytes_read += len(chunk)
                text_chunks.append(decoder.decode(chunk, final=False))

            text_chunks.append(decoder.decode(b'', final=True))
            content = ''.join(text_chunks)

        logger.debug(f"Read text file: {file_path} with encoding {encoding_to_use}")
        result: Dict[str, Any] = {
            "type": "text",
            "encoding": encoding_to_use,
            "content": content,
            "preview_bytes": bytes_read
        }

        file_size = file_path.stat().st_size
        if file_size > read_limit:
            logger.debug(f"Text file {file_path} truncated to {read_limit} bytes")
            result["truncated"] = True

        return result
    except Exception as e:
        logger.error(f"Error reading text file {file_path}: {e}")
        return {
            "type": "error",
            "content": f"Failed to read text file: {str(e)}",
            "exception_type": type(e).__name__,
            "exception_message": str(e)
        }

def _add_metadata(file_info: Dict[str, Any], stat: os.stat_result) -> None:
    """Add metadata to file info with proper timezone handling."""
    if "timezone" in file_info:
        # Metadata already populated (likely by native backend)
        return
    try:
        tz_service = TimezoneService()
        tz_state = tz_service.get_config()
        target_tz = tz_service.get_timezone()
        use_utc = bool(tz_state.get("use_utc", False))

        # Convert timestamps to datetime objects with proper timezone
        birthtime = getattr(stat, "st_birthtime", None)
        if isinstance(birthtime, (int, float)):
            created_dt = datetime.fromtimestamp(birthtime, tz=timezone.utc)
            if not use_utc:
                created_dt = created_dt.astimezone(target_tz)
            created_ts = created_dt.isoformat()
        else:
            created_ts = None

        modified_dt = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        if not use_utc:
            modified_dt = modified_dt.astimezone(target_tz)
        modified_ts = modified_dt.isoformat()

        file_info.update({
            "size": stat.st_size,
            "created": created_ts,
            "modified": modified_ts,
            "permissions": oct(stat.st_mode),
            "timezone": str(target_tz)  # Include timezone information in metadata
        })
    except Exception as e:
        logger.warning(f"Could not retrieve complete metadata: {e}")
