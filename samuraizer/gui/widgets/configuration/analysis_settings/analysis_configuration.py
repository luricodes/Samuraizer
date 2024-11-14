# samuraizer/gui/widgets/options/analysis/analysis_configuration.py

import logging
from pathlib import Path
import mimetypes
from PyQt6.QtWidgets import (
    QWidget, QFormLayout, QSpinBox, QCheckBox, QComboBox, QGroupBox,
    QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout, QLabel,
    QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QFontDatabase, QFontInfo
from typing import Dict, Optional
import charset_normalizer

logger = logging.getLogger(__name__)

class AnalysisConfigurationWidget(QWidget):
    """Widget for configuring analysis options."""
    
    # Encoding descriptions for tooltips
    ENCODING_INFO: Dict[str, str] = {
        "auto": "Automatically detect file encoding (recommended)",
        "utf-8": "Unicode 8-bit encoding - Most common for modern text files",
        "utf-16": "Unicode 16-bit encoding - Used for Unicode text with wide characters",
        "utf-32": "Unicode 32-bit encoding - Fixed-width Unicode encoding",
        "ascii": "7-bit ASCII encoding - Basic English text",
        "iso-8859-1": "Latin-1 Western European encoding",
        "windows-1252": "Windows Western European encoding",
        "big5": "Traditional Chinese encoding",
        "gb2312": "Simplified Chinese encoding",
        "shift-jis": "Japanese encoding",
        "euc-kr": "Korean encoding",
        "koi8-r": "Russian encoding"
    }
    
    # Common file types and their typical encodings
    FILE_TYPE_ENCODINGS = {
        ".py": "utf-8",
        ".js": "utf-8",
        ".html": "utf-8",
        ".css": "utf-8",
        ".java": "utf-8",
        ".xml": "utf-8",
        ".json": "utf-8",
        ".txt": None,  # None means no specific expectation
    }
    
    # Encoding groups for organization
    ENCODING_GROUPS = [
        ("Automatic", ["auto"]),
        ("Unicode", ["utf-8", "utf-16", "utf-32"]),
        ("Western", ["ascii", "iso-8859-1", "windows-1252"]),
        ("Asian", ["big5", "gb2312", "shift-jis", "euc-kr"]),
        ("Cyrillic", ["koi8-r"])
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_preview_file: Optional[Path] = None
        self.initUI()
    
    def get_monospace_font(self) -> QFont:
        """Get a suitable monospace font for the preview."""
        # Try system-specific default monospace fonts first
        font = QFont("Consolas")  # Windows
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setFixedPitch(True)
        font.setKerning(False)  # Disable kerning for monospace
        
        # Set specific font properties
        font.setPointSize(10)
        font.setWeight(QFont.Weight.Normal)
        font.setStyleStrategy(
            QFont.StyleStrategy.PreferAntialias |
            QFont.StyleStrategy.PreferQuality
        )
        
        # Verify if we got a monospace font
        font_info = QFontInfo(font)
        if not font_info.fixedPitch():
            # If not monospace, try common alternatives
            for family in ["Courier New", "DejaVu Sans Mono", "Liberation Mono", "Monospace"]:
                font.setFamily(family)
                font_info = QFontInfo(font)
                if font_info.fixedPitch():
                    break
        
        return font
    
    def initUI(self):
        """Initialize the user interface."""
        main_layout = QVBoxLayout()
        config_layout = QFormLayout()
        
        # Max File Size
        self.max_size = QSpinBox()
        self.max_size.setRange(1, 1000)  # 1MB to 1000MB
        self.max_size.setValue(50)  # Default 50MB
        self.max_size.setSuffix(" MB")
        config_layout.addRow("Max File Size:", self.max_size)
        
        # Binary Files Option
        self.include_binary = QCheckBox("Include binary files")
        config_layout.addRow("", self.include_binary)
        
        # Follow Symlinks Option
        self.follow_symlinks = QCheckBox("Follow symbolic links")
        config_layout.addRow("", self.follow_symlinks)
        
        # Encoding Selection with Groups
        self.encoding = QComboBox()
        self.encoding.setToolTip("Select the character encoding for text files")
        
        # Add encodings with groups
        for group_name, encodings in self.ENCODING_GROUPS:
            if self.encoding.count() > 0:  # Add separator if not first group
                self.encoding.insertSeparator(self.encoding.count())
            for enc in encodings:
                self.encoding.addItem(enc)
        
        # Set tooltips for encoding options
        for i in range(self.encoding.count()):
            enc = self.encoding.itemText(i)
            if enc in self.ENCODING_INFO:
                self.encoding.setItemData(i, self.ENCODING_INFO[enc], Qt.ItemDataRole.ToolTipRole)
        
        self.encoding.setCurrentText("auto")
        config_layout.addRow("Default Encoding:", self.encoding)
        
        # Encoding Preview Section
        preview_group = QGroupBox("Encoding Preview")
        preview_layout = QVBoxLayout()
        
        # Preview controls
        controls_layout = QHBoxLayout()
        self.preview_file_path = QLabel("No file selected")
        self.preview_button = QPushButton("Select File for Preview")
        self.preview_button.setToolTip("Preview how a file would be decoded with current encoding")
        controls_layout.addWidget(self.preview_file_path)
        controls_layout.addWidget(self.preview_button)
        preview_layout.addLayout(controls_layout)
        
        # Preview text area with monospace font
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText("Select a file to preview its encoding")
        preview_font = self.get_monospace_font()
        self.preview_text.setFont(preview_font)
        
        # Set text color to ensure good contrast
        palette = self.preview_text.palette()
        palette.setColor(palette.ColorRole.Text, Qt.GlobalColor.black)
        self.preview_text.setPalette(palette)
        
        preview_layout.addWidget(self.preview_text)
        
        # Status labels for encoding detection and warnings
        self.encoding_status = QLabel("")
        self.encoding_warning = QLabel("")
        self.encoding_warning.setStyleSheet("color: orange")
        preview_layout.addWidget(self.encoding_status)
        preview_layout.addWidget(self.encoding_warning)
        
        preview_group.setLayout(preview_layout)
        
        # Add all layouts to main layout
        config_group = QGroupBox("Analysis Configuration")
        config_group.setLayout(config_layout)
        
        main_layout.addWidget(config_group)
        main_layout.addWidget(preview_group)
        self.setLayout(main_layout)
        
        # Connect signals
        self.encoding.currentTextChanged.connect(self.on_encoding_changed)
        self.preview_button.clicked.connect(self.select_preview_file)
    
    def on_encoding_changed(self, encoding: str):
        """Handle encoding selection changes."""
        if self.current_preview_file:
            self.preview_encoding(self.current_preview_file)
    
    def select_preview_file(self):
        """Open file dialog to select a file for preview."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File for Encoding Preview",
            "",
            "Text Files (*.txt *.py *.java *.cpp *.h *.cs *.js *.html *.css *.xml *.json);;All Files (*.*)"
        )
        
        if file_path:
            self.current_preview_file = Path(file_path)
            self.preview_file_path.setText(str(self.current_preview_file))
            self.preview_encoding(self.current_preview_file)
    
    def check_encoding_mismatch(self, file_path: Path, encoding: str) -> Optional[str]:
        """Check if the selected encoding matches the expected encoding for the file type."""
        suffix = file_path.suffix.lower()
        expected_encoding = self.FILE_TYPE_ENCODINGS.get(suffix)
        
        if expected_encoding and encoding != "auto" and encoding != expected_encoding:
            return f"Warning: {suffix} files typically use {expected_encoding} encoding"
        return None
    
    def preview_encoding(self, file_path: Path):
        """Preview the selected file with current encoding."""
        try:
            # Clear previous warnings
            self.encoding_warning.setText("")
            
            # Read file content
            with open(file_path, 'rb') as f:
                raw_data = f.read(self.max_size.value() * 1024 * 1024)  # Respect max file size
            
            encoding = self.encoding.currentText()
            
            # Check for encoding mismatch
            warning = self.check_encoding_mismatch(file_path, encoding)
            if warning:
                self.encoding_warning.setText(warning)
            
            if encoding == "auto":
                # Use charset_normalizer for detection
                matches = charset_normalizer.from_bytes(raw_data)
                best_match = matches.best()
                
                if best_match:
                    detected_encoding = best_match.encoding
                    content = str(best_match)
                    self.encoding_status.setText(f"Detected encoding: {detected_encoding}")
                    self.encoding_status.setStyleSheet("color: green")
                else:
                    # Fallback to utf-8
                    content = raw_data.decode('utf-8', errors='replace')
                    self.encoding_status.setText("Could not detect encoding, falling back to UTF-8")
                    self.encoding_status.setStyleSheet("color: orange")
            else:
                # Use selected encoding
                content = raw_data.decode(encoding, errors='replace')
                self.encoding_status.setText(f"Using selected encoding: {encoding}")
                self.encoding_status.setStyleSheet("color: blue")
                
                # Check for likely encoding errors
                if '\ufffd' in content[:1000]:  # Replacement character
                    self.encoding_warning.setText(
                        f"Warning: Found replacement characters. This might indicate wrong encoding selection."
                    )
            
            # Update preview
            self.preview_text.setPlainText(content[:10000])  # Limit preview size
            if len(content) > 10000:
                self.preview_text.append("\n[Preview truncated...]")
            
        except Exception as e:
            self.preview_text.setPlainText(f"Error previewing file: {str(e)}")
            self.encoding_status.setText(f"Error: {type(e).__name__}")
            self.encoding_status.setStyleSheet("color: red")
            logger.error(f"Error previewing file {file_path}: {e}", exc_info=True)
