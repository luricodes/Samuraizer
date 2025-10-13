# samuraizer/backend/services/config_services.py

"""Central access to configuration defaults derived from the unified manager."""

from __future__ import annotations

from typing import Any, Dict

from samuraizer.config import ConfigurationManager

config_manager = ConfigurationManager()


def _current_config() -> Dict[str, Any]:
    return config_manager.get_active_profile_config()


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


CACHE_DB_FILE = ".repo_structure_cache.db"
DEFAULT_EXCLUDED_FOLDERS = config_manager.exclusion_config.get_excluded_folders()
DEFAULT_EXCLUDED_FILES = config_manager.exclusion_config.get_excluded_files()
DEFAULT_IMAGE_EXTENSIONS = config_manager.exclusion_config.get_image_extensions()

__all__ = [
    "CACHE_DB_FILE",
    "DEFAULT_EXCLUDED_FOLDERS",
    "DEFAULT_EXCLUDED_FILES",
    "DEFAULT_IMAGE_EXTENSIONS",
    "config_manager",
    "get_default_analysis_settings",
    "get_default_cache_settings",
    "get_default_output_settings",
    "get_default_timezone_settings",
    "get_default_max_file_size_mb",
]
