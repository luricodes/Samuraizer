# samuraizer/gui/app/icons_manager.py

import logging
import sys
from pathlib import Path
from typing import Optional, Dict
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtCore import QSize

logger = logging.getLogger(__name__)

class IconsManager:
    """Manages application icons and provides centralized access to them."""
    
    _instance = None
    _icons_cache: Dict[str, QIcon] = {}
    
    # Standard sizes for different platforms
    ICON_SIZES = [16, 32, 48, 64, 128, 256]
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._icons_dir = Path(__file__).parent.parent.parent / 'resources' / 'icons'
            self._load_icons()
    
    def _load_icons(self) -> None:
        """Load application icon into cache with platform-specific handling."""
        try:
            app_icon = QIcon()
            
            # Load Windows ICO file
            ico_path = self._icons_dir / 'samuraizer_icon_256x256.ico'
            if ico_path.exists():
                if sys.platform == 'win32':
                    # On Windows, use ICO file directly
                    app_icon = QIcon(str(ico_path))
                    logger.info(f"Successfully loaded Windows ICO icon from {ico_path}")
                else:
                    # On non-Windows platforms, extract sizes from ICO
                    pixmap = QPixmap(str(ico_path))
                    for size in self.ICON_SIZES:
                        scaled_pixmap = pixmap.scaled(
                            size, size,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        app_icon.addPixmap(scaled_pixmap)
                    logger.info(f"Successfully loaded and scaled ICO icon for non-Windows platform")
            else:
                logger.warning(f"Application icon not found at {ico_path}")
            
            # Store the icon in cache
            if not app_icon.isNull():
                self._icons_cache['app'] = app_icon
            else:
                logger.warning("Failed to load application icon")
            
        except Exception as e:
            logger.error(f"Error loading icons: {e}", exc_info=True)
    
    @classmethod
    def get_app_icon(cls) -> Optional[QIcon]:
        """Get the main application icon."""
        instance = cls()
        return instance._icons_cache.get('app')
    
    @classmethod
    def set_window_icon(cls, window) -> None:
        """Set the application icon for a window."""
        app_icon = cls.get_app_icon()
        if app_icon:
            window.setWindowIcon(app_icon)
    
    @classmethod
    def initialize(cls, app) -> None:
        """Initialize icons for the application."""
        try:
            instance = cls()
            app_icon = instance.get_app_icon()
            if app_icon:
                app.setWindowIcon(app_icon)
                logger.info("Successfully set application icon")
            else:
                logger.warning("Application icon not found")
        except Exception as e:
            logger.error(f"Error initializing application icons: {e}", exc_info=True)
