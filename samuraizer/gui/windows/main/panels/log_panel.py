from typing import Optional, Dict, List
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QToolBar,
    QPushButton, QComboBox, QLineEdit, QFileDialog, QLabel,
    QSpinBox, QStyle, QMenu, QToolTip, QSizePolicy, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSlot, QSettings, QSize, QTimer
from PyQt6.QtGui import (
    QTextCursor, QColor, QTextCharFormat, QFont,
    QAction, QIcon, QTextDocument
)
import logging
from .....utils.log_handler import GuiLogHandler

class LogPanel(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.settings = QSettings()
        self.log_levels = {
            "All": -1,
            "Debug": logging.DEBUG,
            "Info": logging.INFO,
            "Warning": logging.WARNING,
            "Error": logging.ERROR,
            "Critical": logging.CRITICAL
        }
        self.current_filter = logging.INFO
        self.search_text = ""
        self.auto_scroll = True
        self.line_count = 0
        
        # Set size policy to allow complete collapse
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        
        self.initUI()
        self.loadSettings()

    def sizeHint(self) -> QSize:
        """Override sizeHint to provide a good default size."""
        return QSize(600, 150)

    def minimumSizeHint(self) -> QSize:
        """Override minimumSizeHint to allow complete collapse."""
        return QSize(0, 0)

    def saveSettings(self):
        """Save panel state."""
        settings = QSettings()
        settings.setValue("log_panel/level", self.level_filter.currentText())
        settings.setValue("log_panel/auto_scroll", self.auto_scroll)
        settings.setValue("log_panel/buffer_size", self.buffer_size.value())

    def loadSettings(self):
        """Load panel state."""
        settings = QSettings()
        
        # Load level filter
        level = settings.value("log_panel/level", "Info")
        index = self.level_filter.findText(level)
        if index >= 0:
            self.level_filter.setCurrentIndex(index)
            self.setLogLevel(level)
            
        # Load auto-scroll
        auto_scroll = settings.value("log_panel/auto_scroll", True, type=bool)
        self.auto_scroll_btn.setChecked(auto_scroll)
        self.auto_scroll = auto_scroll
        
        # Load buffer size
        buffer_size = settings.value("log_panel/buffer_size", 1000, type=int)
        self.buffer_size.setValue(buffer_size)

    def initUI(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create toolbar
        toolbar = QToolBar()
        toolbar.setFixedHeight(32)  # Fixed height for consistent appearance
        layout.addWidget(toolbar)

        # Add level filter combo box
        self.level_filter = QComboBox()
        self.level_filter.addItems(self.log_levels.keys())
        self.level_filter.currentTextChanged.connect(self.setLogLevel)
        toolbar.addWidget(QLabel("Level:"))
        toolbar.addWidget(self.level_filter)
        toolbar.addSeparator()
        
        # Add auto-scroll toggle
        self.auto_scroll_btn = QPushButton("Auto-scroll")
        self.auto_scroll_btn.setCheckable(True)
        self.auto_scroll_btn.setChecked(True)
        self.auto_scroll_btn.toggled.connect(self.toggleAutoScroll)
        toolbar.addWidget(self.auto_scroll_btn)
        toolbar.addSeparator()

        # Add buffer controls
        buffer_container = QWidget()
        buffer_layout = QHBoxLayout(buffer_container)
        buffer_layout.setContentsMargins(0, 0, 0, 0)
        
        buffer_label = QLabel("Buffer Size:")
        buffer_label.setToolTip(
            "Maximum number of log entries to keep.\n"
            "When this limit is reached, oldest entries\n"
            "will be automatically removed."
        )
        buffer_layout.addWidget(buffer_label)
        
        self.buffer_size = QSpinBox()
        self.buffer_size.setRange(100, 10000)
        self.buffer_size.setSingleStep(100)
        self.buffer_size.setValue(1000)
        self.buffer_size.valueChanged.connect(self.setBufferSize)
        self.buffer_size.setToolTip(
            "Maximum number of log entries to keep.\n"
            "When this limit is reached, oldest entries\n"
            "will be automatically removed."
        )
        buffer_layout.addWidget(self.buffer_size)
        
        # Add entry counter
        self.entry_counter = QLabel("Entries: 0/1000")
        self.entry_counter.setToolTip(
            "Current number of entries / Maximum buffer size\n"
            "Oldest entries are automatically removed when limit is reached"
        )
        buffer_layout.addWidget(self.entry_counter)
        
        toolbar.addWidget(buffer_container)
        toolbar.addSeparator()

        # Add search controls
        search_container = QWidget()
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(6)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search logs…")
        self.search_input.textChanged.connect(self.searchLogs)
        self.search_input.returnPressed.connect(self.findNext)
        search_layout.addWidget(self.search_input)

        self.prev_button = QPushButton("Previous")
        self.prev_button.setEnabled(False)
        self.prev_button.clicked.connect(lambda: self.findPrevious())
        search_layout.addWidget(self.prev_button)

        self.next_button = QPushButton("Next")
        self.next_button.setEnabled(False)
        self.next_button.clicked.connect(lambda: self.findNext())
        search_layout.addWidget(self.next_button)

        toolbar.addWidget(search_container)
        toolbar.addSeparator()

        # Add clear and save buttons
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clearLog)
        toolbar.addWidget(clear_btn)
        
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.saveLogsToFile)
        toolbar.addWidget(save_btn)
        
        # Enhanced log display configuration
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("Consolas", 10))
        self.log_display.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.log_display.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.log_display.customContextMenuRequested.connect(self.showContextMenu)
        
        # Set size policy for text display to allow collapse
        self.log_display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        
        layout.addWidget(self.log_display)

    # Rest of the class implementation remains the same...
    def showContextMenu(self, position):
        """Show context menu for log display."""
        menu = QMenu(self)
        
        copy_action = menu.addAction("Copy")
        copy_action.triggered.connect(self.copySelectedLogs)
        
        select_all_action = menu.addAction("Select All")
        select_all_action.triggered.connect(self.log_display.selectAll)
        
        menu.addSeparator()
        
        save_action = menu.addAction("Save Logs...")
        save_action.triggered.connect(self.saveLogsToFile)
        
        clear_action = menu.addAction("Clear")
        clear_action.triggered.connect(self.clearLog)
        
        menu.exec(self.log_display.mapToGlobal(position))

    def setLogHandler(self, handler: GuiLogHandler):
        """Set the GUI log handler and connect signals."""
        self.gui_log_handler = handler
        handler.log_record_received.connect(self.addLogMessage)
        handler.batch_records_received.connect(self.addBatchMessages)
        
        # Initialize with current buffer content
        self.clearLog()
        buffer = handler.getBuffer()
        if buffer:
            entries = [{
                'message': entry.formatted,
                'level': entry.level,
                'color': entry.color,
                'timestamp': entry.timestamp,
                'buffer_size': len(buffer)
            } for entry in buffer]
            self.addBatchMessages(entries)

    def removeOldestEntry(self):
        """Remove the oldest entry from the display."""
        cursor = self.log_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.deletePreviousChar()  # Remove the newline
        self.line_count -= 1
        self.updateEntryCount()

    @pyqtSlot(dict)
    def addLogMessage(self, log_data: Dict):
        """Add a single log message to the display."""
        if self.current_filter > log_data['level']:
            return

        # Remove oldest entry if buffer is full
        if self.line_count >= self.buffer_size.value():
            self.removeOldestEntry()
            
        self._appendMessage(log_data)
        self.line_count += 1
        self.updateEntryCount()

    @pyqtSlot(list)
    def addBatchMessages(self, messages: List[Dict]):
        """Add multiple log messages at once."""
        filtered_messages = [
            msg for msg in messages
            if self.current_filter <= msg['level']
        ]
        
        if not filtered_messages:
            return

        # Remove oldest entries if needed
        while self.line_count + len(filtered_messages) > self.buffer_size.value():
            self.removeOldestEntry()
            
        # Temporarily disable auto-scroll for batch processing
        current_auto_scroll = self.auto_scroll
        self.auto_scroll = False
        
        for message in filtered_messages[:-1]:
            self._appendMessage(message)
            
        # Re-enable auto-scroll for last message if it was enabled
        self.auto_scroll = current_auto_scroll
        if filtered_messages:
            self._appendMessage(filtered_messages[-1])
        
        self.line_count += len(filtered_messages)
        self.updateEntryCount()

    def updateEntryCount(self):
        """Update the entry counter display."""
        max_size = self.buffer_size.value()
        self.entry_counter.setText(f"Entries: {self.line_count}/{max_size}")
        
        # Show warning if buffer is near capacity
        if self.line_count >= max_size * 0.9:  # 90% full
            self.entry_counter.setStyleSheet("color: orange;")
            QToolTip.showText(
                self.entry_counter.mapToGlobal(self.entry_counter.rect().topRight()),
                "Buffer is nearly full! Oldest entries will be removed soon.",
                self.entry_counter
            )
        else:
            self.entry_counter.setStyleSheet("")

    def _appendMessage(self, log_data: Dict):
        """Internal method to append a message to the display."""
        format = QTextCharFormat()
        format.setForeground(QColor(log_data['color']))
        
        cursor = self.log_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(log_data['message'] + '\n', format)
        
        if self.auto_scroll:
            self.log_display.setTextCursor(cursor)
            self.log_display.ensureCursorVisible()

    def setLogLevel(self, level_name: str):
        """Set the log level filter."""
        self.current_filter = self.log_levels[level_name]
        
        # Update root logger level
        root_logger = logging.getLogger()
        if level_name == "All":
            root_logger.setLevel(logging.DEBUG)
        else:
            root_logger.setLevel(self.current_filter)
        
        # Clear and reload logs from buffer if handler exists
        if hasattr(self, 'gui_log_handler'):
            self.log_display.clear()
            buffer = self.gui_log_handler.getBuffer()
            self.line_count = 0
            for entry in buffer:
                if self.current_filter <= entry.level:
                    self._appendMessage({
                        'message': entry.formatted,
                        'level': entry.level,
                        'color': entry.color,
                        'timestamp': entry.timestamp,
                        'buffer_size': len(buffer)
                    })
                    self.line_count += 1
            self.updateEntryCount()
        
        self.saveSettings()

    def searchLogs(self, text: str):
        """Search through log messages."""
        self.search_text = text
        if text:
            self.findNext()
        else:
            self.prev_button.setEnabled(False)
            self.next_button.setEnabled(False)

    def findNext(self):
        """Find next occurrence of search text."""
        if not self.search_text:
            return
        found = self.log_display.find(self.search_text)
        self.prev_button.setEnabled(found)
        self.next_button.setEnabled(found)

    def findPrevious(self):
        """Find previous occurrence of search text."""
        if not self.search_text:
            return
        found = self.log_display.find(
            self.search_text,
            QTextDocument.FindFlag.FindBackward
        )
        self.prev_button.setEnabled(found)
        self.next_button.setEnabled(found)

    def toggleAutoScroll(self, enabled: bool):
        """Toggle auto-scrolling of log messages."""
        self.auto_scroll = enabled
        self.saveSettings()

    def setBufferSize(self, size: int):
        """Set the maximum number of log messages to keep."""
        if hasattr(self, 'gui_log_handler'):
            self.gui_log_handler.setMaxBufferSize(size)
            
            # Remove excess entries if new size is smaller
            while self.line_count > size:
                self.removeOldestEntry()
                
        self.saveSettings()

    def clearLog(self):
        """Clear all log messages from the display."""
        self.log_display.clear()
        self.line_count = 0
        self.updateEntryCount()
        if hasattr(self, 'gui_log_handler'):
            self.gui_log_handler.clearBuffer()

    def copySelectedLogs(self):
        """Copy selected log entries to clipboard."""
        self.log_display.copy()

    def saveLogsToFile(self):
        """Save current logs to a file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Logs",
            str(Path.home() / "logs.txt"),
            "Text Files (*.txt);;All Files (*.*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.log_display.toPlainText())
            except Exception as e:
                logging.error(f"Failed to save logs: {e}")
