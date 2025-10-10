"""Utilities for removing legacy LLM/AI configuration artifacts."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Iterable, List
import shutil

logger = logging.getLogger(__name__)

LEGACY_SETTING_GROUPS = {
    "llm",
    "llm_api",
    "ai_integration",
    "ai",
    "openai",
    "anthropic",
}

LEGACY_SETTING_KEY_PREFIXES = (
    "llm/",
    "llm_api/",
    "ai/",
    "ai_api/",
    "openai/",
    "anthropic/",
)

LEGACY_SETTING_KEYS = {
    "llm_api_key",
    "llm/model",
    "llm/provider",
    "llm/enabled",
    "llm/api_key",
    "ai/api_key",
    "ai/provider",
    "ai/model",
    "ai/enabled",
    "ai_api/api_key",
    "openai/api_key",
    "anthropic/api_key",
}

LEGACY_FILES = (
    "llm_settings.ini",
    "llm_api_settings.ini",
    "ai_settings.ini",
    "llm_config.json",
    "ai_config.json",
)

LEGACY_DIRECTORIES = {
    "llm",
    "llm_cache",
    "llm_api",
    "ai_integration",
}


def _remove_paths(paths: Iterable[Path], removed: List[str]) -> None:
    for path in paths:
        try:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
                if not path.exists():
                    removed.append(str(path))
            elif path.exists():
                path.unlink()
                removed.append(str(path))
        except Exception as exc:
            logger.warning("Failed to remove legacy file '%s': %s", path, exc)


def _candidate_config_dirs() -> List[Path]:
    home = Path.home()
    candidates = []

    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidates.append(Path(appdata) / "Samuraizer")
        candidates.append(home / "AppData" / "Roaming" / "Samuraizer")
    else:
        candidates.append(home / ".config" / "Samuraizer")

    candidates.append(home / ".samuraizer")
    candidates.append(Path.cwd() / ".samuraizer")
    return candidates


def remove_legacy_llm_artifacts() -> None:
    """Remove persisted configuration belonging to the deprecated LLM feature."""

    removed_items: List[str] = []

    try:
        from PyQt6.QtCore import QSettings

        settings = QSettings()

        for group in list(settings.childGroups()):
            if group.lower() in LEGACY_SETTING_GROUPS:
                settings.remove(group)
                removed_items.append(f"settings-group:{group}")

        for key in list(settings.allKeys()):
            lower_key = key.lower()
            if (
                lower_key in LEGACY_SETTING_KEYS
                or any(lower_key.startswith(prefix) for prefix in LEGACY_SETTING_KEY_PREFIXES)
            ):
                settings.remove(key)
                removed_items.append(f"settings-key:{key}")

        if removed_items:
            settings.sync()
    except ImportError:
        logger.debug("Qt is not available; skipping QSettings cleanup for legacy LLM data.")
    except Exception as exc:
        logger.warning("Failed to clean legacy LLM settings: %s", exc)

    legacy_paths: List[Path] = []
    for base in _candidate_config_dirs():
        try:
            if not base.exists():
                continue
            legacy_paths.extend(base / name for name in LEGACY_FILES)

            for child in base.iterdir():
                if child.name.lower() in LEGACY_DIRECTORIES:
                    legacy_paths.append(child)
        except Exception as exc:
            logger.debug("Failed to inspect '%s' for legacy artifacts: %s", base, exc)

    _remove_paths(legacy_paths, removed_items)

    if removed_items:
        logger.info("Removed legacy LLM configuration artifacts: %s", ", ".join(removed_items))
