# output_options/additional_options_group.py

import logging
from PyQt6.QtWidgets import (
    QGroupBox, QFormLayout, QCheckBox
)
from PyQt6.QtCore import pyqtSignal

logger = logging.getLogger(__name__)

class AdditionalOptionsGroup(QGroupBox):
    optionChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("Additional Options", parent)
        self.initUI()

    def initUI(self):
        layout = QFormLayout()

        self.include_summary = QCheckBox("Include analysis summary")
        self.include_summary.setChecked(True)
        self.include_summary.stateChanged.connect(self.on_option_changed)
        layout.addRow("", self.include_summary)

        self.pretty_print = QCheckBox("Enable pretty printing")
        self.pretty_print.setChecked(True)
        self.pretty_print.setVisible(False)  # Controlled by format selection
        self.pretty_print.stateChanged.connect(self.on_option_changed)
        layout.addRow("", self.pretty_print)

        self.use_compression = QCheckBox("Use compression")
        self.use_compression.setChecked(True)
        self.use_compression.setVisible(False)  # Controlled by format selection
        self.use_compression.stateChanged.connect(self.on_option_changed)
        layout.addRow("", self.use_compression)

        self.setLayout(layout)

    def on_option_changed(self, state):
        self.optionChanged.emit()

    def set_pretty_print_visible(self, visible: bool):
        self.pretty_print.setVisible(visible)
        if not visible:
            self.pretty_print.setChecked(False)

    def set_compression_visible(self, visible: bool):
        self.use_compression.setVisible(visible)
        if not visible:
            self.use_compression.setChecked(False)

    def load_settings(self, settings_manager):
        self.include_summary.setChecked(settings_manager.load_setting("output/include_summary", True, type_=bool))
        self.pretty_print.setChecked(settings_manager.load_setting("output/pretty_print", True, type_=bool))
        self.use_compression.setChecked(settings_manager.load_setting("output/use_compression", True, type_=bool))

    def save_settings(self, settings_manager):
        settings_manager.save_setting("output/include_summary", self.include_summary.isChecked())
        settings_manager.save_setting("output/pretty_print", self.pretty_print.isChecked())
        settings_manager.save_setting("output/use_compression", self.use_compression.isChecked())

    def get_options(self) -> dict:
        return {
            'include_summary': self.include_summary.isChecked(),
            'pretty_print': self.pretty_print.isChecked(),
            'use_compression': self.use_compression.isChecked()
        }

    def set_options(self, options: dict):
        self.include_summary.setChecked(options.get('include_summary', True))
        self.pretty_print.setChecked(options.get('pretty_print', True))
        self.use_compression.setChecked(options.get('use_compression', True))
