"""Model classes backing the run history table view."""
from __future__ import annotations

from typing import Dict, List, Optional

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt, QVariant
from PyQt6.QtCore import QSortFilterProxyModel

from .models import RunHistoryEntry


class RunHistoryTableModel(QAbstractTableModel):
    """Table model storing run history entries."""

    _HEADERS = [
        "Run",
        "Timestamp",
        "Repository",
        "Preset",
        "Format",
        "Duration",
        "Files",
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._entries: List[RunHistoryEntry] = []
        self._row_lookup: Dict[str, int] = {}

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802 - Qt API
        if parent.isValid():
            return 0
        return len(self._entries)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802 - Qt API
        if parent.isValid():
            return 0
        return len(self._HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):  # noqa: N802 - Qt API
        if role != Qt.ItemDataRole.DisplayRole:
            return QVariant()
        if orientation == Qt.Orientation.Horizontal:
            try:
                return self._HEADERS[section]
            except IndexError:
                return QVariant()
        return section + 1

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # noqa: N802 - Qt API
        if not index.isValid() or not (0 <= index.row() < len(self._entries)):
            return QVariant()

        entry = self._entries[index.row()]
        column = index.column()

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            if column == 0:
                return entry.display_name
            if column == 1:
                return entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            if column == 2:
                return entry.repository
            if column == 3:
                return entry.preset or "default"
            if column == 4:
                return entry.output_format
            if column == 5:
                return "-" if entry.duration_seconds is None else f"{entry.duration_seconds:.2f}s"
            if column == 6:
                return "-" if entry.processed_files is None else str(entry.processed_files)

        if role == Qt.ItemDataRole.UserRole:
            return entry

        return QVariant()

    def add_entry(self, entry: RunHistoryEntry) -> None:
        existing_row = self._row_lookup.get(entry.identifier)
        if existing_row is not None:
            self._entries[existing_row] = entry
            self._row_lookup[entry.identifier] = existing_row
            top_left = self.index(existing_row, 0)
            bottom_right = self.index(existing_row, self.columnCount() - 1)
            self.dataChanged.emit(top_left, bottom_right)
            return

        row = len(self._entries)
        self.beginInsertRows(QModelIndex(), row, row)
        self._entries.append(entry)
        self._row_lookup[entry.identifier] = row
        self.endInsertRows()

    def clear(self) -> None:
        if not self._entries:
            return
        self.beginRemoveRows(QModelIndex(), 0, len(self._entries) - 1)
        self._entries.clear()
        self._row_lookup.clear()
        self.endRemoveRows()

    def entry_at(self, row: int) -> Optional[RunHistoryEntry]:
        if 0 <= row < len(self._entries):
            return self._entries[row]
        return None

    def entries(self) -> List[RunHistoryEntry]:
        return list(self._entries)

    def entry_by_id(self, entry_id: str) -> Optional[RunHistoryEntry]:
        row = self._row_lookup.get(entry_id)
        if row is None:
            return None
        return self._entries[row]

    def index_for_id(self, entry_id: str) -> QModelIndex:
        row = self._row_lookup.get(entry_id)
        if row is None:
            return QModelIndex()
        return self.index(row, 0)


class RunHistoryProxyModel(QSortFilterProxyModel):
    """Proxy model adding filtering behaviour for the run history."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._search_text = ""
        self._repository_filter = ""
        self._preset_filter = ""
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setDynamicSortFilter(True)

    def set_search_text(self, text: str) -> None:
        self._search_text = text.strip()
        self.invalidateFilter()

    def set_repository_filter(self, repository: str) -> None:
        self._repository_filter = repository.strip()
        self.invalidateFilter()

    def set_preset_filter(self, preset: str) -> None:
        self._preset_filter = preset.strip()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # noqa: N802 - Qt API
        model = self.sourceModel()
        if model is None:
            return True

        index = model.index(source_row, 0, source_parent)
        entry = model.data(index, Qt.ItemDataRole.UserRole)
        if not isinstance(entry, RunHistoryEntry):
            return True

        if self._search_text:
            haystack = " ".join(
                [
                    entry.display_name,
                    entry.repository,
                    entry.preset or "default",
                    entry.output_format,
                ]
            ).lower()
            if self._search_text.lower() not in haystack:
                return False

        if self._repository_filter and self._repository_filter.lower() not in (entry.repository or "").lower():
            return False

        if self._preset_filter and self._preset_filter.lower() not in (entry.preset or "").lower():
            return False

        return True
