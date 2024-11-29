# output_options/output_file_group.py

import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QGroupBox, QHBoxLayout, QLineEdit, QPushButton, QFileDialog
)
from PyQt6.QtCore import pyqtSignal

logger = logging.getLogger(__name__)

class OutputFileGroup(QGroupBox):
    outputPathChanged = pyqtSignal(str)

    def __init__(self, settings_manager, get_file_extension_callback, parent=None):
        super().__init__("Output File", parent)
        self.settings_manager = settings_manager
        self.get_file_extension = get_file_extension_callback
        self.initUI()

    def initUI(self):
        layout = QHBoxLayout()

        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("Select output file location...")
        self.output_path.textChanged.connect(self.on_output_path_changed)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_output_file)
        browse_btn.setMaximumWidth(100)

        layout.addWidget(self.output_path)
        layout.addWidget(browse_btn)

        self.setLayout(layout)

    def browse_output_file(self):
        # Assume format_combo is accessible via parent or another mechanism
        # Here, we'll emit a signal or use a callback to get the current format
        # For simplicity, let's assume a callback is provided
        format_name = self.parent().format_selection_group.get_selected_format()
        file_extension = self.get_file_extension(format_name.lower())

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Select Output File",
            str(Path.home()),
            f"{format_name.upper()} Files (*{file_extension})"
        )

        if file_path:
            if not file_path.lower().endswith(file_extension):
                file_path += file_extension
            self.output_path.setText(file_path)
            self.settings_manager.save_setting("output/last_path", file_path)

    def on_output_path_changed(self, path):
        self.outputPathChanged.emit(path)
        self.settings_manager.save_setting("output/last_path", path)

    def load_settings(self):
        last_path = self.settings_manager.load_setting("output/last_path", "")
        if last_path:
            self.output_path.setText(last_path)

    def save_settings(self, settings_manager):
        """Save output file settings"""
        current_path = self.output_path.text()
        if current_path:
            settings_manager.save_setting("output/last_path", current_path)
            logger.debug(f"Saved output path: {current_path}")

    def get_output_path(self) -> str:
        return self.output_path.text()
