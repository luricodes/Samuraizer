# samuraizer/gui/widgets/configuration/output_settings/main_widget.py

import os
import logging
from pathlib import Path
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QMessageBox
from PyQt6.QtCore import Qt, pyqtSignal

from .settings_manager import SettingsManager
from .output_file_group import OutputFileGroup
from .format_selection_group import FormatSelectionGroup
from .streaming_options_group import StreamingOptionsGroup
from .additional_options_group import AdditionalOptionsGroup
from .jsonl_options_group import JsonlOptionsGroup

logger = logging.getLogger(__name__)

class OutputOptionsWidget(QWidget):
    """Widget for configuring analysis output options"""

    outputConfigChanged = pyqtSignal(dict)  # Signal emitted when output configuration changes

    # Define formats that support pretty printing
    _pretty_print_formats = {"JSON", "XML"}

    # Define formats that support compression
    _compression_formats = {"MESSAGEPACK"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings_manager = SettingsManager()
        self.initUI()
        self.loadSettings()

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

        # JSONL Options Group
        self.jsonl_options_group = JsonlOptionsGroup()
        self.jsonl_options_group.optionChanged.connect(self.on_option_changed)
        layout.addWidget(self.jsonl_options_group)

        # Add stretch to keep everything aligned at the top
        layout.addStretch()

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

        # Update streaming availability
        format_upper = format_name.upper()
        format_supports_streaming = format_upper in ["JSON", "JSONL", "MESSAGEPACK"]
        self.streaming_options_group.enable_streaming.setEnabled(format_supports_streaming)
        if not format_supports_streaming:
            self.streaming_options_group.enable_streaming.setChecked(False)

        # Update pretty printing availability
        supports_pretty_print = format_name in self._pretty_print_formats
        self.additional_options_group.set_pretty_print_visible(supports_pretty_print)
        if not supports_pretty_print:
            self.additional_options_group.pretty_print.setChecked(False)

        # Update compression availability
        supports_compression = format_upper in self._compression_formats
        self.additional_options_group.set_compression_visible(supports_compression)
        if not supports_compression:
            self.additional_options_group.use_compression.setChecked(False)

        # Update JSONL options visibility
        is_jsonl = format_upper == "JSONL"
        self.jsonl_options_group.set_visible(is_jsonl)

        # Update file extension in output path if a format is selected
        if self.output_file_group.get_output_path() and format_name != "Choose Output Format":
            current_path = Path(self.output_file_group.get_output_path())
            new_extension = self.get_file_extension(format_name)
            new_path = current_path.with_suffix(new_extension)
            self.output_file_group.output_path.setText(str(new_path))

        self.emit_configuration_changed()
        self.saveSettings()

    def on_streaming_changed(self, is_enabled: bool):
        """Handle streaming option changes"""
        if is_enabled and not self.is_streaming_supported():
            QMessageBox.warning(
                self,
                "Invalid Configuration",
                "Streaming is only available for JSON, JSONL, and MessagePack formats."
            )
            self.streaming_options_group.enable_streaming.setChecked(False)
            return

        self.emit_configuration_changed()
        self.saveSettings()

    def on_output_path_changed(self, path: str):
        """Handle output path changes"""
        self.emit_configuration_changed()
        self.saveSettings()

    def on_option_changed(self):
        """Handle changes to any option checkbox"""
        self.emit_configuration_changed()
        self.saveSettings()

    def emit_configuration_changed(self):
        """Emit signal with current configuration"""
        config = self.get_configuration()
        self.outputConfigChanged.emit(config)

    def get_configuration(self) -> dict:
        """Get the current output configuration"""
        config = {
            'format': self.format_selection_group.get_selected_format().lower(),
            'output_path': self.output_file_group.get_output_path(),
            'streaming': self.streaming_options_group.enable_streaming.isChecked(),
            'include_summary': self.additional_options_group.include_summary.isChecked(),
            'pretty_print': self.additional_options_group.pretty_print.isChecked(),
            'use_compression': self.additional_options_group.use_compression.isChecked()
        }

        # Add JSONL-specific options if JSONL format is selected
        if self.format_selection_group.get_selected_format().upper() == "JSONL":
            config.update(self.jsonl_options_group.get_options())

        return config

    def validate_output_path(self, path: str) -> bool:
        """Validate the output file path"""
        if not path:
            return False

        try:
            output_path = Path(path)
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
                self.jsonl_options_group.load_settings(self.settings_manager)

                # Load last output path
                self.output_file_group.load_settings()

                # Update UI based on format - ensures proper visibility and states
                self.on_format_changed(self.format_selection_group.get_selected_format())

        except Exception as e:
            logger.error(f"Error loading output settings: {e}", exc_info=True)

    def saveSettings(self):
        try:
            # Only save settings if auto-save is enabled
            auto_save = self.settings_manager.load_setting("settings/auto_save", False, type_=bool)
            if auto_save:
                self.settings_manager.save_setting("output/format", self.format_selection_group.get_selected_format())
                self.settings_manager.save_setting("output/streaming", self.streaming_options_group.enable_streaming.isChecked())
                self.additional_options_group.save_settings(self.settings_manager)
                self.jsonl_options_group.save_settings(self.settings_manager)
                self.output_file_group.save_settings(self.settings_manager)
        except Exception as e:
            logger.error(f"Error saving output settings: {e}", exc_info=True)

    def is_streaming_supported(self) -> bool:
        """Check if the selected format supports streaming"""
        format_name = self.format_selection_group.get_selected_format().upper()
        return format_name in ["JSON", "JSONL", "MESSAGEPACK"]
