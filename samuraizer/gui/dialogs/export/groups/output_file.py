# samuraizer/gui/dialogs/export/groups/output_file.py
import logging
import os
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QMessageBox,
)

from ..base import BaseExportGroup

if TYPE_CHECKING:
    from ..export_dialog import ExportDialog

logger = logging.getLogger(__name__)


class OutputFileGroup(BaseExportGroup):
    """Group for output file selection."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("Output File", parent)

    def _parent_dialog(self) -> Optional["ExportDialog"]:
        parent = self.parent()
        if isinstance(parent, BaseExportGroup):
            # Parent of the group is the dialog
            parent = parent.parent()
        if parent is None:
            return None
        try:
            from ..export_dialog import ExportDialog
        except Exception:
            return None
        return parent if isinstance(parent, ExportDialog) else None

    def setup_ui(self) -> None:
        """Set up the output file selection UI."""
        try:
            layout = QHBoxLayout()
            layout.setSpacing(10)

            # Output path input
            self.path_input = QLineEdit()
            self.path_input.setPlaceholderText("Select output file location...")
            self.path_input.textChanged.connect(self.validate_output_path)
            
            # Browse button
            browse_btn = QPushButton("Browse...")
            browse_btn.clicked.connect(self.browse_output_location)
            browse_btn.setMaximumWidth(100)
            
            layout.addWidget(self.path_input)
            layout.addWidget(browse_btn)
            
            self.setLayout(layout)
            
        except Exception as e:
            logger.error(f"Error setting up output file UI: {e}", exc_info=True)
            raise

    def browse_output_location(self) -> None:
        """Open file dialog to select output location."""
        try:
            dialog = self._parent_dialog()
            if dialog is None:
                return
            export_formats = dialog.format_group.EXPORT_FORMATS
            format_name = dialog.format_group.format_combo.currentText()
            extension = export_formats[format_name][0]
            
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Select Export Location",
                str(Path.home()),
                f"{format_name} Files (*{extension})"
            )
            
            if file_path:
                # Ensure correct extension
                if not file_path.lower().endswith(extension):
                    file_path += extension
                self.path_input.setText(file_path)

        except Exception as e:
            logger.error(f"Error browsing output location: {e}", exc_info=True)
            dialog = self._parent_dialog()
            if dialog is not None:
                dialog.show_error("File Selection Error", str(e))

    def validate_output_path(self, path: str) -> bool:
        """Validate the output file path."""
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

    def validate(self) -> bool:
        """Validate the output configuration."""
        try:
            if not self.path_input.text().strip():
                dialog = self._parent_dialog()
                if dialog is not None:
                    dialog.show_error(
                        "Invalid Configuration",
                        "Please select an output file location.",
                    )
                return False

            output_path = Path(self.path_input.text())
            output_dir = output_path.parent

            # Check if directory exists or can be created
            if not output_dir.exists():
                try:
                    output_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    dialog = self._parent_dialog()
                    if dialog is not None:
                        dialog.show_error(
                            "Invalid Output Location",
                            f"Cannot create output directory: {str(e)}",
                        )
                    return False

            # Check if location is writable
            if not os.access(output_dir, os.W_OK):
                dialog = self._parent_dialog()
                if dialog is not None:
                    dialog.show_error(
                        "Invalid Output Location",
                        "Output location is not writable",
                    )
                return False

            return True
            
        except Exception as e:
            logger.error(f"Error validating output configuration: {e}", exc_info=True)
            dialog = self._parent_dialog()
            if dialog is not None:
                dialog.show_error("Validation Error", str(e))
            return False

    def load_settings(self) -> None:
        """Load output settings."""
        try:
            last_dir = self.settings.value("export/last_directory", "")
            if last_dir:
                self.path_input.setText(last_dir)
        except Exception as e:
            logger.error(f"Error loading output settings: {e}", exc_info=True)
            raise

    def save_settings(self) -> None:
        """Save output settings."""
        try:
            output_path = Path(self.path_input.text())
            self.settings.setValue(
                "export/last_directory",
                str(output_path.parent)
            )
        except Exception as e:
            logger.error(f"Error saving output settings: {e}", exc_info=True)
            raise
