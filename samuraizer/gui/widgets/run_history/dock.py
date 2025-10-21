"""Dock widget exposing the run history table and related controls."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from PyQt6.QtCore import QItemSelectionModel, QModelIndex, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QAction,
    QApplication,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .models import RunHistoryEntry
from .table_model import RunHistoryProxyModel, RunHistoryTableModel
from .dialogs import ComparisonDialog


class RunHistoryDock(QDockWidget):
    """Dock widget that exposes the run history with filtering and export options."""

    requestComparison = pyqtSignal(str)
    requestOpen = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__("Run History", parent)
        self.setObjectName("runHistoryDock")
        self.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea
            | Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.BottomDockWidgetArea
        )

        self._table_model = RunHistoryTableModel(self)
        self._proxy_model = RunHistoryProxyModel(self)
        self._proxy_model.setSourceModel(self._table_model)

        self._repositories: set[str] = set()
        self._presets: set[str] = set()

        self._create_ui()
        self._connect_signals()
        self._refresh_filter_buttons()

    # ------------------------------------------------------------------
    # API for manager/controller
    # ------------------------------------------------------------------
    def add_entry(self, entry: RunHistoryEntry) -> None:
        """Add a run entry to the table and update filters."""

        self._table_model.add_entry(entry)
        self._repositories.add(entry.repository)
        if entry.preset:
            self._presets.add(entry.preset)
        self._refresh_filter_buttons()
        self._proxy_model.sort(1, Qt.SortOrder.DescendingOrder)
        self._update_action_states()

    def clear(self) -> None:
        self._table_model.clear()
        self._repositories.clear()
        self._presets.clear()
        self._refresh_filter_buttons()
        self._update_action_states()

    def show_comparison(self, reference: RunHistoryEntry, target: RunHistoryEntry) -> None:
        """Show the comparison dialog between two entries."""

        dialog = ComparisonDialog(reference, target, self)
        dialog.exec()

    def notify_comparison_unavailable(self, message: str) -> None:
        QMessageBox.information(self, "Run History", message)

    # ------------------------------------------------------------------
    # Internal UI setup
    # ------------------------------------------------------------------
    def _create_ui(self) -> None:
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(6)

        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(4)

        search_label = QLabel("Search:")
        toolbar_layout.addWidget(search_label)

        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Filter by repository, preset or format")
        toolbar_layout.addWidget(self.search_field, 1)

        self.repository_button = QToolButton()
        self.repository_button.setText("Repositories")
        self.repository_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        toolbar_layout.addWidget(self.repository_button)

        self.preset_button = QToolButton()
        self.preset_button.setText("Presets")
        self.preset_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        toolbar_layout.addWidget(self.preset_button)

        clear_button = QPushButton("Clear")
        clear_button.setToolTip("Clear filters and selection")
        clear_button.clicked.connect(self._on_clear_filters)
        toolbar_layout.addWidget(clear_button)

        main_layout.addLayout(toolbar_layout)

        self.table = QTableView()
        self.table.setModel(self._proxy_model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.doubleClicked.connect(self._on_entry_activated)
        self.table.setSortingEnabled(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        main_layout.addWidget(self.table, 1)

        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(6)

        self.open_button = QPushButton("Open in Viewer")
        self.open_button.clicked.connect(self._on_open_requested)
        action_layout.addWidget(self.open_button)

        self.compare_button = QPushButton("Compare with Current")
        self.compare_button.clicked.connect(self._on_compare_requested)
        action_layout.addWidget(self.compare_button)

        self.export_button = QPushButton("Export Results…")
        self.export_button.clicked.connect(self._on_export_requested)
        action_layout.addWidget(self.export_button)

        self.share_button = QPushButton("Copy Summary")
        self.share_button.setToolTip("Copy the selected run summary to the clipboard")
        self.share_button.clicked.connect(self._on_copy_summary)
        action_layout.addWidget(self.share_button)

        # Actions are enabled dynamically based on the current selection
        self.open_button.setEnabled(False)
        self.compare_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.share_button.setEnabled(False)

        main_layout.addLayout(action_layout)

        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        self.setWidget(container)
        self._update_action_states()

    def _connect_signals(self) -> None:
        self.search_field.textChanged.connect(self._proxy_model.set_search_text)
        selection_model = self.table.selectionModel()
        if selection_model is not None:
            selection_model.selectionChanged.connect(lambda *_: self._update_action_states())

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------
    def _selected_entry_ids(self) -> list[str]:
        selection_model = self.table.selectionModel()
        if selection_model is None:
            return []

        ids: list[str] = []
        for proxy_index in selection_model.selectedRows():
            source_index = self._proxy_model.mapToSource(proxy_index)
            if not source_index.isValid():
                continue
            entry = self._table_model.entry_at(source_index.row())
            if entry is not None:
                ids.append(entry.identifier)
        return ids

    def _selected_entry(self) -> Optional[RunHistoryEntry]:
        ids = self._selected_entry_ids()
        if not ids:
            return None
        return self._table_model.entry_by_id(ids[0])

    def _update_action_states(self) -> None:
        selection_model = self.table.selectionModel()
        if selection_model is None:
            return

        selected_rows = selection_model.selectedRows()
        has_selection = bool(selected_rows)
        single_selection = len(selected_rows) == 1

        self.open_button.setEnabled(has_selection)
        self.export_button.setEnabled(single_selection)
        self.share_button.setEnabled(single_selection)
        self.compare_button.setEnabled(single_selection)

    def set_active_entry(self, entry_id: Optional[str]) -> None:
        selection_model = self.table.selectionModel()
        if selection_model is None:
            return

        selection_model.clearSelection()
        if not entry_id:
            self._update_action_states()
            return

        source_index = self._table_model.index_for_id(entry_id)
        if not source_index.isValid():
            self._update_action_states()
            return

        proxy_index = self._proxy_model.mapFromSource(source_index)
        if not proxy_index.isValid():
            self._update_action_states()
            return

        selection_flags = (
            QItemSelectionModel.SelectionFlag.ClearAndSelect
            | QItemSelectionModel.SelectionFlag.Rows
        )
        selection_model.select(proxy_index, selection_flags)
        self.table.scrollTo(proxy_index, QAbstractItemView.ScrollHint.PositionAtCenter)
        self._update_action_states()

    def _show_context_menu(self, position) -> None:
        menu = QMenu(self)

        open_action = QAction("Open in Viewer", self)
        open_action.triggered.connect(self._on_open_requested)
        menu.addAction(open_action)

        compare_action = QAction("Compare with Current", self)
        compare_action.triggered.connect(self._on_compare_requested)
        menu.addAction(compare_action)

        export_action = QAction("Export Results…", self)
        export_action.triggered.connect(self._on_export_requested)
        menu.addAction(export_action)

        copy_action = QAction("Copy Summary", self)
        copy_action.triggered.connect(self._on_copy_summary)
        menu.addAction(copy_action)

        menu.exec(self.table.viewport().mapToGlobal(position))

    def _refresh_filter_buttons(self) -> None:
        self._populate_button_menu(self.repository_button, sorted(self._repositories))
        self._populate_button_menu(self.preset_button, sorted(self._presets))

    def _populate_button_menu(self, button: QToolButton, values: Iterable[str]) -> None:
        menu = QMenu(button)
        any_action = QAction("Any", menu)
        any_action.triggered.connect(lambda: self._apply_filter(button, ""))
        menu.addAction(any_action)

        for value in values:
            action = QAction(value or "default", menu)
            action.triggered.connect(lambda checked=False, v=value: self._apply_filter(button, v))
            menu.addAction(action)

        button.setMenu(menu)

    def _apply_filter(self, button: QToolButton, value: str) -> None:
        if button is self.repository_button:
            self._proxy_model.set_repository_filter(value)
            label = value or "Any"
            button.setText(f"Repositories: {label}")
        elif button is self.preset_button:
            self._proxy_model.set_preset_filter(value)
            label = value or "Any"
            button.setText(f"Presets: {label}")

    def _on_clear_filters(self) -> None:
        self.search_field.clear()
        self._proxy_model.set_repository_filter("")
        self._proxy_model.set_preset_filter("")
        self.repository_button.setText("Repositories")
        self.preset_button.setText("Presets")
        self.table.clearSelection()

    def _on_entry_activated(self, index: QModelIndex) -> None:
        source_index = self._proxy_model.mapToSource(index)
        entry = self._table_model.data(source_index, Qt.ItemDataRole.UserRole)
        if isinstance(entry, RunHistoryEntry):
            self.requestComparison.emit(entry.identifier)

    def _on_open_requested(self) -> None:
        for entry_id in self._selected_entry_ids():
            self.requestOpen.emit(entry_id)

    def _on_compare_requested(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            QMessageBox.information(self, "Run History", "Please select a run to compare.")
            return
        self.requestComparison.emit(entry.identifier)

    def _on_export_requested(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            QMessageBox.information(self, "Run History", "Select a run to export.")
            return

        default_name = f"{entry.display_name.replace(' ', '_')}.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Run Results",
            str(Path.home() / default_name),
            "JSON Files (*.json);;All Files (*)",
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as handle:
                handle.write(entry.export_as_json())
        except Exception as exc:  # pragma: no cover - file system interaction
            QMessageBox.critical(self, "Export Failed", f"Could not export results:\n{exc}")
            return

        QMessageBox.information(self, "Export Complete", f"Results exported to {file_path}")

    def _on_copy_summary(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            QMessageBox.information(self, "Run History", "Select a run to copy the summary.")
            return

        summary_text = entry.summary_text()
        try:
            QApplication.clipboard().setText(summary_text)
            QMessageBox.information(self, "Run History", "Run summary copied to clipboard.")
        except Exception as exc:  # pragma: no cover - defensive
            QMessageBox.warning(self, "Clipboard Error", f"Could not copy summary:\n{exc}")
