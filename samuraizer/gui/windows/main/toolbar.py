from typing import TYPE_CHECKING, Optional
import logging
from PyQt6.QtWidgets import (
    QToolBar,
    QLabel,
    QWidget,
    QSizePolicy,
    QVBoxLayout,
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import QStyle

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
        self.setStyleSheet("QToolBar#mainToolBar { border: 0px; margin: 0px; }")
        self.setIconSize(QSize(20, 20))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        
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
            # Title block
            title_container = QWidget(self)
            title_container.setObjectName("toolbarTitleContainer")
            title_layout = QVBoxLayout(title_container)
            title_layout.setContentsMargins(12, 6, 12, 6)
            title_layout.setSpacing(2)

            title_label = QLabel("Samuraizer")
            title_label.setObjectName("toolbarTitle")
            subtitle_label = QLabel("Repository intelligence suite")
            subtitle_label.setObjectName("toolbarSubtitle")

            title_layout.addWidget(title_label)
            title_layout.addWidget(subtitle_label)

            self.addWidget(title_container)

            spacer = QWidget()
            spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self.addWidget(spacer)

            # Open Repository Action
            open_action = QAction(
                self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon),
                "Open Repository",
                self,
            )
            open_action.setStatusTip("Select a repository for analysis")
            open_action.triggered.connect(self.main_window.open_repository)
            open_action.setShortcut("Ctrl+O")
            self.addAction(open_action)

            self.addSeparator()

            # Settings Action
            settings_action = QAction(
                self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView),
                "Settings",
                self,
            )
            settings_action.setStatusTip("Configure application settings")
            settings_action.triggered.connect(self.main_window.show_settings)
            self.addAction(settings_action)

            # Theme toggle action
            self.theme_action = QAction("Switch Theme", self)
            self.theme_action.triggered.connect(lambda: self.main_window.toggle_theme())
            self.addAction(self.theme_action)

            self.addSeparator()

            # About Action
            about_action = QAction(
                self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation),
                "About",
                self,
            )
            about_action.setStatusTip("About Samuraizer")
            about_action.triggered.connect(self.main_window.show_about)
            self.addAction(about_action)

        except Exception as e:
            logger.error(f"Error setting up toolbar actions: {e}", exc_info=True)
            raise

    def update_theme_action(self, theme: str) -> None:
        """Update theme toggle action to reflect the current theme."""
        if not self.theme_action:
            return

        theme_lower = (theme or "").lower()
        if theme_lower == "dark":
            text = "Switch to Light Mode"
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogYesButton)
        else:
            text = "Switch to Dark Mode"
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogNoButton)

        self.theme_action.setText(text)
        self.theme_action.setStatusTip(text)
        self.theme_action.setIcon(icon)
