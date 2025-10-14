from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Generic,
    Iterable,
    List,
    Optional,
    Set,
    TypeVar,
)

from .compat import tomllib
from .exceptions import ConfigError, ConfigValidationError, ConfigMigrationError
from .listeners import _Listener
from .toml_io import _toml_dumps
from .unified import UnifiedConfigManager

logger = logging.getLogger(__name__)

WidgetType = TypeVar("WidgetType")


class ExclusionConfig:
    """Thin wrapper around :class:`UnifiedConfigManager` for exclusions."""

    def __init__(self, manager: Optional[UnifiedConfigManager] = None) -> None:
        self._manager = manager or UnifiedConfigManager()
        self._lock = threading.RLock()
        self._change_callbacks: List[_Listener] = []

    @property
    def config_file(self) -> str:
        return str(self._manager.config_path)

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
        self._manager.update_list(
            "exclusions.image_extensions.include", [normalised.lower()]
        )
        self._notify_change()

    def remove_excluded_folder(self, folder: str) -> None:
        self._manager.update_list(
            "exclusions.folders.exclude", [folder], action="remove"
        )
        self._notify_change()

    def remove_excluded_file(self, file: str) -> None:
        self._manager.update_list("exclusions.files.exclude", [file], action="remove")
        self._notify_change()

    def remove_exclude_pattern(self, pattern: str) -> None:
        self._manager.update_list(
            "exclusions.patterns.exclude", [pattern], action="remove"
        )
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

    def add_change_listener(self, callback: Callable[[], None]) -> None:
        with self._lock:
            if not any(
                listener.matches(callback) for listener in self._change_callbacks
            ):
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
            except RuntimeError as exc:  # pragma: no cover
                if "wrapped C/C++ object" in str(exc):
                    logger.debug("Removing dead exclusion listener: %s", exc)
                    stale.append(listener)
                else:
                    logger.error("Error notifying exclusion change listener: %s", exc)
            except Exception as exc:  # pragma: no cover
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

    def import_profile(
        self, name: str, data: Dict[str, Any], inherit: str = "default"
    ) -> None:
        self.unified.import_profile(name, data, inherit)
        self._notify_change()

    def export_profile_as_toml(self, name: Optional[str] = None) -> str:
        profile_payload = {"profile": self.unified.export_profile(name)}
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
        self.unified.import_profile(name, profile_data, inherit)
        self._notify_change()

    def set_value(self, path: str, value: Any, profile: Optional[str] = None) -> None:
        target_profile = profile or self.get_active_profile()
        profile_kw = None if target_profile == "default" else target_profile
        self.unified.set_value(path, value, profile=profile_kw)
        self._notify_change()

    def update_list(
        self,
        path: str,
        values: Iterable[str],
        action: str = "add",
        profile: Optional[str] = None,
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

        required_keys = {
            "excluded_folders",
            "excluded_files",
            "exclude_patterns",
            "image_extensions",
        }
        if not required_keys.issubset(configuration):
            raise ConfigValidationError(
                "Missing required configuration keys from widget"
            )

        active_profile = self.get_active_profile()
        profile_kw = None if active_profile == "default" else active_profile

        self.unified.set_value(
            "exclusions.folders.exclude",
            list(configuration["excluded_folders"]),
            profile=profile_kw,
        )
        self.unified.set_value(
            "exclusions.files.exclude",
            list(configuration["excluded_files"]),
            profile=profile_kw,
        )
        self.unified.set_value(
            "exclusions.patterns.exclude",
            list(configuration["exclude_patterns"]),
            profile=profile_kw,
        )
        self.unified.set_value(
            "exclusions.image_extensions.include",
            list(configuration["image_extensions"]),
            profile=profile_kw,
        )
        self._notify_change()

    def reset_to_defaults(self) -> None:
        self.unified.reset_to_defaults()
        self._notify_change()

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
        from .unified import UnifiedConfigManager as _Unified  # lazy import

        _Unified._instance = None  # type: ignore[attr-defined]
        ConfigurationManager._instance = None  # type: ignore[attr-defined]
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
            except RuntimeError as exc:  # pragma: no cover
                if "wrapped C/C++ object" in str(exc):
                    logger.debug("Removing dead configuration listener: %s", exc)
                    stale.append(listener)
                else:
                    logger.error(
                        "Error during configuration change notification: %s", exc
                    )
            except Exception as exc:  # pragma: no cover
                logger.error("Error during configuration change notification: %s", exc)
        if stale:
            for listener in stale:
                if listener in self._change_callbacks:
                    self._change_callbacks.remove(listener)


__all__ = ["ConfigurationManager", "ExclusionConfig"]
