# samuraizer/gui/app/icons_manager.py

import logging
from pathlib import Path
from typing import Optional, Dict, Tuple
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtCore import QSize

logger = logging.getLogger(__name__)

class IconsManager:
    """Manages application icons and provides centralized access to them."""
    
    _instance = None
    _icons_cache: Dict[str, QIcon] = {}
    
    # Define standard sizes
    SIZES = {
        'small': QSize(16, 16),    # Small toolbar icons, status icons
        'medium': QSize(24, 24),   # Standard toolbar icons
        'large': QSize(32, 32),    # Larger buttons
        'xlarge': QSize(48, 48),   # Dialog icons
    }
    
    # Define icon specifications
    ICON_SPECS = {
        # Toolbar icons - medium (24x24)
        'open': ('folder-open.png', 'medium'),
        'settings': ('settings.png', 'medium'),
        'about': ('info.png', 'medium'),
        'theme_light': ('sun.png', 'medium'),
        'theme_dark': ('moon.png', 'medium'),
        'export': ('download.png', 'medium'),
        'analyze': ('play.png', 'medium'),
        'stop': ('stop.png', 'medium'),
        'save': ('save.png', 'medium'),
        'copy': ('copy.png', 'medium'),
        'delete': ('trash.png', 'medium'),
        
        # Status icons - small (16x16)
        'warning': ('alert-triangle.png', 'small'),
        'error': ('alert-circle.png', 'small'),
        'success': ('check-circle.png', 'small'),
        
        # Social/External links - medium (24x24)
        'github': ('github.png', 'medium'),
        'docs': ('book.png', 'medium'),
    }
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._icons_dir = Path(__file__).parent.parent.parent / 'resources' / 'icons'
            self._app_icon_path = self._icons_dir / 'samuraizer.ico'
            self._load_icons()
    
    def _load_icons(self) -> None:
        """Load all icons into cache."""
        try:
            # Load application icon
            if self._app_icon_path.exists():
                self._icons_cache['app'] = QIcon(str(self._app_icon_path))
                # Also load PNG version for non-Windows platforms
                png_path = self._icons_dir / 'samuraizer.png'
                if png_path.exists():
                    app_icon = self._icons_cache['app']
                    app_icon.addFile(str(png_path), QSize(256, 256))
            
            # Load all other icons
            for icon_name, (file_name, size_key) in self.ICON_SPECS.items():
                icon_path = self._icons_dir / file_name
                if icon_path.exists():
                    icon = QIcon(str(icon_path))
                    # Set the appropriate size
                    size = self.SIZES[size_key]
                    pixmap = QPixmap(str(icon_path)).scaled(
                        size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    icon = QIcon(pixmap)
                    self._icons_cache[icon_name] = icon
                else:
                    logger.warning(f"Icon not found: {icon_path}")
            
        except Exception as e:
            logger.error(f"Error loading icons: {e}", exc_info=True)
    
    @classmethod
    def get_icon(cls, name: str, size_key: str = None) -> Optional[QIcon]:
        """
        Get an icon by name, optionally specifying a size.
        
        Args:
            name: Icon identifier
            size_key: Optional size key ('small', 'medium', 'large', 'xlarge')
        
        Returns:
            QIcon or None if not found
        """
        instance = cls()
        icon = instance._icons_cache.get(name)
        if icon and size_key:
            size = cls.SIZES.get(size_key)
            if size:
                pixmap = icon.pixmap(size)
                return QIcon(pixmap)
        return icon
    
    @classmethod
    def get_app_icon(cls) -> Optional[QIcon]:
        """Get the main application icon."""
        return cls.get_icon('app')
    
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
            else:
                logger.warning("Application icon not found")
        except Exception as e:
            logger.error(f"Error initializing application icons: {e}", exc_info=True)