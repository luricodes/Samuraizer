from typing import Optional, Dict, List
from datetime import datetime
from pathlib import Path
import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QToolBar,
    QPushButton, QComboBox, QLineEdit, QFileDialog, QLabel,
    QSpinBox, QMenu, QToolTip, QSizePolicy, QTreeWidget,
    QTreeWidgetItem, QHeaderView, QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSlot, QSettings, QSize, QPoint, QEvent
from PyQt6.QtGui import QColor, QBrush, QGuiApplication, QPalette

from .....utils.log_handler import GuiLogHandler


class LogPanel(QWidget):
    """Modernised log viewer with filtering, search and export features."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.settings = QSettings()
        self.log_levels: Dict[str, Optional[int]] = {
            "All": None,
            "Debug": logging.DEBUG,
            "Info": logging.INFO,
            "Warning": logging.WARNING,
            "Error": logging.ERROR,
            "Critical": logging.CRITICAL,
        }
        self.current_filter: Optional[int] = logging.INFO
        self.search_text = ""
        self.auto_scroll = True
        self.line_count = 0
        self.gui_log_handler: Optional[GuiLogHandler] = None

        self._search_results: List[QTreeWidgetItem] = []
        self._search_index = -1
        self._search_highlight = QBrush()
        self._window_text_brush = QBrush()
        self._message_text_brush = QBrush()
        self._highlighted_items: List[QTreeWidgetItem] = []

        # Set size policy to allow complete collapse
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)

        self.initUI()
        self._update_theme_colors()
        self.loadSettings()

    def sizeHint(self) -> QSize:
        """Override sizeHint to provide a good default size."""
        return QSize(600, 200)

    def minimumSizeHint(self) -> QSize:
        """Override minimumSizeHint to allow complete collapse."""
        return QSize(0, 0)

    # ------------------------------------------------------------------
    # Settings persistence
    # ------------------------------------------------------------------
    def saveSettings(self) -> None:
        """Persist the current panel state."""
        settings = QSettings()
        settings.setValue("log_panel/level", self.level_filter.currentText())
        settings.setValue("log_panel/auto_scroll", self.auto_scroll)
        settings.setValue("log_panel/buffer_size", self.buffer_size.value())

    def loadSettings(self) -> None:
        """Restore the panel state."""
        settings = QSettings()

        level = settings.value("log_panel/level", "Info")
        index = self.level_filter.findText(level)
        if index >= 0:
            self.level_filter.setCurrentIndex(index)
            self.setLogLevel(level)

        auto_scroll = settings.value("log_panel/auto_scroll", True, type=bool)
        self.auto_scroll_btn.setChecked(auto_scroll)
        self.auto_scroll = auto_scroll

        buffer_size = settings.value("log_panel/buffer_size", 1000, type=int)
        self.buffer_size.setValue(buffer_size)

    def changeEvent(self, event: QEvent) -> None:  # noqa: D401 - Qt override
        """React to palette changes so the panel follows the active theme."""
        if event.type() == QEvent.Type.PaletteChange:
            self._update_theme_colors()
            self._apply_theme_to_existing_items()
            if self.search_text:
                self._refreshSearchResults()
        super().changeEvent(event)

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------
    def initUI(self) -> None:
        """Initialise the panel layout and widgets."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QToolBar()
        toolbar.setFixedHeight(34)
        layout.addWidget(toolbar)

        self.level_filter = QComboBox()
        self.level_filter.addItems(self.log_levels.keys())
        self.level_filter.currentTextChanged.connect(self.setLogLevel)
        toolbar.addWidget(QLabel("Level:"))
        toolbar.addWidget(self.level_filter)
        toolbar.addSeparator()

        self.auto_scroll_btn = QPushButton("Auto-scroll")
        self.auto_scroll_btn.setCheckable(True)
        self.auto_scroll_btn.setChecked(True)
        self.auto_scroll_btn.toggled.connect(self.toggleAutoScroll)
        toolbar.addWidget(self.auto_scroll_btn)
        toolbar.addSeparator()

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

        self.entry_counter = QLabel("Entries: 0/1000")
        self.entry_counter.setToolTip(
            "Current number of entries / Maximum buffer size\n"
            "Oldest entries are automatically removed when limit is reached"
        )
        buffer_layout.addWidget(self.entry_counter)

        toolbar.addWidget(buffer_container)
        toolbar.addSeparator()

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
        self.prev_button.clicked.connect(self.findPrevious)
        search_layout.addWidget(self.prev_button)

        self.next_button = QPushButton("Next")
        self.next_button.setEnabled(False)
        self.next_button.clicked.connect(self.findNext)
        search_layout.addWidget(self.next_button)

        toolbar.addWidget(search_container)
        toolbar.addSeparator()

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clearLog)
        toolbar.addWidget(clear_btn)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.saveLogsToFile)
        toolbar.addWidget(save_btn)

        self.log_view = QTreeWidget()
        self.log_view.setHeaderLabels(["Time", "Level", "Message"])
        self.log_view.setRootIsDecorated(False)
        self.log_view.setAlternatingRowColors(True)
        self.log_view.setUniformRowHeights(True)
        self.log_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.log_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.log_view.setAllColumnsShowFocus(True)
        self.log_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.log_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.log_view.customContextMenuRequested.connect(self.showContextMenu)
        self.log_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)

        header = self.log_view.header()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.log_view)

    def _update_theme_colors(self) -> None:
        palette = self.log_view.palette()
        self._window_text_brush = palette.brush(QPalette.ColorRole.WindowText)
        self._message_text_brush = palette.brush(QPalette.ColorRole.Text)

        highlight_color = palette.color(QPalette.ColorRole.Highlight)
        if highlight_color.alpha() == 255:
            highlight_color.setAlpha(90)
        self._search_highlight = QBrush(highlight_color)

    def _ensure_theme_colors(self) -> None:
        if (
            self._message_text_brush.style() == Qt.BrushStyle.NoBrush
            or self._window_text_brush.style() == Qt.BrushStyle.NoBrush
        ):
            self._update_theme_colors()

    def _apply_theme_to_existing_items(self) -> None:
        self._ensure_theme_colors()
        for item in self._iter_items():
            entry: Dict = item.data(0, Qt.ItemDataRole.UserRole) or {}
            level_color = QColor(entry.get('color', "#4CAF50"))
            item.setForeground(0, self._window_text_brush)
            item.setForeground(1, QBrush(level_color))
            item.setForeground(2, self._message_text_brush)
            for column in range(3):
                item.setBackground(column, QBrush())
            item.setData(2, Qt.ItemDataRole.UserRole + 1, None)
        self._highlighted_items.clear()

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------
    def showContextMenu(self, position: QPoint) -> None:
        """Show context menu for the log table."""
        menu = QMenu(self)

        copy_action = menu.addAction("Copy")
        copy_action.triggered.connect(self.copySelectedLogs)

        select_all_action = menu.addAction("Select All")
        select_all_action.triggered.connect(self.log_view.selectAll)

        menu.addSeparator()

        save_action = menu.addAction("Save Logs…")
        save_action.triggered.connect(self.saveLogsToFile)

        clear_action = menu.addAction("Clear")
        clear_action.triggered.connect(self.clearLog)

        menu.exec(self.log_view.mapToGlobal(position))

    # ------------------------------------------------------------------
    # Logging integration
    # ------------------------------------------------------------------
    def setLogHandler(self, handler: GuiLogHandler) -> None:
        """Set the GUI log handler and connect signals."""
        self.gui_log_handler = handler
        handler.log_record_received.connect(self.addLogMessage)
        handler.batch_records_received.connect(self.addBatchMessages)

        self.clearLog(clear_buffer=False)
        self._rebuildFromHandler()

    def _rebuildFromHandler(self) -> None:
        if not self.gui_log_handler:
            return

        buffer = self.gui_log_handler.getBuffer()
        if not buffer:
            return

        previous_auto_scroll = self.auto_scroll
        self.auto_scroll = False
        self.log_view.setUpdatesEnabled(False)
        self.log_view.clear()
        self.line_count = 0

        try:
            for entry in buffer:
                entry_dict = self._entry_to_dict(entry)
                if self._should_display(entry_dict['level']):
                    self._appendMessage(entry_dict, scroll=False)
                    self.line_count += 1
        finally:
            self.log_view.setUpdatesEnabled(True)
            self.auto_scroll = previous_auto_scroll

        self._apply_theme_to_existing_items()

        if previous_auto_scroll and self.log_view.topLevelItemCount():
            last_item = self.log_view.topLevelItem(self.log_view.topLevelItemCount() - 1)
            self._scroll_to_item(last_item, align_bottom=True)

        self.updateEntryCount()
        self._refreshSearchResults()

    def _entry_to_dict(self, entry) -> Dict:
        formatted = getattr(entry, 'formatted', getattr(entry, 'message', ''))
        return {
            'message': getattr(entry, 'message', formatted),
            'formatted': formatted,
            'level': getattr(entry, 'level', logging.INFO),
            'level_name': getattr(entry, 'level_name', logging.getLevelName(getattr(entry, 'level', logging.INFO))),
            'logger_name': getattr(entry, 'logger_name', ''),
            'color': getattr(entry, 'color', "#4CAF50"),
            'timestamp': getattr(entry, 'timestamp', datetime.now().timestamp()),
        }

    def _should_display(self, level: int) -> bool:
        if self.current_filter is None:
            return True
        return level >= self.current_filter

    def removeOldestEntry(self) -> None:
        """Remove the oldest entry from the table."""
        if self.log_view.topLevelItemCount() == 0:
            return
        self.log_view.takeTopLevelItem(0)
        self.line_count = max(0, self.line_count - 1)

    @pyqtSlot(dict)
    def addLogMessage(self, log_data: Dict) -> None:
        """Add a single log message to the table."""
        if not self._should_display(log_data['level']):
            return

        if self.line_count >= self.buffer_size.value():
            self.removeOldestEntry()

        self._appendMessage(log_data)
        self.line_count += 1
        self.updateEntryCount()

        if self.search_text:
            self._refreshSearchResults()

    @pyqtSlot(list)
    def addBatchMessages(self, messages: List[Dict]) -> None:
        """Add multiple log messages at once."""
        filtered = [msg for msg in messages if self._should_display(msg['level'])]
        if not filtered:
            return

        while self.line_count + len(filtered) > self.buffer_size.value():
            self.removeOldestEntry()

        self.log_view.setUpdatesEnabled(False)
        try:
            for message in filtered:
                self._appendMessage(message)
            self.line_count += len(filtered)
        finally:
            self.log_view.setUpdatesEnabled(True)

        self.updateEntryCount()

        if self.search_text:
            self._refreshSearchResults()

    def updateEntryCount(self) -> None:
        """Update the entry counter display."""
        max_size = self.buffer_size.value()
        self.entry_counter.setText(f"Entries: {self.line_count}/{max_size}")

        if self.line_count >= max_size * 0.9:
            self.entry_counter.setStyleSheet("color: orange;")
            QToolTip.showText(
                self.entry_counter.mapToGlobal(self.entry_counter.rect().topRight()),
                "Buffer is nearly full! Oldest entries will be removed soon.",
                self.entry_counter
            )
        else:
            self.entry_counter.setStyleSheet("")

    def _appendMessage(self, log_data: Dict, *, scroll: bool = True) -> None:
        """Create and append a tree item for a log entry."""
        self._ensure_theme_colors()
        timestamp = datetime.fromtimestamp(log_data['timestamp'])
        time_text = timestamp.strftime("%H:%M:%S")
        level_name = log_data.get('level_name') or logging.getLevelName(log_data['level'])
        message = log_data.get('message') or log_data.get('formatted') or ""

        item = QTreeWidgetItem([time_text, level_name, message])
        item.setData(0, Qt.ItemDataRole.UserRole, log_data)
        item.setToolTip(2, log_data.get('formatted', message))

        level_color = QColor(log_data['color'])
        item.setForeground(0, self._window_text_brush)
        item.setForeground(1, QBrush(level_color))
        item.setForeground(2, self._message_text_brush)
        item.setTextAlignment(0, Qt.AlignmentFlag.AlignCenter)
        item.setTextAlignment(1, Qt.AlignmentFlag.AlignCenter)
        item.setTextAlignment(2, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.log_view.addTopLevelItem(item)

        if scroll and self.auto_scroll:
            self._scroll_to_item(item, align_bottom=True)

    def _scroll_to_item(self, item: QTreeWidgetItem, *, align_bottom: bool) -> None:
        hint = (
            QAbstractItemView.ScrollHint.PositionAtBottom
            if align_bottom
            else QAbstractItemView.ScrollHint.PositionAtCenter
        )
        self.log_view.scrollToItem(item, hint)

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------
    def setLogLevel(self, level_name: str) -> None:
        """Set the log level filter."""
        self.current_filter = self.log_levels.get(level_name, logging.INFO)
        self.saveSettings()
        self._rebuildFromHandler()

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def searchLogs(self, text: str) -> None:
        """Search through log messages."""
        self.search_text = text.strip()
        self._refreshSearchResults()

    def _refreshSearchResults(self) -> None:
        self._clearSearchHighlights()

        if not self.search_text:
            self._search_results.clear()
            self._search_index = -1
            self.prev_button.setEnabled(False)
            self.next_button.setEnabled(False)
            return

        term = self.search_text.lower()
        matches: List[QTreeWidgetItem] = []
        for item in self._iter_items():
            entry: Dict = item.data(0, Qt.ItemDataRole.UserRole)
            formatted = entry.get('formatted', item.text(2))
            if term in formatted.lower():
                matches.append(item)
                self._highlight_item(item)

        self._search_results = matches
        self._search_index = 0 if matches else -1
        self.prev_button.setEnabled(bool(matches))
        self.next_button.setEnabled(len(matches) > 1)

        if matches:
            self._focusSearchResult(self._search_index)

    def _iter_items(self):
        for index in range(self.log_view.topLevelItemCount()):
            yield self.log_view.topLevelItem(index)

    def _highlight_item(self, item: QTreeWidgetItem) -> None:
        original_brush = item.background(2)
        item.setData(2, Qt.ItemDataRole.UserRole + 1, original_brush)
        item.setBackground(2, self._search_highlight)
        self._highlighted_items.append(item)

    def _clearSearchHighlights(self) -> None:
        for item in self._highlighted_items:
            original = item.data(2, Qt.ItemDataRole.UserRole + 1)
            if isinstance(original, QBrush):
                item.setBackground(2, original)
            else:
                item.setBackground(2, QBrush())
            item.setData(2, Qt.ItemDataRole.UserRole + 1, None)
        self._highlighted_items.clear()

    def _focusSearchResult(self, index: int) -> None:
        if not self._search_results or index < 0 or index >= len(self._search_results):
            return
        item = self._search_results[index]
        self.log_view.setCurrentItem(item)
        self._scroll_to_item(item, align_bottom=False)

    def findNext(self) -> None:
        """Find next occurrence of search text."""
        if not self._search_results:
            return

        if self._search_index < 0:
            self._search_index = 0
        else:
            self._search_index = (self._search_index + 1) % len(self._search_results)

        self._focusSearchResult(self._search_index)

    def findPrevious(self) -> None:
        """Find previous occurrence of search text."""
        if not self._search_results:
            return

        if self._search_index < 0:
            self._search_index = len(self._search_results) - 1
        else:
            self._search_index = (self._search_index - 1) % len(self._search_results)

        self._focusSearchResult(self._search_index)

    # ------------------------------------------------------------------
    # Behaviour controls
    # ------------------------------------------------------------------
    def toggleAutoScroll(self, enabled: bool) -> None:
        """Toggle auto-scrolling of log messages."""
        self.auto_scroll = enabled
        self.saveSettings()

    def setBufferSize(self, size: int) -> None:
        """Set the maximum number of log messages to keep."""
        if self.gui_log_handler:
            self.gui_log_handler.setMaxBufferSize(size)
            while self.line_count > size:
                self.removeOldestEntry()
            self.updateEntryCount()
            if self.search_text:
                self._refreshSearchResults()
        self.saveSettings()

    def clearLog(self, *, clear_buffer: bool = True) -> None:
        """Clear all log messages from the table."""
        self.log_view.clear()
        self.line_count = 0
        self.updateEntryCount()
        self._clearSearchHighlights()
        self._search_results.clear()
        self._search_index = -1
        self.prev_button.setEnabled(False)
        self.next_button.setEnabled(False)

        if clear_buffer and self.gui_log_handler:
            self.gui_log_handler.clearBuffer()

    # ------------------------------------------------------------------
    # Export helpers
    # ------------------------------------------------------------------
    def copySelectedLogs(self) -> None:
        """Copy selected log entries to clipboard."""
        selected = self.log_view.selectedItems()
        if not selected:
            return

        lines: List[str] = []
        for item in selected:
            entry: Dict = item.data(0, Qt.ItemDataRole.UserRole)
            lines.append(entry.get('formatted', item.text(2)))

        clipboard = QGuiApplication.clipboard()
        clipboard.setText("\n".join(lines))

    def saveLogsToFile(self) -> None:
        """Save current logs to a file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Logs",
            str(Path.home() / "logs.txt"),
            "Text Files (*.txt);;All Files (*.*)"
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as file:
                    for item in self._iter_items():
                        entry: Dict = item.data(0, Qt.ItemDataRole.UserRole)
                        file.write(entry.get('formatted', item.text(2)))
                        file.write('\n')
            except Exception as exc:
                logging.error("Failed to save logs: %s", exc)
