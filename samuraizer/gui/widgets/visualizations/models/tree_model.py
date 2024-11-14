# samuraizer_gui/ui/widgets/results_display/models.py

import logging
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import (
    Qt, QAbstractItemModel, QModelIndex
)
from PyQt6.QtGui import QColor

logger = logging.getLogger(__name__)

class ResultsTreeModel(QAbstractItemModel):
    """Tree model for displaying hierarchical analysis results"""

    def __init__(self, data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.root_item = self._processData("Root", data)

    class TreeItem:
        def __init__(self, name: str, data: Any, parent=None):
            self.name = name
            self.data = data
            self.parent_item = parent
            self.child_items: List['ResultsTreeModel.TreeItem'] = []

        def appendChild(self, item: 'ResultsTreeModel.TreeItem'):
            self.child_items.append(item)

        def child(self, row: int) -> Optional['ResultsTreeModel.TreeItem']:
            if 0 <= row < len(self.child_items):
                return self.child_items[row]
            return None

        def childCount(self) -> int:
            return len(self.child_items)

        def row(self) -> int:
            if self.parent_item:
                return self.parent_item.child_items.index(self)
            return 0

        def columnCount(self) -> int:
            return 2  # Name and Value columns

    def _processData(self, name: str, data: Any, parent: Optional['TreeItem'] = None) -> 'TreeItem':
        """Process data recursively to build the tree structure"""
        item = self.TreeItem(name, data, parent)
        
        if isinstance(data, dict):
            for key, value in data.items():
                child = self._processData(key, value, item)
                item.appendChild(child)
        elif isinstance(data, list):
            for i, value in enumerate(data):
                child = self._processData(f"[{i}]", value, item)
                item.appendChild(child)
                
        return item

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            parent_item = self.root_item
        else:
            parent_item = parent.internalPointer()

        child_item = parent_item.child(row)
        if child_item:
            return self.createIndex(row, column, child_item)
        return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()

        child_item = index.internalPointer()
        parent_item = child_item.parent_item

        if parent_item == self.root_item:
            return QModelIndex()

        return self.createIndex(parent_item.row(), 0, parent_item)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parent_item = self.root_item
        else:
            parent_item = parent.internalPointer()

        return parent_item.childCount()

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 2  # Name and Value columns

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        item = index.internalPointer()

        if role == Qt.ItemDataRole.DisplayRole:
            if index.column() == 0:
                return item.name
            elif index.column() == 1:
                if isinstance(item.data, (dict, list)):
                    return f"({type(item.data).__name__})"
                return str(item.data)

        elif role == Qt.ItemDataRole.ForegroundRole:
            if isinstance(item.data, dict) and "type" in item.data:
                if item.data["type"] == "error":
                    return QColor(Qt.GlobalColor.red)
                elif item.data["type"] == "excluded":
                    return QColor(Qt.GlobalColor.gray)

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return ["Name", "Value"][section]
        return None
