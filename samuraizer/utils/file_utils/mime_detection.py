# samuraizer/utils/mime_type.py

from __future__ import annotations

import logging
import threading
from functools import lru_cache
from pathlib import Path
from typing import Optional, Tuple

import magic  # type: ignore[import-untyped]
from colorama import Fore, Style

from .file_helpers import (
    HEURISTIC_SAMPLE_SIZE,
    analyse_sample,
    classify_by_extension,
    is_binary_alternative,
    read_file_sample,
)

logger = logging.getLogger(__name__)

thread_local_data = threading.local()

_MAGIC_FLAGS = 0
for flag_name in ("MAGIC_MIME_TYPE", "MAGIC_ERROR", "MAGIC_NO_CHECK_TEXT"):
    _MAGIC_FLAGS |= getattr(magic, flag_name, 0)

_TEXTUAL_MIME_PREFIXES = (
    "text/",
    "application/json",
    "application/xml",
    "application/javascript",
    "application/x-javascript",
    "application/x-sh",
)
_TEXTUAL_MIME_TYPES = {
    "application/x-empty",
    "inode/x-empty",
}


def get_magic_instance():
    if not hasattr(thread_local_data, "mime"):
        try:
            # python-magic accepts either the ``mime`` kwarg or a flags bitmask.
            # Using flags allows us to disable text heuristics and rely on our
            # own fast-path implementation.
            thread_local_data.mime = magic.Magic(flags=_MAGIC_FLAGS) if _MAGIC_FLAGS else magic.Magic(mime=True)
        except Exception as exc:  # pragma: no cover - libmagic may be absent
            logger.error("%sError initializing magic: %s%s", Fore.RED, exc, Style.RESET_ALL)
            thread_local_data.mime = None
    return thread_local_data.mime


def _mime_implies_text(mime_type: str) -> bool:
    if mime_type in _TEXTUAL_MIME_TYPES:
        return True
    return mime_type.startswith(_TEXTUAL_MIME_PREFIXES)


def _detect_via_magic(sample: bytes, file_path: Path) -> Optional[bool]:
    mime = get_magic_instance()
    if mime is None:
        return None

    try:
        mime_type = mime.from_buffer(sample)
    except Exception as exc:
        message = str(exc)
        if "regex error 14" in message:
            logger.debug(
                "libmagic regex failure on %s; falling back to heuristics", file_path
            )
        else:
            logger.warning(
                "%sError detecting MIME type for %s: %s%s",
                Fore.YELLOW,
                file_path,
                message,
                Style.RESET_ALL,
            )
        return None

    if not mime_type:
        return None

    logger.debug("File: %s - MIME type: %s", file_path, mime_type)
    if _mime_implies_text(mime_type):
        return False
    if mime_type == "application/octet-stream":
        return None
    return True


def _stat_key(file_path: Path) -> Optional[Tuple[str, int, int]]:
    try:
        stat_result = file_path.stat()
    except OSError as exc:
        logger.warning("Failed to stat %s: %s", file_path, exc)
        return None

    mtime_ns = getattr(stat_result, "st_mtime_ns", int(stat_result.st_mtime * 1_000_000_000))
    return (str(file_path.resolve()), stat_result.st_size, int(mtime_ns))


@lru_cache(maxsize=4096)
def _is_binary_cached(path_str: str, size: int, mtime_ns: int) -> bool:
    file_path = Path(path_str)
    return _is_binary_uncached(file_path)


def _is_binary_uncached(file_path: Path) -> bool:
    extension_decision = classify_by_extension(file_path)
    if extension_decision is not None:
        return extension_decision

    try:
        sample = read_file_sample(file_path, HEURISTIC_SAMPLE_SIZE)
    except Exception as exc:
        logger.error("%sUnable to read sample from %s: %s%s", Fore.RED, file_path, exc, Style.RESET_ALL)
        return is_binary_alternative(file_path)

    heuristic_decision = analyse_sample(sample)
    if heuristic_decision is not None:
        return heuristic_decision

    magic_decision = _detect_via_magic(sample, file_path)
    if magic_decision is not None:
        return magic_decision

    return is_binary_alternative(file_path, sample=sample)


def is_binary(file_path: Path) -> bool:
    """Determine whether ``file_path`` should be treated as binary."""

    key = _stat_key(file_path)
    if key is None:
        return is_binary_alternative(file_path)

    return _is_binary_cached(*key)
