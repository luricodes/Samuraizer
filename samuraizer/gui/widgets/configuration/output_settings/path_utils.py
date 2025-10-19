from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

__all__ = [
    "DEFAULT_BASENAME",
    "extension_for_format",
    "sanitize_filename",
    "normalise_output_path",
    "validate_output_path",
    "derive_default_output_path",
]

_DEFAULT_EXTENSION = ".json"
_DEFAULT_FORMAT_EXTENSION_MAP = {
    "json": ".json",
    "yaml": ".yaml",
    "yml": ".yaml",
    "xml": ".xml",
    "jsonl": ".jsonl",
    "dot": ".dot",
    "csv": ".csv",
    "s-expression": ".sexp",
    "sexp": ".sexp",
    "messagepack": ".msgpack",
    "msgpack": ".msgpack",
}

_SANITIZE_PATTERN = re.compile(r"[^\w\-]+")
DEFAULT_BASENAME = "analysis"


def extension_for_format(format_name: Optional[str]) -> str:
    """Return the canonical file extension for a given output format."""

    if not format_name:
        return _DEFAULT_EXTENSION
    key = str(format_name).strip().lower()
    if not key:
        return _DEFAULT_EXTENSION
    return _DEFAULT_FORMAT_EXTENSION_MAP.get(key, _DEFAULT_EXTENSION)


def sanitize_filename(value: Optional[str]) -> str:
    """Normalise a filename fragment for safe filesystem usage."""

    if not value:
        return DEFAULT_BASENAME
    candidate = _SANITIZE_PATTERN.sub("-", value.strip())
    candidate = candidate.strip("-_")
    return candidate or DEFAULT_BASENAME


def normalise_output_path(path: str) -> str:
    """Expand user tokens and resolve a path without requiring existence."""

    candidate = Path(path).expanduser()
    try:
        # ``strict=False`` avoids raising when the final path does not exist yet.
        resolved = candidate.resolve(strict=False)
    except (OSError, RuntimeError):  # pragma: no cover - defensive
        resolved = candidate.absolute()
    return str(resolved)


def _nearest_existing_directory(directory: Path) -> Optional[Path]:
    cursor = directory
    while True:
        if cursor.exists():
            return cursor if cursor.is_dir() else None
        parent = cursor.parent
        if parent == cursor:
            return None
        cursor = parent


def validate_output_path(path: str) -> bool:
    """Check whether an output path targets a writable directory."""

    if not path:
        return False
    try:
        candidate = Path(path).expanduser()
    except (TypeError, ValueError):
        return False

    directory = candidate.parent
    if not str(directory):
        return False

    try:
        directory = directory.resolve(strict=False)
    except (OSError, RuntimeError):  # pragma: no cover - defensive
        directory = directory.absolute()

    if directory.exists():
        return directory.is_dir() and os.access(directory, os.W_OK)

    ancestor = _nearest_existing_directory(directory)
    if ancestor is None:
        return False
    return os.access(ancestor, os.W_OK)


def derive_default_output_path(
    repository_path: Optional[str], filename: str, extension: str
) -> Optional[str]:
    """Compute a sensible default output path using repository context."""

    sanitized_name = sanitize_filename(filename)
    ext = extension if extension.startswith(".") else f".{extension}"

    candidate_dirs = []
    if repository_path:
        repo_dir = Path(repository_path).expanduser()
        candidate_dirs.append(repo_dir)
    candidate_dirs.extend([Path.cwd(), Path.home()])

    seen = set()
    for directory in candidate_dirs:
        try:
            directory = directory.resolve(strict=False)
        except (OSError, RuntimeError):  # pragma: no cover - defensive
            directory = directory.absolute()
        directory_key = str(directory)
        if directory_key in seen:
            continue
        seen.add(directory_key)
        if not directory.exists() or not directory.is_dir():
            continue
        if not os.access(directory, os.W_OK):
            continue
        return str((directory / sanitized_name).with_suffix(ext))
    return None
