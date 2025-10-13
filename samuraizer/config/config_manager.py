# samuraizer/config/config_manager.py

"""Unified configuration management for Samuraizer.

This module implements a modern configuration stack based on a single TOML
configuration file with profile support, validation and basic migration
capabilities.  The :class:`UnifiedConfigManager` class is responsible for
loading, validating and persisting configuration data.  The public
:class:`ConfigurationManager` exposes a backwards compatible façade used by the
rest of the application (CLI, GUI, backend services).
"""

from __future__ import annotations

import logging
import os
import shutil
import threading
import weakref
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, ClassVar, Dict, Iterable, List, Optional, Set, Tuple, TypeVar, Generic

try:  # Python 3.11+
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - fallback for Python <3.11
    import tomli as tomllib  # type: ignore[no-redef]

try:
    from jsonschema import Draft202012Validator, ValidationError
except ModuleNotFoundError as exc:  # pragma: no cover - dependency must be installed
    raise ImportError(
        "The 'jsonschema' package is required for configuration validation. "
        "Install it with 'pip install jsonschema' inside your Samuraizer environment."
    ) from exc
import yaml
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)

WidgetType = TypeVar("WidgetType")


class _Listener:
    """Wrapper that stores callbacks via weak references when possible."""

    __slots__ = ("_ref", "_strong")

    def __init__(self, callback: Callable[[], None]) -> None:
        try:
            if hasattr(callback, "__self__") and hasattr(callback, "__func__"):
                self._ref = weakref.WeakMethod(callback)  # type: ignore[arg-type]
            else:
                self._ref = weakref.ref(callback)
            self._strong: Optional[Callable[[], None]] = None
        except TypeError:
            # Fallback for callables that do not support weak references.
            self._ref = None
            self._strong = callback

    def get(self) -> Optional[Callable[[], None]]:
        if self._ref is None:
            return self._strong
        return self._ref()

    def matches(self, callback: Callable[[], None]) -> bool:
        if self._ref is None:
            return self._strong is callback
        target = self._ref()
        return target is callback

# ---------------------------------------------------------------------------
# Defaults & schema definitions
# ---------------------------------------------------------------------------

DEFAULT_CONFIG_TOML = """\
# Version tracking for migrations
config_version = "1.0"

[analysis]
# Default analysis settings
default_format = "json"
max_file_size_mb = 50
threads = 4
follow_symlinks = false
include_binary = false
encoding = "auto"
hash_algorithm = "xxhash"
cache_enabled = true
include_summary = true

[cache]
path = "~/.cache/samurai"
size_limit_mb = 1000
cleanup_days = 30

[exclusions.folders]
exclude = ["node_modules", ".git", "__pycache__", ".venv", "dist", "build"]

[exclusions.files]
exclude = ["*.tmp", "config.json", ".repo_structure_cache", "package-lock.json", "favicon.ico"]

[exclusions.patterns]
exclude = ["*.pyc", "*.pyo", "*.pyd", ".DS_Store", "Thumbs.db"]

[exclusions.image_extensions]
include = [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp", ".tiff", ".ico"]

[output]
compression = false
streaming = false  # auto-enabled for jsonl, msgpack
pretty_print = true

[theme]
name = "dark"  # only applies to gui mode

[timezone]
use_utc = false

[profiles.work]
inherit = "default"
cache_enabled = false
threads = 8

[profiles.work.exclusions]
additional_folders = ["dist", "build", ".next"]

[profiles.portable]
inherit = "default"
cache_enabled = false
max_file_size_mb = 10

[profiles.portable.output]
compression = true
"""

DEFAULT_CONFIG: Dict[str, Any] = tomllib.loads(DEFAULT_CONFIG_TOML)

CONFIG_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "config_version": {"type": "string"},
        "analysis": {
            "type": "object",
            "properties": {
                "default_format": {"type": "string"},
                "max_file_size_mb": {"type": "integer", "minimum": 0},
                "threads": {"type": "integer", "minimum": 1},
                "follow_symlinks": {"type": "boolean"},
                "include_binary": {"type": "boolean"},
                "encoding": {"type": "string"},
                "hash_algorithm": {"type": "string"},
                "cache_enabled": {"type": "boolean"},
                "include_summary": {"type": "boolean"},
            },
            "required": [
                "default_format",
                "max_file_size_mb",
                "threads",
                "follow_symlinks",
                "include_binary",
                "encoding",
                "hash_algorithm",
                "cache_enabled",
                "include_summary",
            ],
            "additionalProperties": True,
        },
        "cache": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "size_limit_mb": {"type": "integer", "minimum": 0},
                "cleanup_days": {"type": "integer", "minimum": 0},
            },
            "required": ["path", "size_limit_mb", "cleanup_days"],
            "additionalProperties": True,
        },
        "exclusions": {
            "type": "object",
            "properties": {
                "folders": {
                    "type": "object",
                    "properties": {
                        "exclude": {
                            "type": "array",
                            "items": {"type": "string"},
                        }
                    },
                    "required": ["exclude"],
                },
                "files": {
                    "type": "object",
                    "properties": {
                        "exclude": {
                            "type": "array",
                            "items": {"type": "string"},
                        }
                    },
                    "required": ["exclude"],
                },
                "patterns": {
                    "type": "object",
                    "properties": {
                        "exclude": {
                            "type": "array",
                            "items": {"type": "string"},
                        }
                    },
                    "required": ["exclude"],
                },
                "image_extensions": {
                    "type": "object",
                    "properties": {
                        "include": {
                            "type": "array",
                            "items": {"type": "string"},
                        }
                    },
                    "required": ["include"],
                },
            },
            "required": ["folders", "files", "patterns", "image_extensions"],
            "additionalProperties": True,
        },
        "output": {
            "type": "object",
            "properties": {
                "compression": {"type": "boolean"},
                "streaming": {"type": "boolean"},
                "pretty_print": {"type": "boolean"},
            },
            "required": ["compression", "streaming", "pretty_print"],
        },
        "theme": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
        "timezone": {
            "type": "object",
            "properties": {
                "use_utc": {"type": "boolean"},
                "repository_timezone": {
                    "type": "string",
                    "minLength": 1,
                },
            },
            "required": ["use_utc"],
        },
        "profiles": {"type": "object"},
    },
    "required": [
        "config_version",
        "analysis",
        "cache",
        "exclusions",
        "output",
        "theme",
        "timezone",
    ],
    "additionalProperties": True,
}

_validator = Draft202012Validator(CONFIG_SCHEMA)


class ConfigError(Exception):
    """Base exception for configuration errors."""


class ConfigValidationError(ConfigError):
    """Raised when configuration validation fails."""


class ConfigMigrationError(ConfigError):
    """Raised when configuration migration fails."""


class ConfigIOError(ConfigError):
    """Raised when configuration read/write fails."""


@dataclass(frozen=True)
class ProfileResolutionResult:
    name: str
    config: Dict[str, Any]


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\"", "\\\"")


def _format_toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    if isinstance(value, str):
        return f'"{_toml_escape(value)}"'
    if isinstance(value, list):
        return "[" + ", ".join(_format_toml_value(v) for v in value) + "]"
    if value is None:
        return "null"
    raise TypeError(f"Unsupported value type for TOML serialization: {type(value)!r}")


def _iter_dict_items(data: Dict[str, Any]) -> Iterable[Tuple[str, Any]]:
    for key, value in data.items():
        yield key, value


def _toml_dumps(data: Dict[str, Any]) -> str:
    lines: List[str] = []

    def write_table(prefix: str, table: Dict[str, Any]) -> None:
        scalar_items: List[Tuple[str, Any]] = []
        sub_tables: List[Tuple[str, Dict[str, Any]]] = []

        for key, value in _iter_dict_items(table):
            if isinstance(value, dict):
                sub_tables.append((key, value))
            else:
                scalar_items.append((key, value))

        if prefix:
            lines.append(f"[{prefix}]")

        for key, value in scalar_items:
            lines.append(f"{key} = {_format_toml_value(value)}")

        if scalar_items and sub_tables:
            lines.append("")

        for key, value in sub_tables:
            new_prefix = f"{prefix}.{key}" if prefix else key
            write_table(new_prefix, value)

    write_table("", data)
    return "\n".join(lines) + "\n"


def _deep_merge(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _apply_profile_customisations(
    merged: Dict[str, Any], profile_overrides: Dict[str, Any]
) -> Dict[str, Any]:
    exclusions_overrides = profile_overrides.get("exclusions")
    if isinstance(exclusions_overrides, dict):
        folders_extra = exclusions_overrides.get("additional_folders")
        if folders_extra:
            existing = merged.setdefault("exclusions", {}).setdefault("folders", {}).setdefault(
                "exclude", []
            )
            merged["exclusions"]["folders"]["exclude"] = list(
                dict.fromkeys(existing + folders_extra)
            )
        files_extra = exclusions_overrides.get("additional_files")
        if files_extra:
            existing = merged.setdefault("exclusions", {}).setdefault("files", {}).setdefault(
                "exclude", []
            )
            merged["exclusions"]["files"]["exclude"] = list(
                dict.fromkeys(existing + files_extra)
            )
        patterns_extra = exclusions_overrides.get("additional_patterns")
        if patterns_extra:
            existing = merged.setdefault("exclusions", {}).setdefault("patterns", {}).setdefault(
                "exclude", []
            )
            merged["exclusions"]["patterns"]["exclude"] = list(
                dict.fromkeys(existing + patterns_extra)
            )
        image_extra = exclusions_overrides.get("additional_image_extensions")
        if image_extra:
            existing = merged.setdefault("exclusions", {}).setdefault("image_extensions", {}).setdefault(
                "include", []
            )
            merged["exclusions"]["image_extensions"]["include"] = list(
                dict.fromkeys(existing + image_extra)
            )
    return merged


def _resolve_default_base(config: Dict[str, Any]) -> Dict[str, Any]:
    return {k: deepcopy(v) for k, v in config.items() if k != "profiles"}


# ---------------------------------------------------------------------------
# Unified configuration manager
# ---------------------------------------------------------------------------


class UnifiedConfigManager:
    """Singleton configuration manager handling TOML-based configuration."""

    _instance: ClassVar[Optional["UnifiedConfigManager"]] = None
    _lock: ClassVar[threading.RLock] = threading.RLock()

    def __new__(cls) -> "UnifiedConfigManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        self._config_path: Path = self._determine_default_path()
        self._raw_config: Dict[str, Any] = deepcopy(DEFAULT_CONFIG)
        self._active_profile: str = "default"
        self._profile_cache: Dict[str, ProfileResolutionResult] = {}
        self._change_listeners: List["_Listener"] = []
        self._load_or_create()
        self._initialized = True

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _determine_default_path() -> Path:
        if os.name == "nt":
            appdata = os.environ.get("APPDATA")
            base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
            return base / "samurai" / "config.toml"
        return Path.home() / ".config" / "samurai" / "config.toml"

    @property
    def config_path(self) -> Path:
        return self._config_path

    # ------------------------------------------------------------------
    # Loading / saving
    # ------------------------------------------------------------------

    def _ensure_directory(self) -> None:
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:  # pragma: no cover - fatal configuration error
            raise ConfigIOError(f"Unable to create configuration directory: {exc}") from exc

    def _backup_existing_config(self, suffix: str = "backup") -> Optional[Path]:
        if not self._config_path.exists():
            return None
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        backup_name = f"{self._config_path.name}.{suffix}.{timestamp}.bak"
        backup_path = self._config_path.with_name(backup_name)
        try:
            shutil.copy2(self._config_path, backup_path)
            return backup_path
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Failed to create configuration backup at %s: %s", backup_path, exc)
            return None

    def _write_config(self) -> None:
        self._ensure_directory()
        try:
            serialized = _toml_dumps(self._raw_config)
            self._config_path.write_text(serialized, encoding="utf-8")
        except Exception as exc:  # pragma: no cover - fatal configuration error
            raise ConfigIOError(f"Failed to write configuration file: {exc}") from exc

    def _load_or_create(self) -> None:
        self._ensure_directory()
        if not self._config_path.exists():
            logger.info("Creating default configuration at %s", self._config_path)
            self._config_path.write_text(DEFAULT_CONFIG_TOML, encoding="utf-8")
            self._raw_config = deepcopy(DEFAULT_CONFIG)
            if self._normalise_timezone(self._raw_config):
                self._write_config()
            return

        try:
            with self._config_path.open("rb") as fh:
                loaded = tomllib.load(fh)
            if not isinstance(loaded, dict):
                raise ConfigValidationError("Configuration root must be a table")
            self._raw_config = _deep_merge(DEFAULT_CONFIG, loaded)
            timezone_fixed = self._normalise_timezone(self._raw_config)
            self._validate(self._raw_config)
            if timezone_fixed:
                self._write_config()
        except FileNotFoundError:
            self._raw_config = deepcopy(DEFAULT_CONFIG)
            self._normalise_timezone(self._raw_config)
        except tomllib.TOMLDecodeError as exc:
            logger.error("Configuration file %s is not valid TOML: %s", self._config_path, exc)
            backup_path = self._backup_existing_config(suffix="corrupt")
            if backup_path:
                logger.error("Corrupt configuration backed up to %s", backup_path)
            self._raw_config = deepcopy(DEFAULT_CONFIG)
            self._normalise_timezone(self._raw_config)
            self._write_config()
            logger.info("Restored default configuration after TOML decode failure")
        except ValidationError as exc:
            raise ConfigValidationError(f"Invalid configuration: {exc.message}") from exc
        except Exception as exc:  # pragma: no cover - fatal configuration error
            raise ConfigIOError(f"Unable to load configuration: {exc}") from exc

    def reload(self, config_path: Optional[Path] = None, profile: Optional[str] = None) -> None:
        with self._lock:
            if config_path is not None:
                self._config_path = Path(config_path).expanduser().resolve()
            self._profile_cache.clear()
            self._load_or_create()
            if profile:
                self.set_active_profile(profile)
            else:
                self._active_profile = "default"
            self._notify_change()

    def save(self) -> None:
        with self._lock:
            self._write_config()
            self._notify_change()

    # ------------------------------------------------------------------
    # Validation & profiles
    # ------------------------------------------------------------------

    def _validate(self, data: Dict[str, Any]) -> None:
        errors = sorted(_validator.iter_errors(data), key=lambda e: e.path)
        if errors:
            first = errors[0]
            location = ".".join(str(part) for part in first.path)
            message = f"{location}: {first.message}" if location else first.message
            raise ConfigValidationError(message)
        self._validate_profiles(data)

    def _validate_profiles(self, data: Dict[str, Any]) -> None:
        profiles = data.get("profiles", {})
        if not profiles:
            return
        for name, profile in profiles.items():
            inherit = profile.get("inherit", "default")
            if inherit != "default" and inherit not in profiles:
                raise ConfigValidationError(f"Profile '{name}' inherits from unknown profile '{inherit}'")
        for name in profiles:
            self._detect_cycle(name, profiles)

    def _detect_cycle(self, start: str, profiles: Dict[str, Dict[str, Any]]) -> None:
        seen: Set[str] = set()
        current = start
        while True:
            if current == "default":
                return
            if current in seen:
                raise ConfigValidationError(f"Circular inheritance detected at profile '{current}'")
            seen.add(current)
            parent = profiles[current].get("inherit", "default")
            if parent == "default":
                return
            if parent not in profiles:
                raise ConfigValidationError(
                    f"Profile '{current}' inherits from unknown profile '{parent}'"
                )
            current = parent

    def set_active_profile(self, profile: str) -> None:
        resolved = self.resolve_profile(profile)
        self._active_profile = resolved.name
        self._notify_change()

    @property
    def active_profile(self) -> str:
        return self._active_profile

    def resolve_profile(self, profile: Optional[str] = None) -> ProfileResolutionResult:
        profile_name = profile or self._active_profile or "default"
        if profile_name in self._profile_cache:
            return self._profile_cache[profile_name]

        with self._lock:
            base = _resolve_default_base(self._raw_config)
            profiles = self._raw_config.get("profiles", {})

            if profile_name in (None, "default"):
                result = ProfileResolutionResult("default", base)
                self._profile_cache[profile_name] = result
                return result

            profile_data = profiles.get(profile_name)
            if profile_data is None:
                raise ConfigError(f"Profile '{profile_name}' is not defined")

            inherit = profile_data.get("inherit", "default")
            parent_result = self.resolve_profile(inherit)
            overrides = {k: deepcopy(v) for k, v in profile_data.items() if k != "inherit"}
            merged = _deep_merge(parent_result.config, overrides)
            merged = _apply_profile_customisations(merged, overrides)
            result = ProfileResolutionResult(profile_name, merged)
            self._profile_cache[profile_name] = result
            return result

    def get_active_profile_config(self) -> Dict[str, Any]:
        return deepcopy(self.resolve_profile(self._active_profile).config)

    def get_raw_config(self) -> Dict[str, Any]:
        return deepcopy(self._raw_config)

    def validate_current(self) -> None:
        with self._lock:
            self._validate(self._raw_config)

    # ------------------------------------------------------------------
    # Mutation helpers used by façade classes
    # ------------------------------------------------------------------

    def _locate_section(self, path: str, create: bool = False, profile: Optional[str] = None) -> Dict[str, Any]:
        parts = path.split(".") if path else []
        if profile and profile != "default":
            root = self._raw_config.setdefault("profiles", {}).setdefault(profile, {})
        else:
            root = self._raw_config
        cursor = root
        for idx, part in enumerate(parts):
            last = idx == len(parts) - 1
            if last:
                return cursor
            cursor = cursor.setdefault(part, {}) if create else cursor[part]
            if not isinstance(cursor, dict):
                raise ConfigError(f"Configuration path '{path}' is not a table")
        return cursor

    def update_list(
        self,
        path: str,
        values: Iterable[str],
        action: str = "add",
        profile: Optional[str] = None,
    ) -> None:
        items = list(values)
        with self._lock:
            container = self._locate_section(path, create=True, profile=profile)
            key = path.split(".")[-1]
            current = container.get(key)
            if current is None:
                current = []
            if not isinstance(current, list):
                raise ConfigError(f"Configuration path '{path}' does not reference a list")
            if action == "add":
                merged = list(dict.fromkeys(current + items))
            elif action == "remove":
                merged = [value for value in current if value not in items]
            else:
                raise ValueError(f"Unknown action '{action}'")
            container[key] = merged
            self._write_config()
            self._profile_cache.clear()
            self._notify_change()

    def set_value(self, path: str, value: Any, profile: Optional[str] = None) -> None:
        with self._lock:
            parts = path.split(".")
            try:
                container = self._locate_section(
                    path,
                    create=value is not None,
                    profile=profile,
                )
            except KeyError:
                if value is None:
                    return
                raise
            key = parts[-1]
            if value is None:
                if key not in container:
                    return
                del container[key]
            else:
                container[key] = value
            self._write_config()
            self._profile_cache.clear()
            self._notify_change()

    def reset_to_defaults(self) -> None:
        with self._lock:
            self._raw_config = deepcopy(DEFAULT_CONFIG)
            self._normalise_timezone(self._raw_config)
            self._write_config()
            self._profile_cache.clear()
            self._active_profile = "default"
            self._notify_change()

    def add_change_listener(self, callback: Callable[[], None]) -> None:
        if not any(listener.matches(callback) for listener in self._change_listeners):
            self._change_listeners.append(_Listener(callback))

    def remove_change_listener(self, callback: Callable[[], None]) -> None:
        self._change_listeners = [
            listener for listener in self._change_listeners if not listener.matches(callback)
        ]

    def _notify_change(self) -> None:
        stale: List[_Listener] = []
        for listener in list(self._change_listeners):
            callback = listener.get()
            if callback is None:
                stale.append(listener)
                continue
            try:
                callback()
            except RuntimeError as exc:  # pragma: no cover - defensive
                if "wrapped C/C++ object" in str(exc):
                    logger.debug("Removing dead configuration listener: %s", exc)
                    stale.append(listener)
                else:
                    logger.error("Error in configuration change listener: %s", exc)
            except Exception as exc:  # pragma: no cover - best effort
                logger.error("Error in configuration change listener: %s", exc)
        if stale:
            for listener in stale:
                if listener in self._change_listeners:
                    self._change_listeners.remove(listener)

    # ------------------------------------------------------------------
    # Migration support
    # ------------------------------------------------------------------

    def migrate(self) -> bool:
        """Attempt to migrate configuration from legacy sources."""

        with self._lock:
            migrated = False
            legacy_dirs = self._legacy_directories()
            for legacy_dir in legacy_dirs:
                exclusions_file = legacy_dir / "exclusions.yaml"
                if exclusions_file.exists():
                    try:
                        with exclusions_file.open("r", encoding="utf-8") as fh:
                            data = yaml.safe_load(fh) or {}
                        folders = data.get("exclusions", {}).get("folders", [])
                        files = data.get("exclusions", {}).get("files", [])
                        patterns = data.get("exclusions", {}).get("patterns", [])
                        images = data.get("image_extensions", [])
                        self._merge_legacy_exclusions(folders, files, patterns, images)
                        migrated = True
                    except Exception as exc:
                        raise ConfigMigrationError(
                            f"Failed to migrate legacy exclusions from {exclusions_file}: {exc}"
                        ) from exc
            timezone_file = Path.home() / ".samuraizer" / "timezone_config.json"
            if timezone_file.exists():
                try:
                    import json

                    with timezone_file.open("r", encoding="utf-8") as fh:
                        data = json.load(fh)
                    timezone_section = self._raw_config.setdefault("timezone", {})
                    timezone_section["use_utc"] = bool(data.get("use_utc", False))
                    timezone_section["repository_timezone"] = data.get("repository_timezone")
                    migrated = True
                except Exception as exc:
                    raise ConfigMigrationError(
                        f"Failed to migrate timezone configuration from {timezone_file}: {exc}"
                    ) from exc
            if self._migrate_qsettings():
                migrated = True

            if migrated:
                backup_path = self._backup_existing_config(suffix="migration")
                self._write_config()
                self._profile_cache.clear()
                if backup_path:
                    logger.info("Existing configuration backed up to %s", backup_path)
                logger.info("Legacy configuration migrated into %s", self._config_path)
            else:
                logger.info("No legacy configuration files found for migration")
            return migrated

    def _legacy_directories(self) -> List[Path]:
        legacy_paths: List[Path] = []
        if os.name == "nt":
            appdata = os.environ.get("APPDATA")
            if appdata:
                legacy_paths.append(Path(appdata) / "Samuraizer")
        else:
            legacy_paths.append(Path.home() / ".config" / "Samuraizer")
        return legacy_paths

    def _merge_legacy_exclusions(
        self,
        folders: Iterable[str],
        files: Iterable[str],
        patterns: Iterable[str],
        images: Iterable[str],
    ) -> None:
        exclusions = self._raw_config.setdefault("exclusions", {})
        folders_section = exclusions.setdefault("folders", {}).setdefault("exclude", [])
        files_section = exclusions.setdefault("files", {}).setdefault("exclude", [])
        patterns_section = exclusions.setdefault("patterns", {}).setdefault("exclude", [])
        images_section = exclusions.setdefault("image_extensions", {}).setdefault("include", [])

        folders_section[:] = list(dict.fromkeys(folders_section + list(folders)))
        files_section[:] = list(dict.fromkeys(files_section + list(files)))
        patterns_section[:] = list(dict.fromkeys(patterns_section + list(patterns)))
        images_section[:] = list(dict.fromkeys(images_section + list(images)))

    def _migrate_qsettings(self) -> bool:
        """Attempt to migrate settings persisted via QSettings."""
        try:
            from PyQt6.QtCore import QSettings  # type: ignore
        except Exception as exc:  # pragma: no cover - PyQt may be unavailable in CLI environments
            logger.debug("Qt settings migration skipped: %s", exc)
            return False

        settings = QSettings()
        if not settings.allKeys():
            return False

        migrated = False
        analysis = self._raw_config.setdefault("analysis", {})
        cache = self._raw_config.setdefault("cache", {})
        output = self._raw_config.setdefault("output", {})
        theme = self._raw_config.setdefault("theme", {})

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
        if default_format and default_format.strip() and default_format.lower() != "choose output format":
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

    # ------------------------------------------------------------------
    # Export helpers
    # ------------------------------------------------------------------

    def export_profile(self, profile: Optional[str] = None) -> Dict[str, Any]:
        result = self.resolve_profile(profile)
        return deepcopy(result.config)

    def import_profile(self, name: str, data: Dict[str, Any], inherit: str = "default") -> None:
        if not name:
            raise ConfigError("Profile name must not be empty")
        if name == "default":
            raise ConfigError("The default profile cannot be overwritten")
        with self._lock:
            profiles = self._raw_config.setdefault("profiles", {})
            if name in profiles:
                raise ConfigError(f"Profile '{name}' already exists")
            profile_data = deepcopy(data)
            profile_data["inherit"] = inherit
            profiles[name] = profile_data
            self._normalise_timezone(self._raw_config)
            self._write_config()
            self._profile_cache.clear()
            self._notify_change()

    def remove_profile(self, name: str) -> None:
        if name == "default":
            raise ConfigError("The default profile cannot be deleted")
        with self._lock:
            profiles = self._raw_config.get("profiles", {})
            if name not in profiles:
                raise ConfigError(f"Profile '{name}' does not exist")
            del profiles[name]
            for profile in profiles.values():
                if profile.get("inherit") == name:
                    profile["inherit"] = "default"
            if self._active_profile == name:
                self._active_profile = "default"
            self._write_config()
            self._profile_cache.clear()
            self._notify_change()

    def rename_profile(self, current_name: str, new_name: str) -> None:
        if current_name == "default":
            raise ConfigError("The default profile cannot be renamed")
        if not new_name or new_name == "default":
            raise ConfigError("Invalid profile name supplied")
        with self._lock:
            profiles = self._raw_config.setdefault("profiles", {})
            if current_name not in profiles:
                raise ConfigError(f"Profile '{current_name}' does not exist")
            if new_name in profiles:
                raise ConfigError(f"Profile '{new_name}' already exists")
            profile_data = profiles.pop(current_name)
            profiles[new_name] = profile_data
            for profile in profiles.values():
                if profile.get("inherit") == current_name:
                    profile["inherit"] = new_name
            if self._active_profile == current_name:
                self._active_profile = new_name
            self._write_config()
            self._profile_cache.clear()
            self._notify_change()

    def list_profiles(self) -> List[str]:
        with self._lock:
            extra = sorted(self._raw_config.get("profiles", {}).keys())
        return ["default", *extra]

    def _normalise_timezone(self, data: Dict[str, Any]) -> bool:
        corrected = False

        def _coerce(container: Dict[str, Any]) -> None:
            nonlocal corrected
            timezone_cfg = container.get("timezone")
            if not isinstance(timezone_cfg, dict):
                container["timezone"] = {"use_utc": False}
                corrected = True
                return

            use_utc_value = timezone_cfg.get("use_utc")
            if not isinstance(use_utc_value, bool):
                timezone_cfg["use_utc"] = bool(use_utc_value)
                corrected = True

            tz_value = timezone_cfg.get("repository_timezone")
            if tz_value is None:
                if "repository_timezone" in timezone_cfg:
                    timezone_cfg.pop("repository_timezone", None)
                    corrected = True
                return
            if not isinstance(tz_value, str):
                timezone_cfg.pop("repository_timezone", None)
                corrected = True
                return

            tz_name = tz_value.strip()
            if not tz_name:
                timezone_cfg.pop("repository_timezone", None)
                corrected = True
                return
            if tz_name != tz_value:
                timezone_cfg["repository_timezone"] = tz_name
                corrected = True

            try:
                ZoneInfo(tz_name)
            except ZoneInfoNotFoundError:
                if tz_name.upper() == "UTC":
                    if timezone_cfg.get("use_utc") is not True:
                        timezone_cfg["use_utc"] = True
                        corrected = True
                    timezone_cfg.pop("repository_timezone", None)
                    logger.info(
                        "Repository timezone 'UTC' is not available on this system. Enabling UTC mode instead."
                    )
                else:
                    logger.warning(
                        "Repository timezone '%s' is not available on this system. Falling back to system timezone.",
                        tz_name,
                    )
                    timezone_cfg.pop("repository_timezone", None)
                corrected = True

        _coerce(data)
        profiles = data.get("profiles", {})
        if isinstance(profiles, dict):
            for profile in profiles.values():
                if isinstance(profile, dict):
                    _coerce(profile)
        return corrected


# ---------------------------------------------------------------------------
# Compatibility façade used throughout the application
# ---------------------------------------------------------------------------


class ExclusionConfig:
    """Thin wrapper around :class:`UnifiedConfigManager` for exclusions."""

    def __init__(self, manager: Optional[UnifiedConfigManager] = None) -> None:
        self._manager = manager or UnifiedConfigManager()
        self._lock = threading.RLock()
        self._change_callbacks: List[_Listener] = []

    @property
    def config_file(self) -> str:
        return str(self._manager.config_path)

    # ------------------------------------------------------------------
    # Retrieval helpers
    # ------------------------------------------------------------------

    def _get_section(self) -> Dict[str, Any]:
        config = self._manager.get_active_profile_config()
        return config.get("exclusions", {})

    def get_excluded_folders(self) -> Set[str]:
        section = self._get_section()
        folders = section.get("folders", {}).get("exclude", [])
        return set(folders)

    def get_excluded_files(self) -> Set[str]:
        section = self._get_section()
        files = section.get("files", {}).get("exclude", [])
        return set(files)

    def get_exclude_patterns(self) -> List[str]:
        section = self._get_section()
        patterns = section.get("patterns", {}).get("exclude", [])
        return list(patterns)

    def get_image_extensions(self) -> Set[str]:
        section = self._get_section()
        images = section.get("image_extensions", {}).get("include", [])
        return {img.lower() for img in images}

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def add_excluded_folder(self, folder: str) -> None:
        self._manager.update_list("exclusions.folders.exclude", [folder])
        self._notify_change()

    def add_excluded_file(self, file: str) -> None:
        self._manager.update_list("exclusions.files.exclude", [file])
        self._notify_change()

    def add_exclude_pattern(self, pattern: str) -> None:
        self._manager.update_list("exclusions.patterns.exclude", [pattern])
        self._notify_change()

    def add_image_extension(self, extension: str) -> None:
        normalised = extension if extension.startswith(".") else f".{extension}"
        self._manager.update_list("exclusions.image_extensions.include", [normalised.lower()])
        self._notify_change()

    def remove_excluded_folder(self, folder: str) -> None:
        self._manager.update_list("exclusions.folders.exclude", [folder], action="remove")
        self._notify_change()

    def remove_excluded_file(self, file: str) -> None:
        self._manager.update_list("exclusions.files.exclude", [file], action="remove")
        self._notify_change()

    def remove_exclude_pattern(self, pattern: str) -> None:
        self._manager.update_list("exclusions.patterns.exclude", [pattern], action="remove")
        self._notify_change()

    def remove_image_extension(self, extension: str) -> None:
        normalised = extension if extension.startswith(".") else f".{extension}"
        self._manager.update_list(
            "exclusions.image_extensions.include", [normalised.lower()], action="remove"
        )
        self._notify_change()

    def reset_to_defaults(self) -> None:
        self._manager.reset_to_defaults()
        self._notify_change()

    # ------------------------------------------------------------------
    # Listener handling
    # ------------------------------------------------------------------

    def add_change_listener(self, callback: Callable[[], None]) -> None:
        with self._lock:
            if not any(listener.matches(callback) for listener in self._change_callbacks):
                self._change_callbacks.append(_Listener(callback))
                self._manager.add_change_listener(callback)

    def remove_change_listener(self, callback: Callable[[], None]) -> None:
        with self._lock:
            removed = False
            retained: List[_Listener] = []
            for listener in self._change_callbacks:
                if listener.matches(callback):
                    removed = True
                else:
                    retained.append(listener)
            self._change_callbacks = retained
            if removed:
                self._manager.remove_change_listener(callback)

    def cleanup(self) -> None:
        with self._lock:
            self._change_callbacks.clear()

    def _notify_change(self) -> None:
        stale: List[_Listener] = []
        for listener in list(self._change_callbacks):
            callback = listener.get()
            if callback is None:
                stale.append(listener)
                continue
            try:
                callback()
            except RuntimeError as exc:  # pragma: no cover - defensive
                if "wrapped C/C++ object" in str(exc):
                    logger.debug("Removing dead exclusion listener: %s", exc)
                    stale.append(listener)
                else:
                    logger.error("Error notifying exclusion change listener: %s", exc)
            except Exception as exc:  # pragma: no cover - best effort
                logger.error("Error notifying exclusion change listener: %s", exc)
        if stale:
            for listener in stale:
                if listener in self._change_callbacks:
                    self._change_callbacks.remove(listener)


class ConfigurationManager(Generic[WidgetType]):
    """Backwards compatible façade built on top of the unified manager."""

    _instance: ClassVar[Optional["ConfigurationManager"]] = None
    _lock: ClassVar[threading.RLock] = threading.RLock()

    def __new__(cls) -> "ConfigurationManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        self.unified = UnifiedConfigManager()
        self.exclusion_config = ExclusionConfig(self.unified)
        self._change_callbacks: List[_Listener] = []
        self._initialized = True

    # ------------------------------------------------------------------
    # High-level helpers
    # ------------------------------------------------------------------

    def reload_configuration(
        self, config_path: Optional[str] = None, profile: Optional[str] = None
    ) -> None:
        path = Path(config_path).expanduser() if config_path else None
        self.unified.reload(path, profile)
        self._notify_change()

    def get_active_profile_config(self) -> Dict[str, Any]:
        return self.unified.get_active_profile_config()

    def get_active_profile(self) -> str:
        return self.unified.active_profile

    def set_active_profile(self, profile: str) -> None:
        self.unified.set_active_profile(profile)
        self._notify_change()

    def list_profiles(self) -> List[str]:
        return self.unified.list_profiles()

    def create_profile(self, name: str, inherit: Optional[str] = None) -> None:
        base = inherit or "default"
        data = self.unified.export_profile(base)
        self.unified.import_profile(name, data, inherit=base)
        self._notify_change()

    def delete_profile(self, name: str) -> None:
        self.unified.remove_profile(name)
        self._notify_change()

    def rename_profile(self, current_name: str, new_name: str) -> None:
        self.unified.rename_profile(current_name, new_name)
        self._notify_change()

    def export_profile(self, name: Optional[str] = None) -> Dict[str, Any]:
        return self.unified.export_profile(name)

    def import_profile(self, name: str, data: Dict[str, Any], inherit: str = "default") -> None:
        self.unified.import_profile(name, data, inherit)
        self._notify_change()

    def export_profile_as_toml(self, name: Optional[str] = None) -> str:
        profile_payload = {"profile": self.unified.export_profile(name)}
        return _toml_dumps(profile_payload)

    def import_profile_from_toml(self, name: str, content: str, inherit: str = "default") -> None:
        try:
            data = tomllib.loads(content)
        except (tomllib.TOMLDecodeError, AttributeError) as exc:
            raise ConfigValidationError(f"Invalid TOML content: {exc}") from exc
        profile_data = data.get("profile", data)
        if not isinstance(profile_data, dict):
            raise ConfigValidationError("Profile import payload must be a table")
        self.unified.import_profile(name, profile_data, inherit)
        self._notify_change()

    def set_value(self, path: str, value: Any, profile: Optional[str] = None) -> None:
        target_profile = profile or self.get_active_profile()
        profile_kw = None if target_profile == "default" else target_profile
        self.unified.set_value(path, value, profile=profile_kw)
        self._notify_change()

    def update_list(
        self, path: str, values: Iterable[str], action: str = "add", profile: Optional[str] = None
    ) -> None:
        target_profile = profile or self.get_active_profile()
        profile_kw = None if target_profile == "default" else target_profile
        self.unified.update_list(path, values, action=action, profile=profile_kw)
        self._notify_change()

    def validate_configuration(self) -> bool:
        try:
            self.unified.validate_current()
            return True
        except ConfigValidationError as exc:
            logger.error("Configuration validation failed: %s", exc)
            return False

    def migrate_configuration(self) -> bool:
        try:
            return self.unified.migrate()
        except ConfigMigrationError as exc:
            logger.error("Configuration migration failed: %s", exc)
            raise

    def get_merged_exclusions(
        self,
        additional_folders: Optional[Set[str]] = None,
        additional_files: Optional[Set[str]] = None,
        additional_patterns: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        config = self.get_active_profile_config()
        exclusions = config.get("exclusions", {})
        folders = set(exclusions.get("folders", {}).get("exclude", []))
        files = set(exclusions.get("files", {}).get("exclude", []))
        patterns = list(exclusions.get("patterns", {}).get("exclude", []))
        images = set(exclusions.get("image_extensions", {}).get("include", []))

        if additional_folders:
            folders.update(additional_folders)
        if additional_files:
            files.update(additional_files)
        if additional_patterns:
            patterns = list(dict.fromkeys(patterns + additional_patterns))

        return {
            "excluded_folders": folders,
            "excluded_files": files,
            "exclude_patterns": patterns,
            "image_extensions": images,
        }

    # ------------------------------------------------------------------
    # GUI integration helpers
    # ------------------------------------------------------------------

    def update_gui_filters(self, file_filters_widget: WidgetType) -> None:
        config = self.get_active_profile_config()
        exclusions = config.get("exclusions", {})
        try:
            file_filters_widget.folders_list.setItems(
                exclusions.get("folders", {}).get("exclude", [])
            )
            file_filters_widget.files_list.setItems(
                exclusions.get("files", {}).get("exclude", [])
            )
            file_filters_widget.patterns_list.setPatterns(
                exclusions.get("patterns", {}).get("exclude", [])
            )
            file_filters_widget.image_list.setItems(
                exclusions.get("image_extensions", {}).get("include", [])
            )
            self._notify_change()
        except AttributeError as exc:
            raise ConfigError("Invalid widget structure for GUI filters") from exc

    def save_gui_filters(self, file_filters_widget: WidgetType) -> None:
        try:
            configuration = file_filters_widget.get_configuration()
        except AttributeError as exc:
            raise ConfigError("Invalid widget: missing get_configuration") from exc

        required_keys = {"excluded_folders", "excluded_files", "exclude_patterns", "image_extensions"}
        if not required_keys.issubset(configuration):
            raise ConfigValidationError("Missing required configuration keys from widget")

        self.unified.set_value("exclusions.folders.exclude", list(configuration["excluded_folders"]))
        self.unified.set_value("exclusions.files.exclude", list(configuration["excluded_files"]))
        self.unified.set_value("exclusions.patterns.exclude", list(configuration["exclude_patterns"]))
        self.unified.set_value("exclusions.image_extensions.include", list(configuration["image_extensions"]))
        self._notify_change()

    def reset_to_defaults(self) -> None:
        self.unified.reset_to_defaults()
        self._notify_change()

    # ------------------------------------------------------------------
    # Listener helpers & cleanup
    # ------------------------------------------------------------------

    def add_change_listener(self, callback: Callable[[], None]) -> None:
        if not any(listener.matches(callback) for listener in self._change_callbacks):
            self._change_callbacks.append(_Listener(callback))
            self.unified.add_change_listener(callback)

    def remove_change_listener(self, callback: Callable[[], None]) -> None:
        removed = False
        retained: List[_Listener] = []
        for listener in self._change_callbacks:
            if listener.matches(callback):
                removed = True
            else:
                retained.append(listener)
        self._change_callbacks = retained
        if removed:
            self.unified.remove_change_listener(callback)

    def cleanup(self) -> None:
        self._change_callbacks.clear()
        self.exclusion_config.cleanup()
        UnifiedConfigManager._instance = None  # reset singleton for tests
        ConfigurationManager._instance = None
        self._initialized = False

    def _notify_change(self) -> None:
        stale: List[_Listener] = []
        for listener in list(self._change_callbacks):
            callback = listener.get()
            if callback is None:
                stale.append(listener)
                continue
            try:
                callback()
            except RuntimeError as exc:  # pragma: no cover - defensive
                if "wrapped C/C++ object" in str(exc):
                    logger.debug("Removing dead configuration listener: %s", exc)
                    stale.append(listener)
                else:
                    logger.error("Error during configuration change notification: %s", exc)
            except Exception as exc:  # pragma: no cover - best effort
                logger.error("Error during configuration change notification: %s", exc)
        if stale:
            for listener in stale:
                if listener in self._change_callbacks:
                    self._change_callbacks.remove(listener)


__all__ = [
    "UnifiedConfigManager",
    "ConfigurationManager",
    "ExclusionConfig",
    "ConfigError",
    "ConfigValidationError",
    "ConfigMigrationError",
    "ConfigIOError",
]
