"""Traversal utilities backed by the Rust engine with a Python fallback."""

from __future__ import annotations

import base64
import fnmatch
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Set, Tuple

from charset_normalizer import from_bytes
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ...services.event_service.cancellation import CancellationToken
from samuraizer.backend.cache.cache_operations import set_cached_entry
from samuraizer.backend.cache.connection_pool import (
    get_connection_context,
    is_cache_disabled,
)
from samuraizer.config.timezone_service import TimezoneService

try:  # pragma: no cover - the native module ships with the wheel
    from samuraizer import _native
except ImportError:  # pragma: no cover - allow running without native bindings
    _native = None

_DEFAULT_CHUNK_SIZE = 256
_FALLBACK_SAMPLE_BYTES = 512 * 1024


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


def _build_traversal_options(
    *,
    root_dir: Path,
    max_file_size: int,
    include_binary: bool,
    excluded_folders: Set[str],
    excluded_files: Set[str],
    follow_symlinks: bool,
    image_extensions: Set[str],
    exclude_patterns: Sequence[str],
    threads: int,
    encoding: str,
    hashing_enabled: bool,
    cancellation_token: Optional[CancellationToken],
    chunk_size: int,
) -> Dict[str, Any]:
    options: Dict[str, Any] = {
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
        "chunk_size": max(1, int(chunk_size or _DEFAULT_CHUNK_SIZE)),
    }

    try:
        tz_service = TimezoneService()
        tz_config = tz_service.get_config()
        options["use_utc"] = bool(tz_config.get("use_utc", False))
        options["timezone"] = str(tz_service.get_timezone())
    except Exception:  # pragma: no cover - timezone detection best effort
        logging.exception("Failed to resolve timezone configuration")
        options.setdefault("use_utc", True)
        options.setdefault("timezone", "UTC")

    if cancellation_token is not None:
        options["cancellation"] = cancellation_token

    return options


def _generate_directory_chunks_native(
    *,
    options: Dict[str, Any],
    root_dir: Path,
    hashing_enabled: bool,
    progress_callback: Optional[Callable[[int], None]],
) -> Iterator[Dict[str, Any]]:
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


def _matches_patterns(value: str, patterns: Sequence[str]) -> bool:
    return any(fnmatch.fnmatch(value, pattern) for pattern in patterns)


def _resolve_timezone(options: Dict[str, Any]) -> Tuple[timezone, str]:
    use_utc = bool(options.get("use_utc"))
    tz_name = options.get("timezone")

    if use_utc:
        return timezone.utc, "UTC"

    if isinstance(tz_name, str) and tz_name:
        try:
            return ZoneInfo(tz_name), tz_name
        except ZoneInfoNotFoundError:
            logging.debug("Configured timezone '%s' unavailable; falling back", tz_name)

    current = datetime.now().astimezone().tzinfo or timezone.utc
    label = getattr(current, "key", None) or getattr(current, "zone", None) or current.tzname(None) or "UTC"
    return current, label


def _format_timestamp(value: Optional[float], tzinfo: timezone) -> Optional[str]:
    if value is None:
        return None
    try:
        dt = datetime.fromtimestamp(value, tzinfo)
    except (OverflowError, OSError, ValueError):
        return None
    return dt.isoformat()


def _detect_encoding(sample: bytes, requested: Optional[str]) -> str:
    import codecs

    if requested:
        try:
            codec = codecs.lookup(requested)
            return codec.name
        except LookupError:
            logging.debug("Requested encoding '%s' unavailable; auto-detecting", requested)

    if not sample:
        return requested or "utf-8"

    match = from_bytes(sample).best()
    if match and match.encoding:
        return match.encoding

    try:
        sample.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return requested or "latin-1"


def _read_text_preview(
    path: Path,
    *,
    max_preview_bytes: int,
    encoding: Optional[str],
) -> Dict[str, Any]:
    try:
        with path.open("rb") as handle:
            preview = handle.read(max_preview_bytes)
    except OSError as exc:
        raise RuntimeError(f"Failed to read text preview for {path}: {exc}") from exc

    encoding_name = _detect_encoding(preview[:_FALLBACK_SAMPLE_BYTES], encoding)
    text = preview.decode(encoding_name, errors="replace")
    preview_bytes = len(preview)
    size = path.stat().st_size
    result: Dict[str, Any] = {
        "type": "text",
        "encoding": encoding_name,
        "content": text,
        "preview_bytes": preview_bytes,
    }
    if size > preview_bytes:
        result["truncated"] = True
    return result


def _read_binary_preview(path: Path, *, max_preview_bytes: int) -> Dict[str, Any]:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise RuntimeError(f"Failed to stat binary file {path}: {exc}") from exc

    if size > max_preview_bytes:
        return {"type": "excluded", "reason": "binary_too_large", "size": int(size)}

    try:
        with path.open("rb") as handle:
            payload = handle.read(max_preview_bytes)
    except OSError as exc:
        raise RuntimeError(f"Failed to read binary preview for {path}: {exc}") from exc

    encoded = base64.b64encode(payload).decode("ascii") if payload else ""
    result: Dict[str, Any] = {
        "type": "binary",
        "content": encoded,
        "encoding": "base64",
        "preview_bytes": len(payload),
    }
    if size > len(payload):
        result["truncated"] = True
    return result


def _normalise_parent(root_dir: Path, file_path: Path) -> str:
    try:
        relative = file_path.parent.relative_to(root_dir)
    except ValueError:
        return ""
    parts = list(relative.parts)
    return "/".join(parts)


def _process_entry_python(
    file_path: Path,
    *,
    options: Dict[str, Any],
    root_dir: Path,
    tzinfo: timezone,
    tz_label: str,
    encoding: str,
) -> Tuple[Dict[str, Any], Optional[Dict[str, str]]]:
    include_binary = bool(options.get("include_binary"))
    image_extensions = {ext.lower() for ext in options.get("image_extensions", set())}
    max_file_size = int(options.get("max_file_size", 0))
    hashing_enabled = bool(options.get("hashing_enabled"))

    parent = _normalise_parent(root_dir, file_path)
    filename = file_path.name

    try:
        stat_result = file_path.stat()
    except OSError as exc:
        info = {
            "type": "error",
            "content": f"Failed to stat file: {exc}",
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
        }
        failure = {"file": str(file_path), "error": info["content"]}
        entry = {"parent": parent, "filename": filename, "info": info}
        return entry, failure

    size = int(stat_result.st_size)
    if max_file_size > 0 and size > max_file_size:
        info = {"type": "excluded", "reason": "file_size", "size": size}
        entry = {"parent": parent, "filename": filename, "info": info}
        return entry, None

    extension = file_path.suffix.lower()
    is_image = extension in image_extensions

    try:
        from samuraizer.utils.file_utils import mime_detection

        is_binary = mime_detection.is_binary(file_path)
    except Exception as exc:  # pragma: no cover - defensive fallback
        logging.debug("Binary detection failed for %s: %s", file_path, exc)
        is_binary = False

    if (is_binary or is_image) and not include_binary:
        info = {"type": "excluded", "reason": "binary_or_image"}
        entry = {"parent": parent, "filename": filename, "info": info}
        return entry, None

    preview_error: Optional[Dict[str, str]] = None
    try:
        if is_binary or is_image:
            info = _read_binary_preview(file_path, max_preview_bytes=max_file_size or size)
        else:
            info = _read_text_preview(
                file_path,
                max_preview_bytes=max_file_size or size,
                encoding=encoding,
            )
    except Exception as exc:  # pragma: no cover - preview read failures are rare
        message = f"Failed to read file: {exc}"
        info = {
            "type": "error",
            "content": message,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
        }
        preview_error = {"file": str(file_path), "error": message}

    info.setdefault("size", size)
    info.setdefault("permissions", format(getattr(stat_result, "st_mode", 0), "#o"))
    info.setdefault("modified", _format_timestamp(getattr(stat_result, "st_mtime", None), tzinfo))
    info.setdefault("created", _format_timestamp(getattr(stat_result, "st_ctime", None), tzinfo))
    info.setdefault("timezone", tz_label)

    stat_block = {
        "size": size,
        "mtime": float(getattr(stat_result, "st_mtime", 0.0)),
        "ctime": float(getattr(stat_result, "st_ctime", 0.0)),
        "mode": int(getattr(stat_result, "st_mode", 0)),
    }

    entry: Dict[str, Any] = {
        "parent": parent,
        "filename": filename,
        "info": info,
        "stat": stat_block,
    }

    if hashing_enabled:
        try:
            from samuraizer.backend.analysis.hash_service import HashService

            hash_value = HashService.compute_file_hash(file_path)
        except Exception as exc:  # pragma: no cover - hashing fallback errors are rare
            logging.debug("Hash computation failed for %s: %s", file_path, exc)
            hash_value = None

        if hash_value is not None:
            entry["hash"] = hash_value
            if not is_cache_disabled():
                try:
                    with get_connection_context() as conn:
                        if conn is not None:
                            set_cached_entry(
                                conn,
                                str(file_path.resolve()),
                                hash_value,
                                info,
                                size,
                                float(getattr(stat_result, "st_mtime", 0.0)),
                            )
                except RuntimeError:
                    logging.debug("Cache connection pool unavailable; skipping persist")
                except Exception:  # pragma: no cover - cache IO guard
                    logging.exception("Failed to update cache for %s", file_path)

    failure = preview_error
    return entry, failure


def _generate_directory_chunks_python(
    *,
    options: Dict[str, Any],
    root_dir: Path,
    progress_callback: Optional[Callable[[int], None]],
) -> Iterator[Dict[str, Any]]:
    chunk_size = int(options.get("chunk_size", _DEFAULT_CHUNK_SIZE))
    excluded_folders = {str(folder) for folder in options.get("excluded_folders", set())}
    excluded_files = {str(name) for name in options.get("excluded_files", set())}
    exclude_patterns = list(options.get("exclude_patterns", []))
    follow_symlinks = bool(options.get("follow_symlinks"))
    encoding = options.get("encoding") or "utf-8"
    cancellation_token: Optional[CancellationToken] = options.get("cancellation")

    tzinfo, tz_label = _resolve_timezone(options)

    candidates: List[Path] = []
    excluded_count = 0
    stopped_early = False

    for dirpath, dirnames, filenames in os.walk(root_dir, followlinks=follow_symlinks):
        if cancellation_token and cancellation_token.is_cancellation_requested():
            stopped_early = True
            break

        current_dir = Path(dirpath)
        try:
            relative_dir = current_dir.relative_to(root_dir)
            relative_dir_str = relative_dir.as_posix()
        except ValueError:
            relative_dir_str = ""

        dirnames[:] = [
            dirname
            for dirname in dirnames
            if dirname not in excluded_folders
            and not _matches_patterns(
                f"{relative_dir_str}/{dirname}".lstrip("/"), exclude_patterns
            )
        ]

        for filename in filenames:
            full_path = current_dir / filename
            try:
                relative = full_path.relative_to(root_dir)
            except ValueError:
                continue
            relative_str = relative.as_posix()
            if filename in excluded_files or _matches_patterns(relative_str, exclude_patterns):
                excluded_count += 1
                continue
            candidates.append(full_path)

    candidates.sort(key=lambda path: path.relative_to(root_dir).as_posix())
    included_count = len(candidates)

    chunk: List[Dict[str, Any]] = []
    processed = 0
    failures: List[Dict[str, str]] = []

    for file_path in candidates:
        if cancellation_token and cancellation_token.is_cancellation_requested():
            stopped_early = True
            break

        entry, failure = _process_entry_python(
            file_path,
            options=options,
            root_dir=root_dir,
            tzinfo=tzinfo,
            tz_label=tz_label,
            encoding=encoding,
        )
        chunk.append(entry)
        processed += 1

        if failure:
            failures.append(failure)

        if progress_callback:
            try:
                progress_callback(processed)
            except Exception:  # pragma: no cover - callback safety net
                logging.exception("Progress callback failed")

        if len(chunk) >= chunk_size:
            yield {"entries": chunk}
            chunk = []

    if chunk:
        yield {"entries": chunk}

    total_files = included_count + excluded_count
    excluded_percentage = (excluded_count / total_files * 100.0) if total_files else 0.0

    summary: Dict[str, Any] = {
        "total_files": total_files,
        "excluded_files": excluded_count,
        "included_files": included_count,
        "excluded_percentage": excluded_percentage,
        "failed_files": failures,
        "stopped_early": stopped_early,
        "processed_files": processed,
    }

    if options.get("hashing_enabled"):
        summary["hash_algorithm"] = "xxhash"

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
    """Yield traversal chunks using the native engine when available."""

    del max_pending_tasks  # compatibility no-op
    del chunk_callback

    options = _build_traversal_options(
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
        cancellation_token=cancellation_token,
        chunk_size=chunk_size,
    )

    if _native is not None:
        generator = _generate_directory_chunks_native(
            options=options,
            root_dir=root_dir,
            hashing_enabled=hashing_enabled,
            progress_callback=progress_callback,
        )
    else:
        generator = _generate_directory_chunks_python(
            options=options,
            root_dir=root_dir,
            progress_callback=progress_callback,
        )

    for payload in generator:
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
