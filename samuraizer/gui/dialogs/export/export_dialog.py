# samuraizer/gui/dialogs/export/export_dialog.py
from typing import Optional, Tuple, Dict, Any, TYPE_CHECKING
import logging
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QLabel, QWidget

from ..base_dialog import BaseDialog
from .groups import (
    FormatSelectionGroup,
    OutputFileGroup,
    ExportOptionsGroup
)

if TYPE_CHECKING:
    from ...windows.main.components.window import MainWindow

logger = logging.getLogger(__name__)

class ExportDialog(BaseDialog):
    """Dialog for configuring and executing result exports."""
    
    def __init__(self, parent: Optional['QWidget'] = None) -> None:
        super().__init__(
            parent=parent,
            title="Export Results",
            modal=True,
            minimum_size=QSize(500, 400),
            settings_prefix="export_dialog"
        )

    def setup_ui(self) -> None:
        """Set up the dialog's user interface."""
        try:
            # Create format selection group
            self.format_group = FormatSelectionGroup(self)
            self.main_layout.addWidget(self.format_group)
            
            # Set default format to "Choose Output Format"
            self.format_group.format_combo.setCurrentText("Choose Output Format")
            
            # Create output file group
            self.output_group = OutputFileGroup(self)
            self.main_layout.addWidget(self.output_group)
            
            # Create export options group
            self.options_group = ExportOptionsGroup(self)
            self.main_layout.addWidget(self.options_group)
            
            # Format description label
            self.format_description = QLabel()
            self.format_description.setWordWrap(True)
            self.format_description.setStyleSheet("color: gray;")
            self.format_description.setFont(QFont("Segoe UI", 9))
            self.main_layout.addWidget(self.format_description)
            
            # Connect format change signal
            self.format_group.format_combo.currentTextChanged.connect(
                self.update_format_description
            )
            
            # Initial format description update
            self.update_format_description(self.format_group.format_combo.currentText())
            
        except Exception as e:
            logger.error(f"Error setting up export dialog UI: {e}", exc_info=True)
            self.show_error("UI Error", f"Failed to initialize export dialog: {str(e)}")

    def update_format_description(self, format_name: str) -> None:
        """Update the format description text."""
        if format_name in FormatSelectionGroup.EXPORT_FORMATS:
            extension, description = FormatSelectionGroup.EXPORT_FORMATS[format_name]
            self.format_description.setText(
                f"{description}\nFile extension: {extension}"
            )

    def load_settings(self) -> None:
        """Load saved export settings."""
        try:
            self.format_group.load_settings()
            self.output_group.load_settings()
            self.options_group.load_settings()
        except Exception as e:
            logger.error(f"Error loading export settings: {e}", exc_info=True)
            self.show_error("Settings Error", str(e))

    def save_settings(self) -> None:
        """Save current export settings."""
        try:
            self.format_group.save_settings()
            self.output_group.save_settings()
            self.options_group.save_settings()
        except Exception as e:
            logger.error(f"Error saving export settings: {e}", exc_info=True)
            self.show_error("Settings Error", str(e))

    def validate(self) -> bool:
        """Validate the export configuration."""
        try:
            return all([
                self.format_group.validate(),
                self.output_group.validate(),
                self.options_group.validate()
            ])
        except Exception as e:
            logger.error(f"Error validating export configuration: {e}", exc_info=True)
            self.show_error("Validation Error", str(e))
            return False

    def get_export_options(self) -> Tuple[str, str]:
        """Get the selected export options."""
        format_name = self.format_group.format_combo.currentText().lower()
        output_path = self.output_group.path_input.text()
        
        # Append the correct file extension if not present
        if format_name in FormatSelectionGroup.EXPORT_FORMATS:
            extension, _ = FormatSelectionGroup.EXPORT_FORMATS[format_name]
            if not output_path.endswith(extension):
                output_path += extension
        
        return format_name, output_path

    def get_export_configuration(self) -> Dict[str, Any]:
        """Get complete export configuration."""
        return {
            'format': self.format_group.format_combo.currentText().lower(),
            'output_path': self.output_group.path_input.text(),
            'include_summary': self.options_group.include_summary.isChecked(),
            'pretty_print': self.options_group.pretty_print.isChecked(),
            'streaming': self.options_group.enable_streaming.isChecked(),
            'use_compression': self.options_group.use_compression.isChecked()
        }
