import logging
from typing import Dict, Any
from PyQt6.QtWidgets import QTabWidget, QMenu
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction

logger = logging.getLogger(__name__)

class ResultTabs(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tab_counter = 0
        self.active_analyses = set()
        self.initUI()

    def initUI(self):
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self.closeResultTab)

    def closeResultTab(self, index: int):
        try:
            tab_name = self.tabText(index)
            self.active_analyses.discard(tab_name)
            
            widget = self.widget(index)
            self.removeTab(index)
            if widget:
                widget.deleteLater()
                
            logger.debug(f"Closed result tab: {tab_name}")
            
        except Exception as e:
            logger.error(f"Error closing result tab: {e}", exc_info=True)

    def showResultContextMenu(self, pos, view, export_callback):
        try:
            menu = QMenu(self)
            
            export_action = QAction("Export Results...", self)
            export_action.triggered.connect(
                lambda: export_callback(view.results_data)
            )
            menu.addAction(export_action)
            
            copy_action = QAction("Copy Selected", self)
            copy_action.triggered.connect(view.copySelected)
            menu.addAction(copy_action)
            
            menu.exec(view.mapToGlobal(pos))
            
        except Exception as e:
            logger.error(f"Error showing context menu: {e}", exc_info=True)