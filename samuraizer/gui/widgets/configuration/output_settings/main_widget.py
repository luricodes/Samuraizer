# samuraizer/gui/widgets/configuration/output_settings/main_widget.py

import os
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
from samuraizer.config.unified import UnifiedConfigManager

logger = logging.getLogger(__name__)

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
            get_file_extension_callback=self.get_file_extension
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

    def get_file_extension(self, format_name: str) -> str:
        """Get the appropriate file extension for the selected format"""
        extensions = {
            "json": ".json",
            "yaml": ".yaml",
            "xml": ".xml",
            "jsonl": ".jsonl",
            "dot": ".dot",
            "csv": ".csv",
            "s-expression": ".sexp",
            "messagepack": ".msgpack"
        }
        return extensions.get(format_name.lower(), ".txt")

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
            output_path = Path(target_path)
            output_dir = output_path.parent

            # Check if directory exists or can be created
            if not output_dir.exists():
                return output_dir.parent.exists() and output_dir.parent.is_dir()

            # Check if directory is writable
            return os.access(output_dir, os.W_OK)

        except Exception as e:
            logger.error(f"Error validating output path: {e}", exc_info=True)
            return False

    def loadSettings(self):
        """Load saved output settings"""
        try:
            # Only load settings if auto-save is enabled
            auto_save = self.settings_manager.load_setting("settings/auto_save", False, type_=bool)
            if auto_save:
                # Load format selection first
                format_name = self.settings_manager.load_setting("output/format", "Choose Output Format")
                if format_name:
                    self.format_selection_group.set_selected_format(format_name)

                # Load other settings
                streaming_enabled = self.settings_manager.load_setting("output/streaming", False, type_=bool)
                self.streaming_options_group.enable_streaming.setChecked(streaming_enabled)
                self.additional_options_group.load_settings(self.settings_manager)

                # Load last output path
                self.output_file_group.load_settings()

                # Update UI based on format - ensures proper visibility and states
                self.on_format_changed(self.format_selection_group.get_selected_format())

        except Exception as e:
            logger.error(f"Error loading output settings: {e}", exc_info=True)
        finally:
            self._apply_profile_settings()

    def saveSettings(self):
        if self._initializing or self._config_sync_lock:
            return
        try:
            config_snapshot = self.get_configuration()

            format_value = config_snapshot.get('format')
            if format_value:
                self.config_manager.set_value("analysis.default_format", format_value)

            self.config_manager.set_value(
                "analysis.include_summary",
                bool(config_snapshot.get('include_summary', True)),
            )
            self.config_manager.set_value(
                "output.streaming",
                bool(config_snapshot.get('streaming', False)),
            )
            self.config_manager.set_value(
                "output.pretty_print",
                bool(config_snapshot.get('pretty_print', False)),
            )
            self.config_manager.set_value(
                "output.compression",
                bool(config_snapshot.get('use_compression', False)),
            )

            # Only save settings if auto-save is enabled
            auto_save = self.settings_manager.load_setting("settings/auto_save", False, type_=bool)
            if auto_save:
                self.settings_manager.save_setting("output/format", self.format_selection_group.get_selected_format())
                self.settings_manager.save_setting("output/streaming", self.streaming_options_group.enable_streaming.isChecked())
                self.additional_options_group.save_settings(self.settings_manager)
                self.output_file_group.save_settings(self.settings_manager)
        except Exception as e:
            logger.error(f"Error saving output settings: {e}", exc_info=True)

    # ------------------------------------------------------------------
    # Profile synchronisation helpers
    # ------------------------------------------------------------------
    def _apply_profile_settings(self) -> None:
        if self._config_sync_lock:
            return
        with self._suspend_config_sync():
            try:
                config = self.config_manager.get_active_profile_config()
                analysis_cfg = config.get("analysis", {})
                output_cfg = config.get("output", {})

                format_label = self._format_label(analysis_cfg.get("default_format"))
                if not format_label:
                    format_label = "Choose Output Format"
                format_combo = self.format_selection_group.format_combo
                format_combo.blockSignals(True)
                self.format_selection_group.set_selected_format(format_label)
                format_combo.blockSignals(False)
                self.on_format_changed(self.format_selection_group.get_selected_format())

                streaming_checkbox = self.streaming_options_group.enable_streaming
                desired_streaming = bool(output_cfg.get("streaming", False))
                streaming_checkbox.blockSignals(True)
                streaming_checkbox.setChecked(desired_streaming and streaming_checkbox.isEnabled())
                streaming_checkbox.blockSignals(False)

                include_summary_box = self.additional_options_group.include_summary
                include_summary_box.blockSignals(True)
                include_summary_box.setChecked(bool(analysis_cfg.get("include_summary", True)))
                include_summary_box.blockSignals(False)

                pretty_box = self.additional_options_group.pretty_print
                pretty_box.blockSignals(True)
                if pretty_box.isVisible():
                    pretty_box.setChecked(bool(output_cfg.get("pretty_print", True)))
                else:
                    pretty_box.setChecked(False)
                pretty_box.blockSignals(False)

                compression_box = self.additional_options_group.use_compression
                compression_box.blockSignals(True)
                if compression_box.isVisible():
                    compression_box.setChecked(bool(output_cfg.get("compression", False)))
                else:
                    compression_box.setChecked(False)
                compression_box.blockSignals(False)

            except Exception as exc:
                logger.error("Error applying profile output settings: %s", exc, exc_info=True)

        if not self._initializing:
            self.emit_configuration_changed()

    def _handle_config_change(self) -> None:
        self._apply_profile_settings()

    def _on_destroyed(self, _obj=None) -> None:
        try:
            self.config_manager.remove_change_listener(self._handle_config_change)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Error detaching output settings listener: %s", exc)

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
