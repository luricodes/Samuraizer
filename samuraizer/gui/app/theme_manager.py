# samuraizer/gui/app/theme_manager.py

import logging
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QSettings, Qt
import qdarktheme

logger = logging.getLogger(__name__)

class ThemeManager:
    """Manages application theming and related settings."""
    
    @staticmethod
    def get_saved_theme() -> str:
        """Get the saved theme from settings."""
        settings = QSettings()
        return settings.value("theme", "dark", str)
    
    @staticmethod
    def save_theme(theme: str) -> None:
        """Save the current theme to settings."""
        settings = QSettings()
        settings.setValue("theme", theme)
        settings.sync()
    
    @classmethod
    def apply_theme(cls, app: QApplication, theme: str = "dark") -> None:
        """Apply the theme to the application.
        
        Args:
            app: QApplication instance
            theme: Theme name ("dark" or "light")
        """
        try:
            # Save the theme preference
            cls.save_theme(theme)
            
            # Define colors based on theme
            if theme == "dark":
                bg_color = "28, 30, 34"
                surface_color = "40, 43, 49"
                text_color = "255, 255, 255"
                muted_text = "195, 201, 208"
                hover_color = "255, 255, 255"
                hover_alpha = "0.08"
                pressed_alpha = "0.16"
                separator_color = "255, 255, 255"
                separator_alpha = "0.14"
                card_border_alpha = "0.18"
                accent_color = "#5A8CFF"
                accent_hover = "#6C9DFF"
                accent_pressed = "#3F6FD6"
                danger_color = "#EF5350"
                danger_hover = "#FF6E6A"
                danger_pressed = "#C62828"
                control_bg = "rgba(90, 140, 255, 0.12)"
                hero_start = "#2E3553"
                hero_end = "#1B2233"
            else:
                bg_color = "245, 247, 250"
                surface_color = "255, 255, 255"
                text_color = "12, 21, 29"
                muted_text = "92, 102, 112"
                hover_color = "20, 20, 20"
                hover_alpha = "0.06"
                pressed_alpha = "0.12"
                separator_color = "0, 0, 0"
                separator_alpha = "0.12"
                card_border_alpha = "0.12"
                accent_color = "#1F6FEB"
                accent_hover = "#1A5AC7"
                accent_pressed = "#174AB0"
                danger_color = "#E5534B"
                danger_hover = "#F26C65"
                danger_pressed = "#C63C36"
                control_bg = "rgba(31, 111, 235, 0.08)"
                hero_start = "#E6EEFF"
                hero_end = "#D6E4FF"

            card_background = f"rgba({surface_color}, 0.94)"
            input_background = f"rgba({surface_color}, 0.92)"

            # Create base stylesheet with transparency
            base_style = f"""
            QMainWindow {{
                background: rgba({bg_color}, 0.96);
            }}
            QWidget#centralWidget {{
                background: transparent;
                border: none;
            }}
            QFrame#heroHeader {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {hero_start}, stop:1 {hero_end});
                border-radius: 18px;
                border: 1px solid rgba({separator_color}, {card_border_alpha});
            }}
            QLabel#heroTitle {{
                font-size: 20px;
                font-weight: 600;
                color: rgba({text_color}, 0.95);
            }}
            QLabel#heroSubtitle {{
                font-size: 13px;
                color: rgba({muted_text}, 0.82);
            }}
            QFrame#panelCard {{
                background-color: {card_background};
                border-radius: 18px;
                border: 1px solid rgba({separator_color}, {card_border_alpha});
            }}
            QLabel#panelTitle {{
                font-size: 18px;
                font-weight: 600;
                color: rgba({text_color}, 0.96);
            }}
            QLabel#panelSubtitle {{
                font-size: 13px;
                color: rgba({muted_text}, 0.82);
            }}
            QLabel#panelHelper {{
                font-size: 12px;
                color: rgba({muted_text}, 0.76);
            }}
            QFrame#controlButtonBar {{
                background-color: {control_bg};
                border-radius: 14px;
                padding: 12px;
            }}
            QToolBar#mainToolBar {{
                background: rgba({surface_color}, 0.9);
                border: none;
                border-bottom: 1px solid rgba({separator_color}, {card_border_alpha});
                margin: 0px;
                padding: 0px 16px;
            }}
            QToolBar#mainToolBar::separator {{
                background: rgba({separator_color}, {separator_alpha});
                width: 1px;
                height: 18px;
                margin: 0px 8px;
            }}
            QWidget#toolbarTitleContainer {{
                padding: 4px 0px;
            }}
            QLabel#toolbarTitle {{
                font-size: 18px;
                font-weight: 600;
                color: rgba({text_color}, 0.95);
            }}
            QLabel#toolbarSubtitle {{
                font-size: 12px;
                color: rgba({muted_text}, 0.8);
            }}
            QStatusBar#mainStatusBar {{
                background: rgba({surface_color}, 0.9);
                border-top: 1px solid rgba({separator_color}, {card_border_alpha});
                padding: 6px 12px;
            }}
            QToolBar#logPanelToolbar {{
                background: rgba({surface_color}, 0.92);
                border: 1px solid rgba({separator_color}, {card_border_alpha});
                border-top-left-radius: 14px;
                border-top-right-radius: 14px;
                padding: 6px 12px;
            }}
            QTextEdit#logPanelText {{
                background: {input_background};
                border: 1px solid rgba({separator_color}, {card_border_alpha});
                border-top: none;
                border-bottom-left-radius: 14px;
                border-bottom-right-radius: 14px;
                padding: 12px;
                color: rgba({text_color}, 0.9);
            }}
            QToolButton {{
                background: transparent;
                border: none;
                border-radius: 8px;
                padding: 6px 12px;
                color: rgba({text_color}, 0.9);
            }}
            QToolButton:hover {{
                background: rgba({hover_color}, {hover_alpha});
            }}
            QToolButton:pressed {{
                background: rgba({hover_color}, {pressed_alpha});
            }}
            QPushButton {{
                border-radius: 10px;
                padding: 8px 18px;
                border: 1px solid rgba({separator_color}, {card_border_alpha});
                background-color: {input_background};
                color: rgba({text_color}, 0.9);
            }}
            QPushButton:hover {{
                background-color: rgba({hover_color}, {hover_alpha});
            }}
            QPushButton:pressed {{
                background-color: rgba({hover_color}, {pressed_alpha});
            }}
            QPushButton:disabled {{
                color: rgba({muted_text}, 0.5);
                border-color: rgba({separator_color}, 0.1);
            }}
            QPushButton#primaryActionButton {{
                background-color: {accent_color};
                color: #ffffff;
                border: none;
            }}
            QPushButton#primaryActionButton:hover {{
                background-color: {accent_hover};
            }}
            QPushButton#primaryActionButton:pressed {{
                background-color: {accent_pressed};
            }}
            QPushButton#primaryActionButton:disabled {{
                background-color: rgba({separator_color}, 0.2);
                color: rgba({text_color}, 0.4);
            }}
            QPushButton#dangerActionButton {{
                background-color: {danger_color};
                color: #ffffff;
                border: none;
            }}
            QPushButton#dangerActionButton:hover {{
                background-color: {danger_hover};
            }}
            QPushButton#dangerActionButton:pressed {{
                background-color: {danger_pressed};
            }}
            QPushButton#dangerActionButton:disabled {{
                background-color: rgba({separator_color}, 0.18);
                color: rgba({text_color}, 0.35);
            }}
            QPushButton#secondaryActionButton {{
                background-color: transparent;
                border: 1px solid rgba({separator_color}, {card_border_alpha});
                color: rgba({text_color}, 0.85);
            }}
            QPushButton#secondaryActionButton:hover {{
                background-color: rgba({hover_color}, {hover_alpha});
            }}
            QPushButton#secondaryActionButton:pressed {{
                background-color: rgba({hover_color}, {pressed_alpha});
            }}
            QPushButton#pillToggleButton {{
                border-radius: 16px;
                padding: 4px 14px;
                border: 1px solid rgba({separator_color}, {card_border_alpha});
                background-color: transparent;
                color: rgba({text_color}, 0.85);
            }}
            QPushButton#pillToggleButton:checked {{
                background-color: {accent_color};
                color: #ffffff;
                border: none;
            }}
            QPushButton#pillToggleButton:checked:hover {{
                background-color: {accent_hover};
            }}
            QTabWidget::pane {{
                border: 1px solid rgba({separator_color}, {card_border_alpha});
                border-radius: 16px;
                background: {card_background};
                padding: 6px;
            }}
            QTabBar::tab {{
                border-radius: 12px;
                margin: 4px;
                padding: 8px 18px;
                color: rgba({muted_text}, 0.85);
            }}
            QTabBar::tab:selected {{
                background: {accent_color};
                color: #ffffff;
            }}
            QTabBar::tab:hover {{
                background: rgba({hover_color}, {hover_alpha});
                color: rgba({text_color}, 0.9);
            }}
            QSplitter#contentSplitter::handle,
            QSplitter#detailsSplitter::handle,
            QSplitter#resultsSplitter::handle {{
                background: rgba({separator_color}, {card_border_alpha});
                margin: 12px 0px;
                border-radius: 2px;
            }}
            QSplitter#contentSplitter::handle:hover,
            QSplitter#detailsSplitter::handle:hover,
            QSplitter#resultsSplitter::handle:hover {{
                background: rgba({separator_color}, {separator_alpha});
            }}
            QGroupBox {{
                border: 1px solid rgba({separator_color}, {card_border_alpha});
                border-radius: 12px;
                margin-top: 18px;
                background: {card_background};
                padding: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0px 6px;
                color: rgba({text_color}, 0.88);
                font-weight: 600;
            }}
            QLineEdit,
            QTextEdit,
            QPlainTextEdit,
            QSpinBox,
            QDoubleSpinBox,
            QComboBox,
            QDateEdit,
            QTimeEdit {{
                border: 1px solid rgba({separator_color}, {card_border_alpha});
                border-radius: 10px;
                padding: 6px 10px;
                background: {input_background};
                color: rgba({text_color}, 0.9);
            }}
            QLineEdit:focus,
            QTextEdit:focus,
            QPlainTextEdit:focus,
            QSpinBox:focus,
            QDoubleSpinBox:focus,
            QComboBox:focus,
            QDateEdit:focus,
            QTimeEdit:focus {{
                border: 1px solid {accent_color};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox::down-arrow {{
                image: none;
            }}
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollArea > QWidget > QWidget {{
                background: transparent;
            }}
            QToolTip {{
                background-color: rgba({surface_color}, 0.98);
                color: rgba({text_color}, 0.92);
                border: 1px solid rgba({separator_color}, {card_border_alpha});
                padding: 6px 10px;
                border-radius: 8px;
            }}
            """
            
            # Apply the combined stylesheet
            app.setStyleSheet(base_style + qdarktheme.load_stylesheet(theme=theme))
            
            # Apply QPalette for better system integration
            app.setPalette(qdarktheme.load_palette(theme=theme))
            
            # Force an update of all widgets
            for widget in app.allWidgets():
                widget.style().unpolish(widget)
                widget.style().polish(widget)
                widget.update()
            
            logger.debug(f"{theme.capitalize()} theme applied successfully")
        except Exception as e:
            logger.error(f"Error applying theme: {e}")
    
    @classmethod
    def toggle_theme(cls, app: QApplication, window, theme: str = None) -> None:
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
