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


__all__ = [
    "legacy_directories",
    "merge_legacy_exclusions",
    "migrate_from_legacy_files",
    "migrate_timezone_json",
]
