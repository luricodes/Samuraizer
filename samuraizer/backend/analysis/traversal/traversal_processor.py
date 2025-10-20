from typing import Any, Dict, List, Set, Optional, Tuple, Callable, Iterator
from concurrent.futures import (
    ThreadPoolExecutor,
    Future,
    wait,
    FIRST_COMPLETED,
    CancelledError,
)
from tqdm import tqdm
from pathlib import Path
import logging
import sys
import io

from .traversal_core import traverse_and_collect
from ..file_processor import process_file, _add_metadata
from ...services.event_service.cancellation import CancellationToken
from samuraizer.backend.cache.cache_operations import set_cached_entry
from samuraizer.backend.cache.connection_pool import get_connection_context, is_cache_disabled

try:
    from samuraizer import _native
except ImportError:  # pragma: no cover - optional native module
    _native = None

_DEFAULT_CHUNK_SIZE = 256
_DEFAULT_PENDING_MULTIPLIER = 4


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
    encoding: str = 'utf-8',
    hashing_enabled: bool = True,
    progress_callback: Optional[Callable[[int], None]] = None,
    cancellation_token: Optional[CancellationToken] = None,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    max_pending_tasks: Optional[int] = None,
    chunk_callback: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    materialize: bool = True,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:

    dir_structure: Dict[str, Any] = {} if materialize else {}

    generator = generate_directory_chunks(
        root_dir=root_dir,
        max_file_size=max_file_size,
        include_binary=include_binary,
        excluded_folders=excluded_folders,
        excluded_files=excluded_files,
        follow_symlinks=follow_symlinks,
        image_extensions=image_extensions,
        exclude_patterns=exclude_patterns,
        threads=threads,
        encoding=encoding or 'utf-8',
        hashing_enabled=hashing_enabled,
        progress_callback=progress_callback,
        cancellation_token=cancellation_token,
        chunk_size=chunk_size,
        max_pending_tasks=max_pending_tasks,
    )

    summary: Dict[str, Any] = {}
    for payload in generator:
        if "entries" in payload:
            entries = payload["entries"]
            if chunk_callback:
                try:
                    chunk_callback(entries)
                except Exception:
                    logging.exception("Chunk callback failed; continuing without interruption")
            if materialize:
                _apply_entries(dir_structure, entries)
        elif "summary" in payload:
            summary = payload["summary"]

    return dir_structure, summary


def _generate_directory_chunks_python(
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
    max_pending_tasks: Optional[int],
) -> Iterator[Dict[str, Any]]:
    chunk_size = max(1, chunk_size)
    max_workers = max(1, threads)
    pending_limit = max_pending_tasks or max(max_workers * _DEFAULT_PENDING_MULTIPLIER, chunk_size)

    file_iterator, counters = traverse_and_collect(
        root_dir,
        excluded_folders,
        excluded_files,
        exclude_patterns,
        follow_symlinks,
        cancellation_token=cancellation_token,
    )

    logging.debug("Starting progressive processing pipeline")

    # Create a fallback file object if sys.stdout is None or not available
    file_out = sys.stdout if hasattr(sys, 'stdout') and sys.stdout is not None else io.StringIO()

    pbar: tqdm = tqdm(
        total=0,
        desc="Process files",
        unit="file",
        dynamic_ncols=True,
        file=file_out,
    )

    failed_files: List[Dict[str, str]] = []
    processed_count = 0
    chunk: List[Dict[str, Any]] = []

    def emit_chunk(force: bool = False) -> Iterator[Dict[str, Any]]:
        nonlocal chunk
        if chunk and (force or len(chunk) >= chunk_size):
            to_emit = chunk
            chunk = []
            yield {"entries": to_emit}

    pending: Dict[Future[Tuple[str, Any]], Path] = {}
    scheduling_finished = False

    def _schedule_more(executor: ThreadPoolExecutor) -> None:
        nonlocal scheduling_finished
        while not scheduling_finished and len(pending) < pending_limit:
            if cancellation_token and cancellation_token.is_cancellation_requested():
                scheduling_finished = True
                break
            try:
                file_path = next(file_iterator)
            except StopIteration:
                scheduling_finished = True
                break

            future = executor.submit(
                process_file,
                file_path,
                max_file_size,
                include_binary,
                image_extensions,
                encoding=encoding,
                hashing_enabled=hashing_enabled,
            )
            pending[future] = file_path

            # Update the progress bar total dynamically as we discover files
            if pbar.total != counters.included:
                pbar.total = counters.included
                pbar.refresh()

    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            _schedule_more(executor)

            while pending:
                if cancellation_token and cancellation_token.is_cancellation_requested():
                    logging.info("Cancellation requested; draining pending results")
                    for future in list(pending.keys()):
                        if not future.done():
                            future.cancel()

                done, _ = wait(pending.keys(), return_when=FIRST_COMPLETED)
                for future in done:
                    file_path = pending.pop(future)
                    if future.cancelled():
                        continue

                    try:
                        filename, file_info = future.result()
                    except CancelledError:
                        continue
                    except Exception as exc:  # pragma: no cover - safety net
                        logging.error(f"Error when processing the file {file_path}: {exc}")
                        file_info = {
                            "type": "error",
                            "content": f"Errors during processing: {str(exc)}",
                            "exception_type": type(exc).__name__,
                            "exception_message": str(exc),
                        }
                        failed_files.append({"file": str(file_path), "error": str(exc)})
                        filename = file_path.name

                    parent_str = _normalize_parent(root_dir, file_path)
                    if file_info is not None:
                        entry = {
                            "parent": parent_str,
                            "filename": filename,
                            "info": file_info,
                        }
                        chunk.append(entry)

                    processed_count += 1
                    pbar.update(1)
                    if progress_callback:
                        try:
                            progress_callback(processed_count)
                        except Exception:
                            logging.exception("Progress callback failed")

                    for emitted in emit_chunk():
                        yield emitted

                if not scheduling_finished:
                    _schedule_more(executor)

    except KeyboardInterrupt:  # pragma: no cover - interactive safeguard
        logging.warning("\nCancellation by user. Attempts to terminate running tasks...")
        raise
    finally:
        if pbar.total != counters.included:
            pbar.total = counters.included
            pbar.refresh()
        for emitted in emit_chunk(force=True):
            yield emitted
        pbar.close()

    included_files = counters.included
    excluded_files_count = counters.excluded
    total_files = included_files + excluded_files_count
    excluded_percentage = (excluded_files_count / total_files * 100) if total_files else 0.0

    if cancellation_token and cancellation_token.is_cancellation_requested():
        logging.info(
            "Analysis was stopped. %d files were processed before cancellation.",
            processed_count,
        )

    summary: Dict[str, Any] = {
        "total_files": total_files,
        "excluded_files": excluded_files_count,
        "included_files": included_files,
        "excluded_percentage": excluded_percentage,
        "failed_files": failed_files,
        "stopped_early": bool(cancellation_token and cancellation_token.is_cancellation_requested()),
        "processed_files": processed_count,
    }

    if hashing_enabled:
        summary["hash_algorithm"] = "xxhash"

    logging.info("Analysis Summary:")
    logging.info("  Processed files: %d", included_files)
    logging.info("  Excluded files: %d (%.2f%%)", excluded_files_count, excluded_percentage)
    if failed_files:
        logging.info("  Failed files: %d", len(failed_files))
    if cancellation_token and cancellation_token.is_cancellation_requested():
        logging.info("  Analysis was stopped before completion")
    logging.info(
        "  Hash algorithm used: %s",
        "xxhash" if hashing_enabled else "disabled",
    )

    yield {"summary": summary}


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
    chunk_callback: Optional[Callable[[List[Dict[str, Any]]], None]],
    cancellation_token: Optional[CancellationToken],
    chunk_size: int,
) -> Iterator[Dict[str, Any]]:
    options = {
        "root": str(root_dir),
        "max_file_size": max_file_size,
        "include_binary": include_binary,
        "excluded_folders": sorted(excluded_folders),
        "excluded_files": sorted(excluded_files),
        "follow_symlinks": follow_symlinks,
        "image_extensions": sorted(image_extensions),
        "exclude_patterns": list(exclude_patterns),
        "threads": threads,
        "encoding": encoding,
        "hashing_enabled": hashing_enabled,
        "chunk_size": chunk_size,
    }

    if cancellation_token is not None:
        options["cancellation"] = cancellation_token

    generator = _native.traverse_and_process(options)
    processed_count = 0

    for payload in generator:
        if not isinstance(payload, dict):
            continue

        if "entries" in payload:
            raw_entries = payload["entries"]
            processed_entries: List[Dict[str, Any]] = []
            if not isinstance(raw_entries, list):
                continue

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
                        _add_metadata(info, stat_result)
                        if hashing_enabled and not is_cache_disabled():
                            hash_value = raw_entry.get("hash")
                            if isinstance(hash_value, str):
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
                                        except Exception:
                                            logging.exception("Failed to update cache for %s", file_path)

                processed_entries.append({
                    "parent": parent,
                    "filename": filename,
                    "info": info,
                })

                processed_count += 1
                if progress_callback:
                    try:
                        progress_callback(processed_count)
                    except Exception:
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
    max_pending_tasks: Optional[int],
) -> Iterator[Dict[str, Any]]:
    if _native is not None:
        try:
            yield from _generate_directory_chunks_native(
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
                chunk_callback=chunk_callback,
                cancellation_token=cancellation_token,
                chunk_size=chunk_size,
            )
            return
        except Exception:
            logging.exception("Native traversal failed; falling back to Python implementation")

    yield from _generate_directory_chunks_python(
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
        chunk_callback=chunk_callback,
        cancellation_token=cancellation_token,
        chunk_size=chunk_size,
        max_pending_tasks=max_pending_tasks,
    )


def _normalize_parent(root_dir: Path, file_path: Path) -> str:
    try:
        relative_parent = file_path.parent.relative_to(root_dir)
        parent_str = str(relative_parent).strip()
        if parent_str in {".", ""}:
            return ""
        return parent_str.replace("\\", "/")
    except ValueError:
        return str(file_path.parent)


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
