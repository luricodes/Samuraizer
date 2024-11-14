# samuraizer/gui/dialogs/components/settings/groups/general_settings.py

from typing import Optional
import logging
from PyQt6.QtWidgets import (
    QWidget, QFormLayout, QCheckBox,
    QLabel
)
from PyQt6.QtGui import QFont

from ..base import BaseSettingsGroup

logger = logging.getLogger(__name__)

class GeneralSettingsGroup(BaseSettingsGroup):
    """Group for general application settings."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("General Settings", parent)

    def setup_ui(self) -> None:
        """Set up the general settings UI."""
        try:
            layout = QFormLayout()
            layout.setSpacing(10)
            
            # Auto-save setting
            self.auto_save = QCheckBox()
            self.auto_save.setToolTip(
                "Saves the Output Options 'Output File' as well as 'Output Format' "
                "for the next program start"
            )
            layout.addRow("Auto-save Output Options:", self.auto_save)
            
            # Add helper text
            help_text = QLabel(
                "When enabled, output settings will be remembered between sessions"
            )
            help_text.setStyleSheet("color: gray;")
            help_text.setWordWrap(True)
            help_text.setFont(QFont("Segoe UI", 9))
            layout.addRow("", help_text)
            
            self.setLayout(layout)
            
        except Exception as e:
            logger.error(f"Error setting up general settings UI: {e}", exc_info=True)
            raise

    def load_settings(self) -> None:
        """Load general settings."""
        try:
            self.auto_save.setChecked(
                self.settings.value("settings/auto_save", False, type=bool)
            )
            logger.debug(f"Auto-save setting loaded: {self.auto_save.isChecked()}")
        except Exception as e:
            logger.error(f"Error loading general settings: {e}", exc_info=True)
            raise

    def save_settings(self) -> None:
        """Save general settings."""
        try:
            auto_save_value = self.auto_save.isChecked()
            self.settings.setValue("settings/auto_save", auto_save_value)
            # Force settings to sync to disk
            self.settings.sync()
            logger.debug(f"Auto-save setting saved and synced: {auto_save_value}")
        except Exception as e:
            logger.error(f"Error saving general settings: {e}", exc_info=True)
            raise

    def validate(self) -> bool:
        """Validate general settings."""
        return True  # General settings don't need validation
