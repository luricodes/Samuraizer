from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List

import yaml

from .exceptions import ConfigMigrationError

logger = logging.getLogger(__name__)


def legacy_directories() -> List[Path]:
    legacy_paths: List[Path] = []
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            legacy_paths.append(Path(appdata) / "Samuraizer")
    else:
        legacy_paths.append(Path.home() / ".config" / "Samuraizer")
    return legacy_paths


def merge_legacy_exclusions(
    raw_config: Dict[str, Any],
    folders: Iterable[str],
    files: Iterable[str],
    patterns: Iterable[str],
    images: Iterable[str],
) -> None:
    exclusions = raw_config.setdefault("exclusions", {})
    folders_section = exclusions.setdefault("folders", {}).setdefault("exclude", [])
    files_section = exclusions.setdefault("files", {}).setdefault("exclude", [])
    patterns_section = exclusions.setdefault("patterns", {}).setdefault("exclude", [])
    images_section = exclusions.setdefault("image_extensions", {}).setdefault(
        "include", []
    )

    folders_section[:] = list(dict.fromkeys(folders_section + list(folders)))
    files_section[:] = list(dict.fromkeys(files_section + list(files)))
    patterns_section[:] = list(dict.fromkeys(patterns_section + list(patterns)))
    images_section[:] = list(dict.fromkeys(images_section + list(images)))


def migrate_from_legacy_files(raw_config: Dict[str, Any]) -> bool:
    migrated = False
    for legacy_dir in legacy_directories():
        exclusions_file = legacy_dir / "exclusions.yaml"
        if not exclusions_file.exists():
            continue
        try:
            with exclusions_file.open("r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            folders = data.get("exclusions", {}).get("folders", [])
            files = data.get("exclusions", {}).get("files", [])
            patterns = data.get("exclusions", {}).get("patterns", [])
            images = data.get("image_extensions", [])
            merge_legacy_exclusions(raw_config, folders, files, patterns, images)
            migrated = True
        except Exception as exc:  # pragma: no cover
            raise ConfigMigrationError(
                f"Failed to migrate legacy exclusions from {exclusions_file}: {exc}"
            ) from exc
    return migrated


def migrate_timezone_json(raw_config: Dict[str, Any]) -> bool:
    timezone_file = Path.home() / ".samuraizer" / "timezone_config.json"
    if not timezone_file.exists():
        return False
    try:
        with timezone_file.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        timezone_section = raw_config.setdefault("timezone", {})
        timezone_section["use_utc"] = bool(data.get("use_utc", False))
        timezone_section["repository_timezone"] = data.get("repository_timezone")
        return True
    except Exception as exc:  # pragma: no cover
        raise ConfigMigrationError(
            f"Failed to migrate timezone configuration from {timezone_file}: {exc}"
        ) from exc


def migrate_qsettings(raw_config: Dict[str, Any]) -> bool:
    """Attempt to migrate settings persisted via QSettings."""
    try:
        from PyQt6.QtCore import QSettings  # type: ignore
    except Exception as exc:  # pragma: no cover
        logger.debug("Qt settings migration skipped: %s", exc)
        return False

    settings = QSettings()
    if not settings.allKeys():
        return False

    migrated = False
    analysis = raw_config.setdefault("analysis", {})
    cache = raw_config.setdefault("cache", {})
    output = raw_config.setdefault("output", {})
    theme = raw_config.setdefault("theme", {})

    def _set(container: Dict[str, Any], key: str, value: Any) -> None:
        nonlocal migrated
        container[key] = value
        migrated = True

    max_file_size = settings.value("analysis/max_file_size", None, type=int)
    if max_file_size is not None:
        _set(analysis, "max_file_size_mb", int(max_file_size))

    include_binary = settings.value("analysis/include_binary", None, type=bool)
    if include_binary is not None:
        _set(analysis, "include_binary", bool(include_binary))

    follow_symlinks = settings.value("analysis/follow_symlinks", None, type=bool)
    if follow_symlinks is not None:
        _set(analysis, "follow_symlinks", bool(follow_symlinks))

    encoding = settings.value("analysis/encoding", None)
    if encoding:
        _set(analysis, "encoding", str(encoding))

    thread_count = settings.value("analysis/thread_count", None, type=int)
    if thread_count is not None and thread_count > 0:
        _set(analysis, "threads", int(thread_count))

    disable_cache = settings.value("settings/disable_cache", None, type=bool)
    if disable_cache is not None:
        _set(analysis, "cache_enabled", not bool(disable_cache))

    cache_path = settings.value("settings/cache_path", None)
    if cache_path:
        _set(cache, "path", str(cache_path))

    cache_cleanup = settings.value("settings/cache_cleanup", None, type=int)
    if cache_cleanup is not None and cache_cleanup > 0:
        _set(cache, "cleanup_days", int(cache_cleanup))

    cache_size = settings.value("settings/max_cache_size", None, type=int)
    if cache_size is not None and cache_size > 0:
        _set(cache, "size_limit_mb", int(cache_size))

    default_format = settings.value("output/format", None)
    if (
        default_format
        and default_format.strip()
        and default_format.lower() != "choose output format"
    ):
        _set(analysis, "default_format", default_format.strip().lower())

    streaming_enabled = settings.value("output/streaming", None, type=bool)
    if streaming_enabled is not None:
        _set(output, "streaming", bool(streaming_enabled))

    include_summary = settings.value("output/include_summary", None, type=bool)
    if include_summary is not None:
        _set(analysis, "include_summary", bool(include_summary))

    pretty_print = settings.value("output/pretty_print", None, type=bool)
    if pretty_print is not None:
        _set(output, "pretty_print", bool(pretty_print))

    compression = settings.value("output/use_compression", None, type=bool)
    if compression is not None:
        _set(output, "compression", bool(compression))

    theme_name = settings.value("theme", None)
    if theme_name:
        _set(theme, "name", str(theme_name).lower())

    return migrated


__all__ = [
    "legacy_directories",
    "merge_legacy_exclusions",
    "migrate_from_legacy_files",
    "migrate_timezone_json",
    "migrate_qsettings",
]
