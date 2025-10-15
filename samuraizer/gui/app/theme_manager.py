# samuraizer/gui/app/theme_manager.py

import logging
import sys
from typing import Optional

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import QSettings, Qt
import qdarktheme

from samuraizer.config.unified import UnifiedConfigManager

logger = logging.getLogger(__name__)

class ThemeManager:
    """Manages application theming and related settings."""
    
    @staticmethod
    def get_saved_theme() -> str:
        """Get the saved theme from settings."""
        try:
            config = UnifiedConfigManager().get_active_profile_config()
            theme = config.get("theme", {}).get("name")
            if theme:
                return str(theme)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Unable to read theme from configuration: %s", exc)
        settings = QSettings()
        return settings.value("theme", "dark", str)
    
    @staticmethod
    def save_theme(theme: str, *, persist_config: bool = True) -> None:
        """Save the current theme to settings."""
        try:
            if persist_config:
                UnifiedConfigManager().set_value("theme.name", theme)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Unable to persist theme to configuration: %s", exc)
        settings = QSettings()
        settings.setValue("theme", theme)
        settings.sync()
    
    @classmethod
    def apply_theme(cls, app: QApplication, theme: str = "dark", *, persist: bool = True) -> None:
        """Apply the theme to the application.
        
        Args:
            app: QApplication instance
            theme: Theme name ("dark" or "light")
        """
        try:
            # Save the theme preference
            cls.save_theme(theme, persist_config=persist)
            
            # Define colors based on theme
            if theme == "dark":
                bg_color = "32, 33, 36"
                text_color = "255, 255, 255"
                hover_color = "255, 255, 255"
                hover_alpha = "0.1"
                pressed_alpha = "0.15"
                separator_color = "255, 255, 255"
                separator_alpha = "0.1"
            else:
                bg_color = "255, 255, 255"
                text_color = "0, 0, 0"
                hover_color = "0, 0, 0"
                hover_alpha = "0.05"
                pressed_alpha = "0.1"
                separator_color = "0, 0, 0"
                separator_alpha = "0.1"
            
            # Create base stylesheet with transparency
            base_style = f"""
            QMainWindow {{
                background: rgba({bg_color}, 0.92);
            }}
            QWidget#centralWidget {{
                background: rgba({bg_color}, 0.92);
                border: none;
            }}
            QToolBar#mainToolBar {{
                background: rgba({bg_color}, 0.92);
                border: none;
                margin: 0px;
                padding: 4px;
            }}
            QToolBar#mainToolBar::separator {{
                background: rgba({separator_color}, {separator_alpha});
                width: 1px;
                height: 16px;
                margin: 0px 8px;
            }}
            QStatusBar {{
                background: rgba({bg_color}, 0.92);
                border: none;
            }}
            QToolButton {{
                background: transparent;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                color: rgba({text_color}, 0.9);
            }}
            QToolButton:hover {{
                background: rgba({hover_color}, {hover_alpha});
            }}
            QToolButton:pressed {{
                background: rgba({hover_color}, {pressed_alpha});
            }}
            """
            
            # Apply the combined stylesheet
            app.setStyleSheet(base_style + qdarktheme.load_stylesheet(theme=theme))
            
            # Apply QPalette for better system integration
            app.setPalette(qdarktheme.load_palette(theme=theme))
            
            # Force an update of all widgets
            fallback_style = app.style()
            for widget in app.allWidgets():
                style = widget.style() or fallback_style
                if style is None:
                    continue
                style.unpolish(widget)
                style.polish(widget)
                widget.update()
            
            logger.debug(f"{theme.capitalize()} theme applied successfully")
        except Exception as e:
            logger.error(f"Error applying theme: {e}")
    
    @classmethod
    def toggle_theme(cls, app: QApplication, window: QWidget, theme: Optional[str] = None) -> None:
        """Toggle between light and dark themes or apply specific theme.
        
        Args:
            app: QApplication instance
            window: Main window instance that needs theme update notifications
            theme: Optional specific theme to apply ("dark" or "light")
        """
        if theme is None:
            current_theme = cls.get_saved_theme()
            new_theme = "light" if current_theme == "dark" else "dark"
        else:
            new_theme = theme.lower()
            
        cls.apply_theme(app, new_theme)
        
        # Update UI elements that need to reflect the theme change
        if hasattr(window, 'updateThemeActionText'):
            window.updateThemeActionText(new_theme)
    
    @classmethod
    def setup_style(cls, app: QApplication) -> None:
        """Apply the theme and platform-specific styles to the application.
        
        Args:
            app: QApplication instance
        """
        try:
            # Get saved theme preference
            theme = cls.get_saved_theme()
            
            # Apply platform-specific tweaks
            if sys.platform == "darwin":  # macOS
                app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus)
            
            # Apply the theme
            cls.apply_theme(app, theme)
            
            logger.debug(f"Initial {theme} theme applied successfully")
        except Exception as e:
            logger.error(f"Error applying initial theme: {e}")
