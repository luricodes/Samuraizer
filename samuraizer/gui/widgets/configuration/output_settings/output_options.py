# samuraizer_gui/ui/widgets/output_options.py
import os
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLineEdit, QPushButton, QFileDialog,
    QCheckBox, QLabel, QComboBox, QFormLayout, QMessageBox
)
from PyQt6.QtCore import Qt, QSettings, pyqtSignal

logger = logging.getLogger(__name__)

class OutputOptionsWidget(QWidget):
    """Widget for configuring analysis output options"""

    outputConfigChanged = pyqtSignal(dict)  # Signal emitted when output configuration changes

    # Define formats that support pretty printing
    _pretty_print_formats = {"JSON", "XML"}
    
    # Define formats that support compression
    _compression_formats = {"MESSAGEPACK"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings()
        self.initUI()
        self.loadSettings()

    def initUI(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)

        # Output File Group
        self.createOutputGroup(layout)

        # Format Selection Group
        self.createFormatGroup(layout)

        # Stream Options Group
        self.createStreamGroup(layout)

        # Additional Options Group
        self.createOptionsGroup(layout)

        # Add stretch to keep everything aligned at the top
        layout.addStretch()

    def createFormatGroup(self, parent_layout):
        """Create the format selection group"""
        group = QGroupBox("Output Format")
        layout = QVBoxLayout()

        # Create format combo box with "Choose Output Format" as default
        self.format_combo = QComboBox()
        formats = [
            "Choose Output Format", "JSON", "YAML", "XML", "JSONL", "DOT",
            "CSV", "S-Expression", "MessagePack"
        ]
        self.format_combo.addItems(formats)
        # Set "Choose Output Format" as default
        self.format_combo.setCurrentIndex(0)
        self.format_combo.currentIndexChanged.connect(self.onFormatChanged)

        # Add format description label
        self.format_description = QLabel()
        self.format_description.setWordWrap(True)
        self.format_description.setStyleSheet("color: gray;")
        
        layout.addWidget(self.format_combo)
        layout.addWidget(self.format_description)
        
        group.setLayout(layout)
        parent_layout.addWidget(group)

    def createOutputGroup(self, parent_layout):
        """Create the output file configuration group"""
        group = QGroupBox("Output File")
        layout = QHBoxLayout()

        # Output path input
        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("Select output file location...")
        self.output_path.textChanged.connect(self.onOutputPathChanged)

        # Browse button
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browseOutputFile)
        browse_btn.setMaximumWidth(100)

        layout.addWidget(self.output_path)
        layout.addWidget(browse_btn)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    def createStreamGroup(self, parent_layout):
        """Create the streaming options group"""
        group = QGroupBox("Streaming Options")
        layout = QVBoxLayout()

        # Enable streaming checkbox
        self.enable_streaming = QCheckBox("Enable streaming mode")
        self.enable_streaming.stateChanged.connect(self.onStreamingChanged)

        # Streaming description
        streaming_desc = QLabel(
            "Streaming mode writes results incrementally, using less memory "
            "but only available for JSON, JSONL, and MessagePack formats."
        )
        streaming_desc.setWordWrap(True)
        streaming_desc.setStyleSheet("color: gray;")

        layout.addWidget(self.enable_streaming)
        layout.addWidget(streaming_desc)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    def createOptionsGroup(self, parent_layout):
        """Create additional options group"""
        group = QGroupBox("Additional Options")
        layout = QFormLayout()

        # Include summary option
        self.include_summary = QCheckBox("Include analysis summary")
        self.include_summary.setChecked(True)
        self.include_summary.stateChanged.connect(self.onOptionChanged)
        layout.addRow("", self.include_summary)

        # Pretty print option (for applicable formats)
        self.pretty_print = QCheckBox("Enable pretty printing")
        self.pretty_print.setChecked(True)
        self.pretty_print.setVisible(False)  # Hidden by default until a supporting format is selected
        self.pretty_print.stateChanged.connect(self.onOptionChanged)
        layout.addRow("", self.pretty_print)

        # Compression option (for MessagePack)
        self.use_compression = QCheckBox("Use compression")
        self.use_compression.setChecked(True)
        self.use_compression.setVisible(False)  # Hidden by default until MessagePack is selected
        self.use_compression.stateChanged.connect(self.onOptionChanged)
        layout.addRow("", self.use_compression)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    def browseOutputFile(self):
        """Open file dialog to select output file location"""
        current_format = self.format_combo.currentText().lower()
        file_extension = self.getFileExtension(current_format)
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Select Output File",
            str(Path.home()),
            f"{current_format.upper()} Files (*{file_extension})"
        )
        
        if file_path:
            # Ensure correct extension
            if not file_path.lower().endswith(file_extension):
                file_path += file_extension
            self.output_path.setText(file_path)
            # Save settings after setting the path
            self.saveSettings()

    def getFileExtension(self, format_name: str) -> str:
        """Get the appropriate file extension for the selected format"""
        extensions = {
            "json": ".json",
            "yaml": ".yaml",
            "xml": ".xml",
            "jsonl": ".jsonl",
            "dot": ".dot",
            "csv": ".csv",
            "s-expression": ".sexp",
            "messagepack": ".msgpack"
        }
        return extensions.get(format_name.lower(), ".txt")

    def onFormatChanged(self, index: int):
        """Handle format selection changes"""
        format_name = self.format_combo.currentText()
        
        # Update format description
        descriptions = {
            "JSON": "Standard JSON format with optional pretty printing",
            "YAML": "Human-readable YAML format",
            "XML": "XML format with optional pretty printing",
            "JSONL": "Newline-delimited JSON (good for streaming)",
            "DOT": "GraphViz DOT format for visualization",
            "CSV": "Comma-separated values format",
            "S-Expression": "Lisp-style S-Expression format",
            "MessagePack": "Binary MessagePack format with optional compression"
        }
        self.format_description.setText(descriptions.get(format_name, ""))

        # Update streaming availability
        format_supports_streaming = format_name.upper() in ["JSON", "JSONL", "MESSAGEPACK"]
        self.enable_streaming.setEnabled(format_supports_streaming)
        if not format_supports_streaming:
            self.enable_streaming.setChecked(False)

        # Update pretty printing availability
        supports_pretty_print = format_name in self._pretty_print_formats
        self.pretty_print.setVisible(supports_pretty_print)
        if not supports_pretty_print:
            self.pretty_print.setChecked(False)

        # Update compression availability
        supports_compression = format_name.upper() in self._compression_formats
        self.use_compression.setVisible(supports_compression)
        if not supports_compression:
            self.use_compression.setChecked(False)

        # Update file extension in output path if a format is selected
        if self.output_path.text() and format_name != "Choose Output Format":
            current_path = Path(self.output_path.text())
            new_extension = self.getFileExtension(format_name)
            new_path = current_path.with_suffix(new_extension)
            self.output_path.setText(str(new_path))
        
        self.emitConfigurationChanged()
        # Save settings after format change
        self.saveSettings()

    def onStreamingChanged(self, state):
        """Handle streaming option changes"""
        if state == Qt.CheckState.Checked:
            if not self.isStreamingSupported():
                QMessageBox.warning(
                    self,
                    "Invalid Configuration",
                    "Streaming is only available for JSON, JSONL, and MessagePack formats."
                )
                self.enable_streaming.setChecked(False)
                return
        
        self.emitConfigurationChanged()
        # Save settings after streaming change
        self.saveSettings()

    def onOutputPathChanged(self, path: str):
        """Handle output path changes"""
        self.emitConfigurationChanged()
        # Save settings after path change
        self.saveSettings()

    def onOptionChanged(self, state):
        """Handle changes to any option checkbox"""
        self.emitConfigurationChanged()
        # Save settings after option change
        self.saveSettings()

    def validateOutputPath(self, path: str) -> bool:
        """Validate the output file path"""
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

    def loadSettings(self):
        """Load saved output settings"""
        try:
            # Only load settings if auto-save is enabled
            if self.settings.value("settings/auto_save", False, type=bool):
                # Load format selection first
                format_name = self.settings.value("output/format", "Choose Output Format")
                if format_name:
                    index = self.format_combo.findText(format_name, Qt.MatchFlag.MatchFixedString)
                    if index >= 0:
                        self.format_combo.setCurrentIndex(index)

                # Load other settings
                self.enable_streaming.setChecked(self.settings.value("output/streaming", False, bool))
                self.include_summary.setChecked(self.settings.value("output/include_summary", True, bool))
                self.pretty_print.setChecked(self.settings.value("output/pretty_print", True, bool))
                self.use_compression.setChecked(self.settings.value("output/use_compression", True, bool))

                # Load last output path - removed parent directory check to allow restoring any valid path
                last_path = self.settings.value("output/last_path", "")
                if last_path:
                    self.output_path.setText(last_path)
                    logger.debug(f"Restored output path: {last_path}")

                # Update UI based on format - do this after setting the path to ensure proper extension handling
                self.onFormatChanged(self.format_combo.currentIndex())

        except Exception as e:
            logger.error(f"Error loading output settings: {e}", exc_info=True)

    def saveSettings(self):
        """Save current output settings"""
        try:
            # Only save settings if auto-save is enabled
            if self.settings.value("settings/auto_save", False, type=bool):
                # Save current output path first to ensure it's not lost during format changes
                current_path = self.output_path.text()
                if current_path:
                    self.settings.setValue("output/last_path", current_path)
                    logger.debug(f"Saved output path: {current_path}")

                self.settings.setValue("output/format", self.format_combo.currentText())
                self.settings.setValue("output/streaming", self.enable_streaming.isChecked())
                self.settings.setValue("output/include_summary", self.include_summary.isChecked())
                self.settings.setValue("output/pretty_print", self.pretty_print.isChecked())
                self.settings.setValue("output/use_compression", self.use_compression.isChecked())
                
                # Force settings to sync to disk
                self.settings.sync()
                logger.debug("Output settings saved and synced to disk")
        except Exception as e:
            logger.error(f"Error saving output settings: {e}", exc_info=True)

    def emitConfigurationChanged(self):
        """Emit signal with current configuration"""
        config = self.getConfiguration()
        self.outputConfigChanged.emit(config)

    def getConfiguration(self) -> dict:
        """Get the current output configuration"""
        return {
            'format': self.format_combo.currentText().lower(),
            'output_path': self.output_path.text(),
            'streaming': self.enable_streaming.isChecked(),
            'include_summary': self.include_summary.isChecked(),
            'pretty_print': self.pretty_print.isChecked(),
            'use_compression': self.use_compression.isChecked()
        }

    def isStreamingSupported(self) -> bool:
        """Check if the selected format supports streaming"""
        format_name = self.format_combo.currentText().upper()
        return format_name in ["JSON", "JSONL", "MESSAGEPACK"]
