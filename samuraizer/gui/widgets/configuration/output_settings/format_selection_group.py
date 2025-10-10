# output_options/format_selection_group.py

import logging
from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QComboBox, QLabel
)
from PyQt6.QtCore import pyqtSignal, Qt

logger = logging.getLogger(__name__)

class FormatSelectionGroup(QGroupBox):
    formatChanged = pyqtSignal(str)

    _descriptions = {
        "JSON": "Standard JSON format with optional pretty printing",
        "YAML": "Human-readable YAML format",
        "XML": "XML format with optional pretty printing",
        "JSONL": "JSON Lines format ideal for streaming large result sets",
        "DOT": "GraphViz DOT format for visualization",
        "CSV": "Comma-separated values format",
        "S-Expression": "Lisp-style S-Expression format",
        "MessagePack": "Binary MessagePack format with optional compression"
    }

    def __init__(self, parent=None):
        super().__init__("Output Format", parent)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        self.format_combo = QComboBox()
        formats = [
            "Choose Output Format", "JSON", "YAML", "XML", "JSONL", "DOT",
            "CSV", "S-Expression", "MessagePack"
        ]
        self.format_combo.addItems(formats)
        self.format_combo.setCurrentIndex(0)
        self.format_combo.currentTextChanged.connect(self.on_format_changed)

        self.format_description = QLabel()
        self.format_description.setWordWrap(True)
        self.format_description.setStyleSheet("color: gray;")

        layout.addWidget(self.format_combo)
        layout.addWidget(self.format_description)

        self.setLayout(layout)

    def on_format_changed(self, format_name):
        self.format_description.setText(self._descriptions.get(format_name, ""))
        self.formatChanged.emit(format_name)

    def get_selected_format(self) -> str:
        return self.format_combo.currentText()

    def set_selected_format(self, format_name: str):
        index = self.format_combo.findText(format_name, Qt.MatchFlag.MatchFixedString)
        if index >= 0:
            self.format_combo.setCurrentIndex(index)
