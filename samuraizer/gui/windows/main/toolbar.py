from typing import TYPE_CHECKING, Optional
import logging
from PyQt6.QtWidgets import QToolBar
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt

if TYPE_CHECKING:
    from samuraizer.gui.windows.main.components.window import MainWindow

logger = logging.getLogger(__name__)

class MainToolBar(QToolBar):
    """Main application toolbar."""
    
    def __init__(self, parent: 'MainWindow') -> None:
        """Initialize the toolbar.
        
        Args:
            parent: Parent MainWindow instance
        """
        super().__init__(parent)
        self.setObjectName("mainToolBar")
        self.main_window = parent
        self.setMovable(False)
        self.theme_action: Optional[QAction] = None
        
        # Remove borders and margins
        self.setStyleSheet("QToolBar { border: 0px; margin: 0px; padding: 4px; }")
        
        # Disable context menu only for the toolbar
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
        
        self.setup_actions()
        
    def hideEvent(self, event):
        """Override hideEvent to prevent hiding."""
        event.ignore()  # Prevent the hide event
        self.setVisible(True)
    
    def setup_actions(self) -> None:
        """Set up toolbar actions."""
        try:
            # Settings Action
            settings_action = QAction("Settings", self)
            settings_action.setStatusTip("Configure application settings")
            settings_action.triggered.connect(self.main_window.show_settings)
            self.addAction(settings_action)
            self.addSeparator()

            # About Action
            about_action = QAction("About", self)
            about_action.setStatusTip("About Samuraizer")
            about_action.triggered.connect(self.main_window.show_about)
            self.addAction(about_action)
            
        except Exception as e:
            logger.error(f"Error setting up toolbar actions: {e}", exc_info=True)
            raise
