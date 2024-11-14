# samuraizer/gui/dialogs/components/settings/components/theme_settings.py

from typing import Optional
import logging
from PyQt6.QtWidgets import (
    QWidget, QFormLayout, QLabel,
    QComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ..base import BaseSettingsGroup

logger = logging.getLogger(__name__)

class ThemeSettingsGroup(BaseSettingsGroup):
    """Group for theme-related settings."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("Theme Settings", parent)

    def setup_ui(self) -> None:
        """Set up the theme settings UI."""
        try:
            layout = QFormLayout()
            layout.setSpacing(10)
            
            # Theme selection combo box
            self.theme_combo = QComboBox()
            self.theme_combo.addItems(["Dark", "Light"])
            self.theme_combo.setToolTip("Select application theme")
            self.theme_combo.currentTextChanged.connect(self.on_theme_changed)
            layout.addRow("Application theme:", self.theme_combo)
            
            # Add helper text
            theme_help = QLabel("Theme changes apply immediately")
            theme_help.setStyleSheet("color: gray;")
            theme_help.setWordWrap(True)
            theme_help.setFont(QFont("Segoe UI", 9))
            layout.addRow("", theme_help)
            
            self.setLayout(layout)
            
        except Exception as e:
            logger.error(f"Error setting up theme settings UI: {e}", exc_info=True)
            raise

    def on_theme_changed(self, theme_name: str) -> None:
        """Handle theme selection changes."""
        try:
            # Convert theme name to lowercase for system use
            theme = theme_name.lower()
            current_theme = self.settings.value("theme", "dark", str)
            
            if theme != current_theme:
                # Get the main window (parent of the dialog)
                dialog_parent = self.parent().parent()
                if dialog_parent and hasattr(dialog_parent, 'toggle_theme'):
                    # Call the parent window's theme toggle
                    dialog_parent.toggle_theme()
                    
        except Exception as e:
            logger.error(f"Error changing theme: {e}", exc_info=True)
            if hasattr(self.parent(), 'show_error'):
                self.parent().show_error("Theme Error", str(e))

    def load_settings(self) -> None:
        """Load theme settings."""
        try:
            self.theme_combo.blockSignals(True)
            current_theme = self.settings.value("theme", "dark", str)
            theme_index = self.theme_combo.findText(
                current_theme.capitalize(),
                Qt.MatchFlag.MatchFixedString
            )
            if theme_index >= 0:
                self.theme_combo.setCurrentIndex(theme_index)
            self.theme_combo.blockSignals(False)
        except Exception as e:
            logger.error(f"Error loading theme settings: {e}", exc_info=True)
            raise

    def save_settings(self) -> None:
        """Save theme settings."""
        try:
            # Theme settings are saved immediately when changed
            pass
        except Exception as e:
            logger.error(f"Error saving theme settings: {e}", exc_info=True)
            raise

    def validate(self) -> bool:
        """Validate theme settings."""
        return True  # Theme settings don't need validation