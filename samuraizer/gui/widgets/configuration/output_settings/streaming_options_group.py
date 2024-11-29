# output_options/streaming_options_group.py

import logging
from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QCheckBox, QLabel, QMessageBox
)
from PyQt6.QtCore import pyqtSignal, Qt

logger = logging.getLogger(__name__)

class StreamingOptionsGroup(QGroupBox):
    streamingChanged = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__("Streaming Options", parent)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        self.enable_streaming = QCheckBox("Enable streaming mode")
        self.enable_streaming.stateChanged.connect(self.on_streaming_changed)

        streaming_desc = QLabel(
            "Streaming mode writes results incrementally, using less memory "
            "but only available for JSON, JSONL, and MessagePack formats."
        )
        streaming_desc.setWordWrap(True)
        streaming_desc.setStyleSheet("color: gray;")

        layout.addWidget(self.enable_streaming)
        layout.addWidget(streaming_desc)

        self.setLayout(layout)

    def on_streaming_changed(self, state):
        is_checked = state == Qt.CheckState.Checked
        self.streamingChanged.emit(is_checked)
