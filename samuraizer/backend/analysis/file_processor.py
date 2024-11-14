import base64
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple, Union
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from samuraizer.backend.cache.cache_operations import get_cached_entry, set_cached_entry
from samuraizer.backend.cache.connection_pool import get_connection_context
from samuraizer.backend.cache.cache_cleaner import clean_cache
from ..analysis.hash_service import HashService
from ...utils.file_utils.mime_detection import is_binary
from ...config.timezone_config import TimezoneConfigManager

import charset_normalizer

logger = logging.getLogger(__name__)

def process_file(
    file_path: Path,
    max_file_size: int,
    include_binary: bool,
    image_extensions: Set[str],
    encoding: Optional[str] = None,
    hash_algorithm: Optional[str] = None,  # Added hash_algorithm parameter
) -> Tuple[str, Optional[Dict[str, Any]]]:
    filename = file_path.name
    logger.debug(f"Processing file: {file_path} (hash_algorithm: {hash_algorithm})")

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

    # Only check cache if caching is enabled (hash_algorithm is not None)
    cached_entry = None
    file_hash = None
    if hash_algorithm is not None:
        logger.debug(f"Cache enabled, checking cache for file: {file_path}")
        # Check cache using xxHash
        with get_connection_context() as conn:
            if conn is not None:  # Only proceed if connection is available (cache enabled)
                logger.debug("Got valid connection from pool")
                cached_entry = get_cached_entry(conn, str(file_path.resolve()))
                logger.debug(f"Cache lookup result for {file_path}: {'hit' if cached_entry else 'miss'}")
            else:
                logger.warning("Connection is None despite hash_algorithm being set")

        if cached_entry:
            cached_size = cached_entry.get("size")
            cached_mtime = cached_entry.get("mtime")
            cached_hash_algorithm = cached_entry.get("hash_algorithm")

            logger.debug(f"Comparing cache: size={cached_size}=={current_size}, mtime={cached_mtime}=={current_mtime}, algo={cached_hash_algorithm}=={hash_algorithm}")

            # Only use cache if size, mtime, and hash algorithm match
            if (cached_size == current_size and 
                cached_mtime == current_mtime and 
                cached_hash_algorithm == hash_algorithm):
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
    if hash_algorithm is not None and file_hash:
        logger.debug(f"Attempting to update cache for file: {file_path}")
        with get_connection_context() as conn:
            if conn is not None:  # Only proceed if connection is available (cache enabled)
                try:
                    logger.debug(f"Got valid connection, writing to cache. Hash: {file_hash}, Algorithm: {hash_algorithm}")
                    set_cached_entry(
                        conn,
                        str(file_path.resolve()),
                        file_hash,
                        file_info,
                        current_size,
                        current_mtime,
                        hash_algorithm  # Pass the hash_algorithm to set_cached_entry
                    )
                    logger.debug(f"Cache updated successfully for: {file_path}")
                except Exception as e:
                    logger.error(f"Failed to update cache for {file_path}: {e}", exc_info=True)
            else:
                logger.warning("Connection is None when trying to write to cache")

    return filename, file_info

def _process_file_content(file_path: Path, include_binary: bool, image_extensions: Set[str], max_file_size: int, encoding: str) -> Dict[str, Any]:
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
    try:
        file_size = file_path.stat().st_size
        if file_size > max_file_size:
            logger.info(f"Binary file too large to include: {file_path} ({file_size} bytes)")
            return {
                "type": "excluded",
                "reason": "binary_too_large",
                "size": file_size
            }
        
        with open(file_path, 'rb') as f:
            content = base64.b64encode(f.read()).decode('utf-8')
        logger.debug(f"Included binary file: {file_path}")
        return {
            "type": "binary",
            "content": content
        }
    except Exception as e:
        logger.error(f"Error reading binary file {file_path}: {e}")
        return {
            "type": "error",
            "content": f"Failed to read binary file: {str(e)}",
            "exception_type": type(e).__name__,
            "exception_message": str(e)
        }

def _read_text_file(file_path: Path, max_file_size: int, encoding: Optional[str]) -> Dict[str, Any]:
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read(max_file_size)

        if encoding is None:
            matches = charset_normalizer.from_bytes(raw_data)
            best_match = matches.best()
            if best_match:
                encoding_to_use = best_match.encoding
                content = str(best_match)  # This is the correct way to get normalized content
                logger.debug(f"Detected encoding '{encoding_to_use}' for file {file_path}")
            else:
                encoding_to_use = 'utf-8'
                content = raw_data.decode(encoding_to_use, errors='replace')
                logger.warning(f"Could not detect encoding for {file_path}. Falling back to 'utf-8'.")
        else:
            encoding_to_use = encoding
            content = raw_data.decode(encoding_to_use, errors='replace')
            logger.debug(f"Using provided encoding '{encoding}' for file {file_path}")

        logger.debug(f"Read text file: {file_path} with encoding {encoding_to_use}")
        return {
            "type": "text",
            "encoding": encoding_to_use,
            "content": content
        }
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
    try:
        # Get timezone configuration
        tz_config = TimezoneConfigManager()
        target_tz = tz_config.get_timezone()

        # Convert timestamps to datetime objects with proper timezone
        if hasattr(stat, 'st_birthtime'):
            created_dt = datetime.fromtimestamp(stat.st_birthtime, tz=timezone.utc)
            if not tz_config.config['use_utc']:
                created_dt = created_dt.astimezone(target_tz)
            created_ts = created_dt.isoformat()
        else:
            created_ts = None

        modified_dt = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        if not tz_config.config['use_utc']:
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
