# samuraizer/gui/dialogs/export/groups/format_selection.py
from typing import Optional, Dict, Tuple
import logging
from PyQt6.QtWidgets import QWidget, QFormLayout, QComboBox
from PyQt6.QtCore import Qt, pyqtSignal

from ..base import BaseExportGroup

logger = logging.getLogger(__name__)

class FormatSelectionGroup(BaseExportGroup):
    """Group for export format selection."""

    # Define available export formats with their extensions and descriptions
    EXPORT_FORMATS: Dict[str, Tuple[str, str]] = {
        'JSON': ('.json', 'JavaScript Object Notation - Standard hierarchical format'),
        'YAML': ('.yaml', 'YAML Ain\'t Markup Language - Human-readable format'),
        'XML': ('.xml', 'Extensible Markup Language - Structured format'),
        'CSV': ('.csv', 'Comma-Separated Values - Tabular format'),
        'DOT': ('.dot', 'GraphViz DOT - Graph visualization format'),
        'NDJSON': ('.ndjson', 'Newline-Delimited JSON - Streaming-friendly format'),
        'S-Expression': ('.sexp', 'S-Expression format - Lisp-style format'),
        'MessagePack': ('.msgpack', 'MessagePack binary format - Compact binary format')
    }

    format_changed = pyqtSignal(str)  # Signal emitted when format changes

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("Export Format", parent)

    def setup_ui(self) -> None:
        """Set up the format selection UI."""
        try:
            layout = QFormLayout()
            layout.setSpacing(10)

            # Format combo box
            self.format_combo = QComboBox()
            self.format_combo.addItem("Choose Output Format")  # Add default option
            self.format_combo.addItems(self.EXPORT_FORMATS.keys())
            self.format_combo.currentTextChanged.connect(self._on_format_changed)
            self.format_combo.setToolTip("Select the output format for the export")
            
            layout.addRow("Format:", self.format_combo)
            self.setLayout(layout)
            
        except Exception as e:
            logger.error(f"Error setting up format selection UI: {e}", exc_info=True)
            raise

    def _on_format_changed(self, format_name: str) -> None:
        """Handle format selection changes."""
        self.format_changed.emit(format_name)

    def load_settings(self) -> None:
        """Load format settings."""
        try:
            format_name = self.settings.value("export/format", "Choose Output Format")
            index = self.format_combo.findText(
                format_name,
                Qt.MatchFlag.MatchFixedString
            )
            if index >= 0:
                self.format_combo.setCurrentIndex(index)
        except Exception as e:
            logger.error(f"Error loading format settings: {e}", exc_info=True)
            raise

    def save_settings(self) -> None:
        """Save format settings."""
        try:
            self.settings.setValue("export/format", self.format_combo.currentText())
        except Exception as e:
            logger.error(f"Error saving format settings: {e}", exc_info=True)
            raise
