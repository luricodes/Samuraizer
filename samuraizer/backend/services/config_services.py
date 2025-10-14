# samuraizer/backend/services/config_services.py

"""Central access to configuration defaults derived from the unified manager."""

from __future__ import annotations

from typing import Any, Dict, List, Set

from samuraizer.config.unified import UnifiedConfigManager

CACHE_DB_FILE = ".repo_structure_cache.db"


def _manager() -> UnifiedConfigManager:
    return UnifiedConfigManager()


def _current_config() -> Dict[str, Any]:
    return _manager().get_active_profile_config()


def get_default_max_file_size_mb() -> int:
    return int(_current_config().get("analysis", {}).get("max_file_size_mb", 50))


def get_default_analysis_settings() -> Dict[str, Any]:
    return _current_config().get("analysis", {})


def get_default_cache_settings() -> Dict[str, Any]:
    return _current_config().get("cache", {})


def get_default_output_settings() -> Dict[str, Any]:
    return _current_config().get("output", {})


def get_default_timezone_settings() -> Dict[str, Any]:
    return _current_config().get("timezone", {})


def get_excluded_folders() -> Set[str]:
    exclusions = _current_config().get("exclusions", {})
    folders = exclusions.get("folders", {}).get("exclude", [])
    return set(str(folder) for folder in folders)


def get_excluded_files() -> Set[str]:
    exclusions = _current_config().get("exclusions", {})
    files = exclusions.get("files", {}).get("exclude", [])
    return set(str(file) for file in files)


def get_exclude_patterns() -> List[str]:
    exclusions = _current_config().get("exclusions", {})
    patterns = exclusions.get("patterns", {}).get("exclude", [])
    return [str(pattern) for pattern in patterns]


def get_image_extensions() -> Set[str]:
    exclusions = _current_config().get("exclusions", {})
    images = exclusions.get("image_extensions", {}).get("include", [])
    return {str(image).lower() for image in images}


__all__ = [
    "CACHE_DB_FILE",
    "get_default_analysis_settings",
    "get_default_cache_settings",
    "get_default_output_settings",
    "get_default_timezone_settings",
    "get_default_max_file_size_mb",
    "get_excluded_folders",
    "get_excluded_files",
    "get_exclude_patterns",
    "get_image_extensions",
]
