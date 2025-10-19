from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, ClassVar, Dict, Iterable, List, Optional

from .compat import tomllib
from .defaults import DEFAULT_CONFIG_TOML, DEFAULT_CONFIG
from .exceptions import (
    ConfigError,
    ConfigValidationError,
    ConfigMigrationError,
    ConfigIOError,
)
from .listeners import _Listener
from .profile_service import ProfileService, ProfileResolutionResult
from .profiles import normalise_profile_sections
from .storage import ConfigStorage
from .timezone import TimezoneNormalizer
from .utils import _deep_merge
from .validation import _validator, ValidationError
from .migration import migrate_from_legacy_files, migrate_timezone_json
from .toml_io import _toml_dumps

logger = logging.getLogger(__name__)


class UnifiedConfigManager:
    """Singleton configuration manager orchestrating modular services."""

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

        self.storage = ConfigStorage()
        self._raw_config: Dict[str, Any] = deepcopy(DEFAULT_CONFIG)
        self._active_profile: str = "default"
        self._profile_cache: Dict[str, ProfileResolutionResult] = {}
        self._change_listeners: List[_Listener] = []

        self._profiles = ProfileService()
        self._tz = TimezoneNormalizer()

        self._load_or_create()
        self._initialized = True

        self._batch_depth = 0
        self._batch_dirty = False
        self._batch_notify = False
        self._batch_clear_profiles = False

    @property
    def config_path(self) -> Path:
        return self.storage.path

    def _write_config(self) -> None:
        try:
            self.storage.write_config(self._raw_config)
        except ConfigIOError:
            raise
        except Exception as exc:  # pragma: no cover
            raise ConfigIOError(f"Failed to write configuration file: {exc}") from exc

    def _load_or_create(self) -> None:
        try:
            self.storage.ensure_directory()
        except ConfigIOError:
            raise
        except Exception as exc:  # pragma: no cover
            raise ConfigIOError(
                f"Unable to create configuration directory: {exc}"
            ) from exc

        if not self.storage.path.exists():
            logger.info("Creating default configuration at %s", self.storage.path)
            try:
                self.storage.write_default(DEFAULT_CONFIG_TOML)
            except ConfigIOError:
                raise
            except Exception as exc:  # pragma: no cover
                raise ConfigIOError(
                    f"Failed to write configuration file: {exc}"
                ) from exc
            self._raw_config = deepcopy(DEFAULT_CONFIG)
            if self._tz.normalise_timezone(self._raw_config):
                self._write_config()
            return

        try:
            loaded = self.storage.read_config()
            if not isinstance(loaded, dict):
                raise ConfigValidationError("Configuration root must be a table")
            self._raw_config = _deep_merge(DEFAULT_CONFIG, loaded)
            timezone_fixed = self._tz.normalise_timezone(self._raw_config)
            profile_fixed = normalise_profile_sections(self._raw_config)
            self._validate(self._raw_config)
            if timezone_fixed or profile_fixed:
                self._write_config()
        except FileNotFoundError:
            self._raw_config = deepcopy(DEFAULT_CONFIG)
            self._tz.normalise_timezone(self._raw_config)
        except tomllib.TOMLDecodeError as exc:
            logger.error(
                "Configuration file %s is not valid TOML: %s", self.storage.path, exc
            )
            backup_path = self.storage.backup_existing_config(suffix="corrupt")
            if backup_path:
                logger.error("Corrupt configuration backed up to %s", backup_path)
            self._raw_config = deepcopy(DEFAULT_CONFIG)
            self._tz.normalise_timezone(self._raw_config)
            self._write_config()
            logger.info("Restored default configuration after TOML decode failure")
        except ConfigValidationError:
            raise
        except ValidationError as exc:
            raise ConfigValidationError(
                f"Invalid configuration: {exc.message}"
            ) from exc
        except ConfigIOError:
            raise
        except Exception as exc:  # pragma: no cover
            raise ConfigIOError(f"Unable to load configuration: {exc}") from exc

    def reload(
        self, config_path: Optional[Path] = None, profile: Optional[str] = None
    ) -> None:
        with self._lock:
            if config_path is not None:
                self.storage.set_path(Path(config_path))
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

    def _validate(self, data: Dict[str, Any]) -> None:
        try:
            errors = sorted(_validator.iter_errors(data), key=lambda e: getattr(e, "path", []))
        except ImportError as exc:
            raise ConfigValidationError(str(exc)) from exc
        if errors:
            first = errors[0]
            location = ".".join(str(part) for part in first.path)
            message = f"{location}: {first.message}" if location else first.message
            raise ConfigValidationError(message)
        self._profiles.validate_profiles(data)

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
            result = self._profiles.resolve(
                profile_name, self._raw_config, self._profile_cache
            )
            return result

    def get_active_profile_config(self) -> Dict[str, Any]:
        return deepcopy(self.resolve_profile(self._active_profile).config)

    def get_raw_config(self) -> Dict[str, Any]:
        return deepcopy(self._raw_config)

    def validate_current(self) -> None:
        with self._lock:
            self._validate(self._raw_config)

    def _locate_section(
        self, path: str, create: bool = False, profile: Optional[str] = None
    ) -> Dict[str, Any]:
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

    def _schedule_persist(self, notify: bool = True) -> None:
        if self._batch_depth > 0:
            self._batch_dirty = True
            if notify:
                self._batch_notify = True
            self._batch_clear_profiles = True
            return
        self._write_config()
        self._profile_cache.clear()
        if notify:
            self._notify_change()

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
                raise ConfigError(
                    f"Configuration path '{path}' does not reference a list"
                )
            if action == "add":
                merged = list(dict.fromkeys(current + items))
            elif action == "remove":
                merged = [value for value in current if value not in items]
            else:
                raise ValueError(f"Unknown action '{action}'")
            if merged == current:
                return
            container[key] = merged
            self._schedule_persist()

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
            current = container.get(key)
            if value is None:
                if key not in container:
                    return
                del container[key]
            else:
                if current == value:
                    return
                container[key] = value
            self._schedule_persist()

    def begin_batch_update(self) -> None:
        with self._lock:
            self._batch_depth += 1

    def end_batch_update(self, notify: bool = True) -> None:
        with self._lock:
            if self._batch_depth == 0:
                raise RuntimeError("end_batch_update called without matching begin_batch_update")
            self._batch_depth -= 1
            if self._batch_depth == 0:
                try:
                    if self._batch_dirty:
                        self._write_config()
                        if self._batch_clear_profiles:
                            self._profile_cache.clear()
                        if self._batch_notify and notify:
                            self._notify_change()
                    elif self._batch_notify and notify:
                        self._notify_change()
                finally:
                    self._batch_dirty = False
                    self._batch_notify = False
                    self._batch_clear_profiles = False
            else:
                if not notify:
                    self._batch_notify = False

    @contextmanager
    def batch_update(self, notify: bool = True):
        self.begin_batch_update()
        try:
            yield
        finally:
            self.end_batch_update(notify=notify)

    def set_values_batch(
        self, updates: Dict[str, Any], profile: Optional[str] = None, notify: bool = True
    ) -> None:
        if not updates:
            return
        with self.batch_update(notify=notify):
            for path, value in updates.items():
                self.set_value(path, value, profile=profile)

    def reset_to_defaults(self) -> None:
        with self._lock:
            self._raw_config = deepcopy(DEFAULT_CONFIG)
            self._tz.normalise_timezone(self._raw_config)
            self._write_config()
            self._profile_cache.clear()
            self._active_profile = "default"
            self._notify_change()

    def add_change_listener(self, callback: Callable[[], None]) -> None:
        if not any(listener.matches(callback) for listener in self._change_listeners):
            self._change_listeners.append(_Listener(callback))

    def remove_change_listener(self, callback: Callable[[], None]) -> None:
        self._change_listeners = [
            listener
            for listener in self._change_listeners
            if not listener.matches(callback)
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
            except RuntimeError as exc:  # pragma: no cover
                if "wrapped C/C++ object" in str(exc):
                    logger.debug("Removing dead configuration listener: %s", exc)
                    stale.append(listener)
                else:
                    logger.error("Error in configuration change listener: %s", exc)
            except Exception as exc:  # pragma: no cover
                logger.error("Error in configuration change listener: %s", exc)
        if stale:
            for listener in stale:
                if listener in self._change_listeners:
                    self._change_listeners.remove(listener)

    def migrate(self) -> bool:
        with self._lock:
            migrated = False
            try:
                if migrate_from_legacy_files(self._raw_config):
                    migrated = True
                if migrate_timezone_json(self._raw_config):
                    migrated = True
            except ConfigMigrationError:
                raise
            except Exception as exc:  # pragma: no cover
                raise ConfigMigrationError(f"Failed during migration: {exc}") from exc

            if migrated:
                backup_path = self.storage.backup_existing_config(suffix="migration")
                self._write_config()
                self._profile_cache.clear()
                if backup_path:
                    logger.info("Existing configuration backed up to %s", backup_path)
                logger.info("Legacy configuration migrated into %s", self.storage.path)
            else:
                logger.info("No legacy configuration files found for migration")
            return migrated

    def export_profile(self, profile: Optional[str] = None) -> Dict[str, Any]:
        result = self.resolve_profile(profile)
        return deepcopy(result.config)

    def import_profile(
        self, name: str, data: Dict[str, Any], inherit: str = "default"
    ) -> None:
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
            self._tz.normalise_timezone(self._raw_config)
            normalise_profile_sections(self._raw_config)
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

    def create_profile(self, name: str, inherit: Optional[str] = None) -> None:
        base = inherit or "default"
        data = self.export_profile(base)
        self.import_profile(name, data, inherit=base)

    def export_profile_as_toml(self, name: Optional[str] = None) -> str:
        profile_payload = {"profile": self.export_profile(name)}
        return _toml_dumps(profile_payload)

    def import_profile_from_toml(
        self, name: str, content: str, inherit: str = "default"
    ) -> None:
        try:
            data = tomllib.loads(content)
        except (tomllib.TOMLDecodeError, AttributeError) as exc:
            raise ConfigValidationError(f"Invalid TOML content: {exc}") from exc
        profile_data = data.get("profile", data)
        if not isinstance(profile_data, dict):
            raise ConfigValidationError("Profile import payload must be a table")
        self.import_profile(name, profile_data, inherit=inherit)

    def cleanup(self) -> None:
        with self._lock:
            self._change_listeners.clear()
            self._profile_cache.clear()
            self._initialized = False
            type(self)._instance = None  # reset singleton for future use


__all__ = ["UnifiedConfigManager", "ProfileResolutionResult"]
