# samuraizer_gui/ui/widgets/results_display/text_result_view.py

import json
import logging
from typing import Dict, Any

from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

from PyQt6.QtWidgets import QApplication

logger = logging.getLogger(__name__)

class TextResultView(QTextEdit):
    """Text view for displaying plain text results"""
    
    def __init__(self, data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.results_data = data
        self.initUI()

    def initUI(self):
        """Initialize the user interface"""
        self.setReadOnly(True)
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        
        # Set monospace font
        font = QFont("Courier New")
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        
        # Format and display the data
        try:
            formatted_text = json.dumps(self.results_data, indent=2)
            self.setText(formatted_text)
        except Exception as e:
            logger.error(f"Error formatting text data: {e}", exc_info=True)
            self.setText(f"Error displaying results: {str(e)}")

    def copySelected(self):
        """Copy selected text to clipboard"""
        self.copy()
