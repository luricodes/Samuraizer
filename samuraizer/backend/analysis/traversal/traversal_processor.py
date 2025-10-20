"""Traversal utilities backed entirely by the Rust engine."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Set, Tuple

from ...services.event_service.cancellation import CancellationToken
from samuraizer.backend.cache.cache_operations import set_cached_entry
from samuraizer.backend.cache.connection_pool import (
    get_connection_context,
    is_cache_disabled,
)
from samuraizer.config.timezone_service import TimezoneService

try:  # pragma: no cover - the native module ships with the wheel
    from samuraizer import _native
except ImportError as exc:  # pragma: no cover - defensive guard for type checkers
    raise RuntimeError(
        "The samuraizer native extension is required. "
        "Build it with `maturin develop` or install the wheel."
    ) from exc

_DEFAULT_CHUNK_SIZE = 256


def get_directory_structure(
    root_dir: Path,
    max_file_size: int,
    include_binary: bool,
    excluded_folders: Set[str],
    excluded_files: Set[str],
    follow_symlinks: bool,
    image_extensions: Set[str],
    exclude_patterns: List[str],
    threads: int,
    encoding: str = "utf-8",
    hashing_enabled: bool = True,
    progress_callback: Optional[Callable[[int], None]] = None,
    cancellation_token: Optional[CancellationToken] = None,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    max_pending_tasks: Optional[int] = None,  # kept for API compatibility
    chunk_callback: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    materialize: bool = True,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Collect a directory snapshot using the native traversal pipeline."""

    del max_pending_tasks  # parameter retained for backwards compatibility

    directory: Dict[str, Any] = {} if materialize else {}
    summary: Dict[str, Any] = {}

    for payload in generate_directory_chunks(
        root_dir=root_dir,
        max_file_size=max_file_size,
        include_binary=include_binary,
        excluded_folders=excluded_folders,
        excluded_files=excluded_files,
        follow_symlinks=follow_symlinks,
        image_extensions=image_extensions,
        exclude_patterns=exclude_patterns,
        threads=threads,
        encoding=encoding or "utf-8",
        hashing_enabled=hashing_enabled,
        progress_callback=progress_callback,
        chunk_callback=chunk_callback,
        cancellation_token=cancellation_token,
        chunk_size=chunk_size,
        max_pending_tasks=None,
    ):
        if "entries" in payload:
            entries = payload["entries"]
            if chunk_callback:
                try:
                    chunk_callback(entries)
                except Exception:  # pragma: no cover - callback safety net
                    logging.exception("Chunk callback failed; continuing execution")
            if materialize:
                _apply_entries(directory, entries)
        elif "summary" in payload:
            summary = payload["summary"]

    return directory, summary


def _generate_directory_chunks_native(
    *,
    root_dir: Path,
    max_file_size: int,
    include_binary: bool,
    excluded_folders: Set[str],
    excluded_files: Set[str],
    follow_symlinks: bool,
    image_extensions: Set[str],
    exclude_patterns: List[str],
    threads: int,
    encoding: str,
    hashing_enabled: bool,
    progress_callback: Optional[Callable[[int], None]],
    cancellation_token: Optional[CancellationToken],
    chunk_size: int,
) -> Iterator[Dict[str, Any]]:
    options = {
        "root": str(root_dir),
        "max_file_size": max_file_size,
        "include_binary": include_binary,
        "excluded_folders": set(excluded_folders),
        "excluded_files": set(excluded_files),
        "follow_symlinks": follow_symlinks,
        "image_extensions": set(image_extensions),
        "exclude_patterns": list(exclude_patterns),
        "threads": threads,
        "encoding": encoding,
        "hashing_enabled": hashing_enabled,
        "chunk_size": chunk_size,
    }

    try:
        tz_service = TimezoneService()
        tz_config = tz_service.get_config()
        options["use_utc"] = bool(tz_config.get("use_utc", False))
        options["timezone"] = str(tz_service.get_timezone())
    except Exception:  # pragma: no cover - timezone detection best effort
        logging.exception("Failed to resolve timezone configuration")

    if cancellation_token is not None:
        options["cancellation"] = cancellation_token

    generator = _native.traverse_and_process(options)
    processed = 0

    for payload in generator:
        if not isinstance(payload, dict):
            continue

        if "entries" in payload:
            raw_entries = payload["entries"]
            if not isinstance(raw_entries, list):
                continue

            processed_entries: List[Dict[str, Any]] = []

            for raw_entry in raw_entries:
                if not isinstance(raw_entry, dict):
                    continue

                parent = str(raw_entry.get("parent", "") or "")
                filename = raw_entry.get("filename")
                info = raw_entry.get("info") or {}

                if not filename:
                    continue
                if not isinstance(info, dict):
                    info = {"type": "error", "content": "Invalid info payload"}

                file_path = (root_dir / Path(parent) / filename) if parent else root_dir / filename

                if info.get("type") not in {"error", "excluded"}:
                    try:
                        stat_result = file_path.stat()
                    except OSError as exc:
                        logging.error("Failed to stat %s: %s", file_path, exc)
                        info = {
                            "type": "error",
                            "content": f"Failed to stat file: {exc}",
                            "exception_type": type(exc).__name__,
                            "exception_message": str(exc),
                        }
                    else:
                        if hashing_enabled and not is_cache_disabled():
                            hash_value = raw_entry.get("hash")
                            if isinstance(hash_value, str):
                                try:
                                    with get_connection_context() as conn:
                                        if conn is not None:
                                            try:
                                                set_cached_entry(
                                                    conn,
                                                    str(file_path.resolve()),
                                                    hash_value,
                                                    info,
                                                    stat_result.st_size,
                                                    stat_result.st_mtime,
                                                )
                                            except Exception:  # pragma: no cover - cache IO guard
                                                logging.exception("Failed to update cache for %s", file_path)
                                except RuntimeError:
                                    logging.debug("Cache connection pool unavailable; skipping persist")

                processed_entries.append({
                    "parent": parent,
                    "filename": filename,
                    "info": info,
                })

                processed += 1
                if progress_callback:
                    try:
                        progress_callback(processed)
                    except Exception:  # pragma: no cover - callback safety net
                        logging.exception("Progress callback failed")

            if processed_entries:
                yield {"entries": processed_entries}

        elif "summary" in payload:
            summary = payload["summary"]
            if isinstance(summary, dict):
                yield {"summary": summary}


def generate_directory_chunks(
    *,
    root_dir: Path,
    max_file_size: int,
    include_binary: bool,
    excluded_folders: Set[str],
    excluded_files: Set[str],
    follow_symlinks: bool,
    image_extensions: Set[str],
    exclude_patterns: List[str],
    threads: int,
    encoding: str,
    hashing_enabled: bool,
    progress_callback: Optional[Callable[[int], None]],
    chunk_callback: Optional[Callable[[List[Dict[str, Any]]], None]],
    cancellation_token: Optional[CancellationToken],
    chunk_size: int,
    max_pending_tasks: Optional[int],  # retained for API compatibility
) -> Iterator[Dict[str, Any]]:
    """Yield traversal chunks generated by the Rust backend."""

    del max_pending_tasks  # compatibility no-op
    del chunk_callback

    for payload in _generate_directory_chunks_native(
        root_dir=root_dir,
        max_file_size=max_file_size,
        include_binary=include_binary,
        excluded_folders=excluded_folders,
        excluded_files=excluded_files,
        follow_symlinks=follow_symlinks,
        image_extensions=image_extensions,
        exclude_patterns=exclude_patterns,
        threads=threads,
        encoding=encoding,
        hashing_enabled=hashing_enabled,
        progress_callback=progress_callback,
        cancellation_token=cancellation_token,
        chunk_size=chunk_size,
    ):
        yield payload


def _apply_entries(structure: Dict[str, Any], entries: List[Dict[str, Any]]) -> None:
    for entry in entries:
        parent = entry.get("parent", "")
        filename = entry.get("filename")
        info = entry.get("info")

        if not filename:
            continue

        current = structure
        if parent:
            for part in Path(parent).parts:
                current = current.setdefault(part, {})

        current[filename] = info
