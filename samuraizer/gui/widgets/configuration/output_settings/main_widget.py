# samuraizer/gui/widgets/configuration/output_settings/main_widget.py

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QMessageBox
from PyQt6.QtCore import pyqtSignal

from .settings_manager import SettingsManager
from .output_file_group import OutputFileGroup
from .format_selection_group import FormatSelectionGroup
from .streaming_options_group import StreamingOptionsGroup
from .additional_options_group import AdditionalOptionsGroup
from .path_utils import (
    DEFAULT_BASENAME,
    derive_default_output_path,
    extension_for_format,
    normalise_output_path,
    validate_output_path as is_valid_output_path,
)
from samuraizer.config.defaults import DEFAULT_CONFIG
from samuraizer.config.unified import UnifiedConfigManager

logger = logging.getLogger(__name__)

_PATH_UNCHANGED = object()

class OutputOptionsWidget(QWidget):
    """Widget for configuring analysis output options"""

    outputConfigChanged = pyqtSignal(dict)  # Signal emitted when output configuration changes

    # Define formats that support pretty printing
    _pretty_print_formats = {"JSON", "XML"}

    # Define formats that support compression
    _compression_formats = {"MESSAGEPACK"}

    _FORMAT_LABELS = {
        "json": "JSON",
        "yaml": "YAML",
        "xml": "XML",
        "jsonl": "JSONL",
        "dot": "DOT",
        "csv": "CSV",
        "s-expression": "S-Expression",
        "sexp": "S-Expression",
        "messagepack": "MessagePack",
        "msgpack": "MessagePack",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = UnifiedConfigManager()
        self.settings_manager = SettingsManager()
        self._initializing: bool = True
        self._config_sync_lock: bool = False
        self.config_manager.add_change_listener(self._handle_config_change)
        self.destroyed.connect(self._on_destroyed)
        self.initUI()
        self.loadSettings()
        self._initializing = False
        self.emit_configuration_changed()

    def initUI(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)

        # Output File Group
        self.output_file_group = OutputFileGroup(
            settings_manager=self.settings_manager,
            get_file_extension_callback=extension_for_format,
        )
        self.output_file_group.outputPathChanged.connect(self.on_output_path_changed)
        layout.addWidget(self.output_file_group)

        # Format Selection Group
        self.format_selection_group = FormatSelectionGroup()
        self.format_selection_group.formatChanged.connect(self.on_format_changed)
        layout.addWidget(self.format_selection_group)

        # Streaming Options Group
        self.streaming_options_group = StreamingOptionsGroup()
        self.streaming_options_group.streamingChanged.connect(self.on_streaming_changed)
        layout.addWidget(self.streaming_options_group)

        # Additional Options Group
        self.additional_options_group = AdditionalOptionsGroup()
        self.additional_options_group.optionChanged.connect(self.on_option_changed)
        layout.addWidget(self.additional_options_group)

        # Add stretch to keep everything aligned at the top
        layout.addStretch()

        # Ensure output file extension reflects the initial state
        self.output_file_group.set_format(self.format_selection_group.get_selected_format())

    def on_format_changed(self, format_name: str):
        """Handle format selection changes"""
        # Update format description is handled within FormatSelectionGroup
        self.output_file_group.set_format(format_name)

        # Update streaming availability
        format_upper = (format_name or "").upper()
        if format_upper == "CHOOSE OUTPUT FORMAT":
            format_upper = ""

        format_supports_streaming = format_upper in {"JSON", "JSONL", "MESSAGEPACK"}
        self.streaming_options_group.enable_streaming.setEnabled(format_supports_streaming)
        if not format_supports_streaming:
            self.streaming_options_group.enable_streaming.setChecked(False)

        # Update pretty printing availability
        supports_pretty_print = format_upper in self._pretty_print_formats
        self.additional_options_group.set_pretty_print_visible(supports_pretty_print)
        if not supports_pretty_print:
            self.additional_options_group.pretty_print.setChecked(False)

        # Update compression availability
        supports_compression = format_upper in self._compression_formats
        self.additional_options_group.set_compression_visible(supports_compression)
        if not supports_compression:
            self.additional_options_group.use_compression.setChecked(False)

        if self._initializing or self._config_sync_lock:
            return

        self.emit_configuration_changed()
        self.saveSettings()

    def on_streaming_changed(self, is_enabled: bool):
        """Handle streaming option changes"""
        if self._initializing:
            return

        if bool(is_enabled) and not self.is_streaming_supported():
            QMessageBox.warning(
                self,
                "Invalid Configuration",
                "Streaming is only available for JSON, JSONL, and MessagePack formats."
            )
            self.streaming_options_group.enable_streaming.setChecked(False)
            return

        if self._config_sync_lock:
            return

        self.emit_configuration_changed()
        self.saveSettings()

    def on_output_path_changed(self, path: str):
        """Handle output path changes"""
        if self._initializing or self._config_sync_lock:
            return
        self.output_file_group.set_path_source("custom")
        self.emit_configuration_changed()
        self.saveSettings()

    def on_option_changed(self):
        """Handle changes to any option checkbox"""
        if self._initializing or self._config_sync_lock:
            return
        self.emit_configuration_changed()
        self.saveSettings()

    def emit_configuration_changed(self):
        """Emit signal with current configuration"""
        if self._initializing or self._config_sync_lock:
            return
        config = self.get_configuration()
        self.outputConfigChanged.emit(config)

    def get_configuration(self) -> dict:
        """Get the current output configuration"""
        selected_format = self.format_selection_group.get_selected_format() or ""
        format_value = selected_format.lower()
        if format_value == "choose output format":
            format_value = ""

        config = {
            'format': format_value,
            'output_path': self.output_file_group.get_output_path(),
            'streaming': self.streaming_options_group.enable_streaming.isChecked(),
            'include_summary': self.additional_options_group.include_summary.isChecked(),
            'pretty_print': self.additional_options_group.pretty_print.isChecked(),
            'use_compression': self.additional_options_group.use_compression.isChecked()
        }

        return config

    def validate_output_path(self, path: Optional[str] = None) -> bool:
        """Validate the output file path"""
        target_path = path or self.output_file_group.get_output_path()
        if not target_path:
            return False
        try:
            canonical = normalise_output_path(target_path)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to normalise output path %s: %s", target_path, exc, exc_info=True)
            return False
        return is_valid_output_path(canonical)

    def loadSettings(self):
        """Load saved output settings and migrate legacy preferences."""
        try:
            self._migrate_output_settings()
        except Exception as exc:
            logger.error("Error migrating output settings: %s", exc, exc_info=True)
        finally:
            self._apply_profile_settings()

    def saveSettings(self):
        if self._initializing or self._config_sync_lock:
            return
        try:
            config_snapshot = self.get_configuration()

            profile_kw = self._profile_storage_target()
            format_value = config_snapshot.get('format')

            updates = {
                "analysis.include_summary": bool(
                    config_snapshot.get('include_summary', True)
                ),
                "output.streaming": bool(config_snapshot.get('streaming', False)),
                "output.pretty_print": bool(config_snapshot.get('pretty_print', False)),
                "output.compression": bool(
                    config_snapshot.get('use_compression', False)
                ),
            }
            if format_value:
                updates["analysis.default_format"] = format_value

            output_path_raw = config_snapshot.get('output_path') or ""
            output_path = None
            if output_path_raw:
                try:
                    output_path = normalise_output_path(output_path_raw)
                except Exception as exc:  # pragma: no cover - defensive
                    logger.error("Failed to normalise output path %s: %s", output_path_raw, exc, exc_info=True)
                    output_path = output_path_raw
            updates["output.path"] = output_path

            self.config_manager.set_values_batch(updates, profile=profile_kw)
        except Exception as e:
            logger.error(f"Error saving output settings: {e}", exc_info=True)

    # ------------------------------------------------------------------
    # Profile synchronisation helpers
    # ------------------------------------------------------------------
    def _apply_profile_settings(self) -> None:
        if self._config_sync_lock:
            return

        path_update = _PATH_UNCHANGED
        with self._suspend_config_sync():
            try:
                config = self.config_manager.get_active_profile_config()
            except Exception as exc:
                logger.error(
                    "Error retrieving profile configuration: %s", exc, exc_info=True
                )
            else:
                analysis_cfg = config.get("analysis", {})
                output_cfg = config.get("output", {})

                self._sync_format_controls(analysis_cfg)
                self._sync_streaming_controls(output_cfg)
                self._sync_additional_options(analysis_cfg, output_cfg)
                path_update = self._sync_output_path(analysis_cfg, output_cfg)

        if not self._initializing:
            self.emit_configuration_changed()

        if path_update is not _PATH_UNCHANGED:
            try:
                self.config_manager.set_values_batch(
                    {"output.path": path_update},
                    profile=self._profile_storage_target(),
                    notify=False,
                )
            except Exception as exc:
                logger.error(
                    "Failed to persist fallback output path: %s", exc, exc_info=True
                )

    def _sync_format_controls(self, analysis_cfg: dict) -> None:
        format_label = self._format_label(analysis_cfg.get("default_format"))
        if not format_label:
            format_label = "Choose Output Format"
        format_combo = self.format_selection_group.format_combo
        format_combo.blockSignals(True)
        self.format_selection_group.set_selected_format(format_label)
        format_combo.blockSignals(False)
        self.on_format_changed(self.format_selection_group.get_selected_format())

    def _sync_streaming_controls(self, output_cfg: dict) -> None:
        streaming_checkbox = self.streaming_options_group.enable_streaming
        desired_streaming = bool(output_cfg.get("streaming", False))
        streaming_checkbox.blockSignals(True)
        streaming_checkbox.setChecked(
            desired_streaming and streaming_checkbox.isEnabled()
        )
        streaming_checkbox.blockSignals(False)

    def _sync_additional_options(self, analysis_cfg: dict, output_cfg: dict) -> None:
        include_summary_box = self.additional_options_group.include_summary
        include_summary_box.blockSignals(True)
        include_summary_box.setChecked(
            bool(analysis_cfg.get("include_summary", True))
        )
        include_summary_box.blockSignals(False)

        pretty_box = self.additional_options_group.pretty_print
        pretty_box.blockSignals(True)
        pretty_enabled = bool(output_cfg.get("pretty_print", True))
        if not pretty_box.isVisible():
            pretty_enabled = False
        pretty_box.setChecked(pretty_enabled)
        pretty_box.blockSignals(False)

        compression_box = self.additional_options_group.use_compression
        compression_box.blockSignals(True)
        compression_enabled = bool(output_cfg.get("compression", False))
        if not compression_box.isVisible():
            compression_enabled = False
        compression_box.setChecked(compression_enabled)
        compression_box.blockSignals(False)

    def _sync_output_path(self, analysis_cfg: dict, output_cfg: dict) -> object:
        desired_path_raw = output_cfg.get("path")
        desired_path_text = str(desired_path_raw).strip() if desired_path_raw else ""
        normalised_profile_path = ""
        if desired_path_text:
            try:
                normalised_profile_path = normalise_output_path(desired_path_text)
            except Exception as exc:
                logger.warning(
                    "Failed to normalise profile output path '%s': %s",
                    desired_path_text,
                    exc,
                )
                normalised_profile_path = desired_path_text
            if normalised_profile_path and not is_valid_output_path(normalised_profile_path):
                logger.warning(
                    "Profile specified output path '%s' is invalid; falling back to defaults.",
                    desired_path_text,
                )
                normalised_profile_path = ""

        repository_path = self.output_file_group.get_repository_path().strip()
        repository_normalised = ""
        if repository_path:
            try:
                repository_normalised = normalise_output_path(repository_path)
            except Exception:  # pragma: no cover - defensive
                repository_normalised = repository_path

        path_source = "default"
        path_update = _PATH_UNCHANGED

        if normalised_profile_path:
            self.output_file_group.set_output_path(normalised_profile_path)
            path_source = "profile"
            if normalised_profile_path != desired_path_text:
                path_update = normalised_profile_path
        else:
            fallback_path = self._determine_default_output_path(analysis_cfg)
            if fallback_path:
                self.output_file_group.set_output_path(fallback_path)
                if repository_normalised and self._is_within_repository(
                    fallback_path, repository_normalised
                ):
                    path_source = "repository"
                else:
                    path_source = "default"
                if fallback_path != desired_path_text:
                    path_update = fallback_path
            else:
                self.output_file_group.set_output_path("")
                path_source = "default"
                if desired_path_text:
                    path_update = None

        self.output_file_group.set_path_source(path_source)
        return path_update

    def _handle_config_change(self) -> None:
        self._apply_profile_settings()

    def _on_destroyed(self, _obj=None) -> None:
        try:
            self.config_manager.remove_change_listener(self._handle_config_change)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Error detaching output settings listener: %s", exc)

    def _profile_storage_target(self) -> Optional[str]:
        """Return the profile section used for persistence."""

        active_profile = self.config_manager.active_profile
        if active_profile == "default":
            return None
        return active_profile

    @classmethod
    def _format_label(cls, value: Optional[str]) -> str:
        if value is None:
            return ""
        key = str(value).strip().lower().replace("_", "-")
        return cls._FORMAT_LABELS.get(key, "")

    @contextmanager
    def _suspend_config_sync(self):
        previous = self._config_sync_lock
        self._config_sync_lock = True
        try:
            yield
        finally:
            self._config_sync_lock = previous

    def is_streaming_supported(self) -> bool:
        """Check if the selected format supports streaming"""
        format_name = self.format_selection_group.get_selected_format().upper()
        return format_name in ["JSON", "JSONL", "MESSAGEPACK"]

    # ------------------------------------------------------------------ #
    # Compatibility helpers
    # ------------------------------------------------------------------ #
    def get_output_path(self) -> str:
        return self.output_file_group.get_output_path()

    def validateOutputPath(self, path: Optional[str] = None) -> bool:  # noqa: N802 - Qt style compatibility
        return self.validate_output_path(path)

    def apply_repository_context(self, repository_path: str) -> None:
        self.output_file_group.apply_repository_defaults(repository_path)
        if self.output_file_group.get_path_source() in {"default", "repository"}:
            fallback = self._determine_default_output_path()
            if fallback:
                try:
                    repository_normalised = normalise_output_path(repository_path)
                except Exception:  # pragma: no cover - defensive
                    repository_normalised = repository_path
                path_source = (
                    "repository"
                    if repository_normalised
                    and self._is_within_repository(fallback, repository_normalised)
                    else "default"
                )
                with self._suspend_config_sync():
                    self.output_file_group.set_output_path(fallback)
                    self.output_file_group.set_path_source(path_source)
                try:
                    self.config_manager.set_values_batch(
                        {"output.path": fallback},
                        profile=self._profile_storage_target(),
                        notify=False,
                    )
                except Exception as exc:
                    logger.error(
                        "Failed to persist repository-derived output path: %s",
                        exc,
                        exc_info=True,
                    )
                if not self._initializing:
                    self.emit_configuration_changed()

    def _determine_default_output_path(
        self, analysis_cfg: Optional[dict] = None
    ) -> Optional[str]:
        """Compute a sensible default output path when profiles lack one."""

        if analysis_cfg is None:
            try:
                analysis_cfg = (
                    self.config_manager.get_active_profile_config().get("analysis", {})
                )
            except Exception:  # pragma: no cover - defensive
                analysis_cfg = {}

        filename = self.output_file_group.get_preview_filename() or DEFAULT_BASENAME
        extension = self.output_file_group.get_current_extension()
        if not extension:
            format_key = analysis_cfg.get("default_format")
            if not format_key:
                format_key = DEFAULT_CONFIG.get("analysis", {}).get(
                    "default_format", "json"
                )
            extension = extension_for_format(format_key)

        repository_path = self.output_file_group.get_repository_path() or None
        fallback = derive_default_output_path(repository_path, filename, extension)
        if fallback:
            try:
                return normalise_output_path(fallback)
            except Exception:  # pragma: no cover - defensive
                return fallback
        return None

    @staticmethod
    def _is_within_repository(candidate: str, repository_path: str) -> bool:
        try:
            candidate_path = Path(candidate).resolve(strict=False)
            repo_path = Path(repository_path).resolve(strict=False)
        except Exception:  # pragma: no cover - defensive
            return False
        try:
            candidate_path.relative_to(repo_path)
            return True
        except ValueError:
            return False

    def _migrate_output_settings(self) -> None:
        """Populate profile storage with legacy QSettings preferences."""
        migrated_flag = self.settings_manager.load_setting(
            "output/migrated_to_profiles", False, type_=bool
        )
        if migrated_flag:
            return

        config = self.config_manager.get_active_profile_config()
        analysis_cfg = config.get("analysis", {})
        output_cfg = config.get("output", {})
        updates = {}

        stored_format = self.settings_manager.load_setting("output/format", "")
        if stored_format:
            stored_format = str(stored_format).strip()
            if stored_format and stored_format.lower() != analysis_cfg.get("default_format"):
                updates["analysis.default_format"] = stored_format.lower()

        streaming_pref = self.settings_manager.load_setting("output/streaming", None, type_=bool)
        if streaming_pref is not None and bool(streaming_pref) != bool(output_cfg.get("streaming")):
            updates["output.streaming"] = bool(streaming_pref)

        include_summary = self.settings_manager.load_setting("output/include_summary", None, type_=bool)
        if include_summary is not None and bool(include_summary) != bool(analysis_cfg.get("include_summary", True)):
            updates["analysis.include_summary"] = bool(include_summary)

        pretty_pref = self.settings_manager.load_setting("output/pretty_print", None, type_=bool)
        if pretty_pref is not None and bool(pretty_pref) != bool(output_cfg.get("pretty_print", DEFAULT_CONFIG["output"].get("pretty_print", True))):
            updates["output.pretty_print"] = bool(pretty_pref)

        compression_pref = self.settings_manager.load_setting("output/use_compression", None, type_=bool)
        if compression_pref is not None and bool(compression_pref) != bool(output_cfg.get("compression", DEFAULT_CONFIG["output"].get("compression", False))):
            updates["output.compression"] = bool(compression_pref)

        legacy_path = self.settings_manager.load_setting("output/last_path", "")
        if legacy_path and not output_cfg.get("path"):
            try:
                legacy_normalised = normalise_output_path(str(legacy_path))
            except Exception as exc:
                logger.warning(
                    "Failed to normalise legacy output path '%s': %s",
                    legacy_path,
                    exc,
                )
                legacy_normalised = str(legacy_path)
            if is_valid_output_path(legacy_normalised):
                updates["output.path"] = legacy_normalised
            else:
                logger.warning(
                    "Discarding legacy output path '%s' because the directory is not writable.",
                    legacy_path,
                )

        if updates:
            try:
                self.config_manager.set_values_batch(
                    updates,
                    profile=self._profile_storage_target(),
                    notify=False,
                )
            except Exception as exc:
                logger.error("Failed migrating legacy output settings: %s", exc, exc_info=True)
                return

        self.settings_manager.save_setting("output/migrated_to_profiles", True)
