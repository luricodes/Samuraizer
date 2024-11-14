# samuraizer_gui/ui/widgets/results_display/json_tree_view.py

import logging
from typing import Dict, Any

from PyQt6.QtWidgets import QTreeView, QApplication
from PyQt6.QtCore import Qt

from ..models import ResultsTreeModel

logger = logging.getLogger(__name__)

class JsonTreeView(QTreeView):
    """Tree view for displaying JSON-like data structures"""
    
    def __init__(self, data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.results_data = data
        self.initUI()

    def initUI(self):
        """Initialize the user interface"""
        # Set up the model
        self.model = ResultsTreeModel(self.results_data)
        self.setModel(self.model)
        
        # Configure view
        self.setAlternatingRowColors(True)
        self.setUniformRowHeights(True)
        self.setExpandsOnDoubleClick(True)
        self.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        
        # Set column widths
        self.setColumnWidth(0, 300)  # Name column
        self.setColumnWidth(1, 400)  # Value column
        
        # Expand first level
        self.expandToDepth(0)

    def copySelected(self):
        """Copy selected items to clipboard"""
        indexes = self.selectedIndexes()
        if not indexes:
            return

        text = []
        last_row = indexes[0].row()
        for idx in indexes:
            if idx.row() != last_row:
                text.append('\n')
            text.append(self.model.data(idx, Qt.ItemDataRole.DisplayRole))
            text.append('\t')
            last_row = idx.row()

        QApplication.clipboard().setText(''.join(text))
