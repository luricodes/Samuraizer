# windows/base/window.py
from typing import Optional
import logging
import sys
from PyQt6.QtWidgets import QMainWindow, QStatusBar
from PyQt6.QtCore import QSettings, QSize, QPoint, Qt

logger = logging.getLogger(__name__)

class BaseWindow(QMainWindow):
    """Base window class with common functionality for all application windows."""
    
    def __init__(self, 
                 title: str = "", 
                 min_size: QSize = QSize(800, 600),
                 settings_prefix: str = "") -> None:
        """Initialize the base window.
        
        Args:
            title: Window title
            min_size: Minimum window size
            settings_prefix: Prefix for settings keys
        """
        super().__init__()
        
        self.settings = QSettings()
        self.settings_prefix = settings_prefix or self.__class__.__name__.lower()
        self.status_bar: Optional[QStatusBar] = None
        
        # Set window properties
        self.setWindowTitle(title)
        self.setMinimumSize(min_size)
        
        # Set up transparency effect while keeping native window frame
        if sys.platform == "win32":
            # Windows-specific transparency handling
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        else:
            # macOS and Linux transparency handling
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        
        # Initialize state
        self._initialized = False
        
    def load_settings(self) -> None:
        """Load window settings."""
        try:
            # Load geometry
            geometry = self.settings.value(f"{self.settings_prefix}/geometry")
            if geometry:
                self.restoreGeometry(geometry)
            else:
                # Fallback to basic position/size
                pos = self.settings.value(f"{self.settings_prefix}/pos")
                size = self.settings.value(f"{self.settings_prefix}/size")
                if isinstance(pos, QPoint):
                    self.move(pos)
                if isinstance(size, QSize):
                    self.resize(size)
                    
            # Load window state if supported
            state = self.settings.value(f"{self.settings_prefix}/state")
            if state and hasattr(self, 'restoreState'):
                self.restoreState(state)
                
            logger.debug(f"Settings loaded for {self.__class__.__name__}")
            
        except Exception as e:
            logger.error(f"Error loading window settings: {e}", exc_info=True)
            
    def save_settings(self) -> None:
        """Save window settings."""
        try:
            # Save geometry and state
            self.settings.setValue(
                f"{self.settings_prefix}/geometry",
                self.saveGeometry()
            )
            if hasattr(self, 'saveState'):
                self.settings.setValue(
                    f"{self.settings_prefix}/state",
                    self.saveState()
                )
                
            # Save position and size as backup
            self.settings.setValue(f"{self.settings_prefix}/pos", self.pos())
            self.settings.setValue(f"{self.settings_prefix}/size", self.size())
            
            logger.debug(f"Settings saved for {self.__class__.__name__}")
            
        except Exception as e:
            logger.error(f"Error saving window settings: {e}", exc_info=True)
            
    def closeEvent(self, event) -> None:
        """Handle window close event."""
        try:
            if self._initialized:
                self.save_settings()
            super().closeEvent(event)
        except Exception as e:
            logger.error(f"Error in close event: {e}", exc_info=True)
            event.accept()
