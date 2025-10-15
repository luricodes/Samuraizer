from typing import Optional, TYPE_CHECKING, Protocol, cast
import logging
from PyQt6.QtWidgets import (
    QWidget, QFormLayout, QCheckBox,
    QMessageBox
)
from PyQt6.QtCore import Qt

from ..base import BaseExportGroup
from .format_selection import FormatSelectionGroup

if TYPE_CHECKING:
    from ..export_dialog import ExportDialog


class _ExportDialogProtocol(Protocol):
    format_group: FormatSelectionGroup

    def show_error(self, title: str, message: str) -> None:
        ...

logger = logging.getLogger(__name__)

class ExportOptionsGroup(BaseExportGroup):
    """Group for export options."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("Export Options", parent)

    def _get_parent_dialog(self) -> Optional['_ExportDialogProtocol']:
        parent = self.parent()
        if parent is None:
            return None
        try:
            from ..export_dialog import ExportDialog  # Local import to avoid circular dependency
        except Exception:  # pragma: no cover - defensive guard
            return None

        if isinstance(parent, ExportDialog):
            return cast('_ExportDialogProtocol', parent)
        return None

    def setup_ui(self) -> None:
        """Set up the export options UI."""
        try:
            layout = QFormLayout()
            layout.setSpacing(10)

            # Include summary option
            self.include_summary = QCheckBox("Include analysis summary")
            self.include_summary.setChecked(True)
            self.include_summary.setToolTip("Add summary statistics to the export")
            layout.addRow("", self.include_summary)

            # Pretty print option
            self.pretty_print = QCheckBox("Enable pretty printing")
            self.pretty_print.setChecked(True)
            self.pretty_print.setToolTip("Format output for better readability")
            layout.addRow("", self.pretty_print)

            # Streaming option
            self.enable_streaming = QCheckBox("Enable streaming mode")
            self.enable_streaming.setToolTip(
                "Use streaming for large datasets (JSON/JSONL/MessagePack only)"
            )
            self.enable_streaming.stateChanged.connect(self.on_streaming_changed)
            layout.addRow("", self.enable_streaming)

            # Compression option (for MessagePack)
            self.use_compression = QCheckBox("Use compression")
            self.use_compression.setChecked(True)
            self.use_compression.setEnabled(False)
            self.use_compression.setToolTip("Enable data compression (MessagePack only)")
            layout.addRow("", self.use_compression)

            self.setLayout(layout)
            
        except Exception as e:
            logger.error(f"Error setting up export options UI: {e}", exc_info=True)
            raise

    def on_streaming_changed(self, state: int) -> None:
        """Handle streaming option changes."""
        try:
            if state == Qt.CheckState.Checked.value:
                dialog = self._get_parent_dialog()
                if dialog is None:
                    logger.warning("Streaming changed without a valid export dialog parent")
                    self.enable_streaming.setChecked(False)
                    return
                format_name = dialog.format_group.format_combo.currentText()
                if format_name.upper() not in ["JSON", "JSONL", "MESSAGEPACK"]:
                    dialog.show_error(
                        "Invalid Configuration",
                        "Streaming is only available for JSON, JSONL, "
                        "and MessagePack formats."
                    )
                    self.enable_streaming.setChecked(False)

        except Exception as e:
            logger.error(f"Error handling streaming change: {e}", exc_info=True)
            dialog = self._get_parent_dialog()
            if dialog is not None:
                dialog.show_error("Configuration Error", str(e))

    def update_options_state(self, format_name: str) -> None:
        """Update options state based on selected format."""
        try:
            # Update streaming availability
            format_supports_streaming = format_name.upper() in ["JSON", "JSONL", "MESSAGEPACK"]
            self.enable_streaming.setEnabled(format_supports_streaming)
            if not format_supports_streaming:
                self.enable_streaming.setChecked(False)
            
            # Update compression availability
            self.use_compression.setEnabled(format_name.upper() == "MESSAGEPACK")
            if not self.use_compression.isEnabled():
                self.use_compression.setChecked(False)
            
        except Exception as e:
            logger.error(f"Error updating options state: {e}", exc_info=True)
            dialog = self._get_parent_dialog()
            if dialog is not None:
                dialog.show_error("Configuration Error", str(e))

    def load_settings(self) -> None:
        """Load export options settings."""
        try:
            self.include_summary.setChecked(
                self.settings.value("export/include_summary", True, bool)
            )
            self.pretty_print.setChecked(
                self.settings.value("export/pretty_print", True, bool)
            )
            self.enable_streaming.setChecked(
                self.settings.value("export/streaming", False, bool)
            )
            self.use_compression.setChecked(
                self.settings.value("export/use_compression", True, bool)
            )
        except Exception as e:
            logger.error(f"Error loading export options settings: {e}", exc_info=True)
            raise

    def save_settings(self) -> None:
        """Save export options settings."""
        try:
            self.settings.setValue(
                "export/include_summary",
                self.include_summary.isChecked()
            )
            self.settings.setValue(
                "export/pretty_print",
                self.pretty_print.isChecked()
            )
            self.settings.setValue(
                "export/streaming",
                self.enable_streaming.isChecked()
            )
            self.settings.setValue(
                "export/use_compression",
                self.use_compression.isChecked()
            )
        except Exception as e:
            logger.error(f"Error saving export options settings: {e}", exc_info=True)
            raise
