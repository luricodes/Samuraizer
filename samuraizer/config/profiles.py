from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Set

_PROFILE_SECTION_KEY_MAP: Dict[str, Set[str]] = {
    "analysis": {
        "default_format",
        "max_file_size_mb",
        "threads",
        "follow_symlinks",
        "include_binary",
        "encoding",
        "hash_algorithm",
        "cache_enabled",
        "include_summary",
    },
    "output": {"compression", "streaming", "pretty_print"},
    "cache": {"path", "size_limit_mb", "cleanup_days"},
    "theme": {"name"},
    "timezone": {"use_utc", "repository_timezone"},
}


def _apply_flat_profile_keys(
    merged: Dict[str, Any], profile_overrides: Dict[str, Any]
) -> Dict[str, Any]:
    sentinel = object()
    for section, keys in _PROFILE_SECTION_KEY_MAP.items():
        override_section = profile_overrides.get(section)
        if not isinstance(override_section, dict):
            override_section = {}
        section_dict = merged.get(section)
        if not isinstance(section_dict, dict):
            section_dict = {}
            merged[section] = section_dict
        for key in keys:
            if key in override_section:
                merged.pop(key, None)
                continue
            value = sentinel
            if key in profile_overrides:
                value = deepcopy(profile_overrides[key])
                merged.pop(key, None)
            else:
                value = merged.pop(key, sentinel)
            if value is sentinel:
                continue
            section_dict[key] = value
    return merged


def _apply_profile_customisations(
    merged: Dict[str, Any], profile_overrides: Dict[str, Any]
) -> Dict[str, Any]:
    exclusions_overrides = profile_overrides.get("exclusions")
    if isinstance(exclusions_overrides, dict):
        folders_extra = exclusions_overrides.get("additional_folders")
        if folders_extra:
            existing = (
                merged.setdefault("exclusions", {})
                .setdefault("folders", {})
                .setdefault("exclude", [])
            )
            merged["exclusions"]["folders"]["exclude"] = list(
                dict.fromkeys(existing + folders_extra)
            )
        files_extra = exclusions_overrides.get("additional_files")
        if files_extra:
            existing = (
                merged.setdefault("exclusions", {})
                .setdefault("files", {})
                .setdefault("exclude", [])
            )
            merged["exclusions"]["files"]["exclude"] = list(
                dict.fromkeys(existing + files_extra)
            )
        patterns_extra = exclusions_overrides.get("additional_patterns")
        if patterns_extra:
            existing = (
                merged.setdefault("exclusions", {})
                .setdefault("patterns", {})
                .setdefault("exclude", [])
            )
            merged["exclusions"]["patterns"]["exclude"] = list(
                dict.fromkeys(existing + patterns_extra)
            )
        image_extra = exclusions_overrides.get("additional_image_extensions")
        if image_extra:
            existing = (
                merged.setdefault("exclusions", {})
                .setdefault("image_extensions", {})
                .setdefault("include", [])
            )
            merged["exclusions"]["image_extensions"]["include"] = list(
                dict.fromkeys(existing + image_extra)
            )
    merged = _apply_flat_profile_keys(merged, profile_overrides)
    return merged


def _rehome_flat_keys(container: Dict[str, Any]) -> bool:
    corrected = False
    for section, keys in _PROFILE_SECTION_KEY_MAP.items():
        for key in keys:
            if key not in container:
                continue
            value = container.pop(key)
            section_dict = container.get(section)
            if not isinstance(section_dict, dict):
                section_dict = {}
                container[section] = section_dict
            section_dict[key] = value
            corrected = True
    return corrected


def _resolve_default_base(config: Dict[str, Any]) -> Dict[str, Any]:
    return {k: deepcopy(v) for k, v in config.items() if k != "profiles"}


def normalise_profile_sections(data: Dict[str, Any]) -> bool:
    corrected = _rehome_flat_keys(data)
    profiles = data.get("profiles", {})
    if isinstance(profiles, dict):
        for profile in profiles.values():
            if isinstance(profile, dict) and _rehome_flat_keys(profile):
                corrected = True
    return corrected


__all__ = [
    "_PROFILE_SECTION_KEY_MAP",
    "_apply_flat_profile_keys",
    "_apply_profile_customisations",
    "_rehome_flat_keys",
    "_resolve_default_base",
    "normalise_profile_sections",
]
