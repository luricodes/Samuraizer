# samuraizer/gui/dialogs/components/settings/components/general_settings.py

from typing import Optional
import logging
from PyQt6.QtWidgets import (
    QWidget, QFormLayout, QCheckBox
)

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
            self.auto_save.setToolTip("Saves the Output Options 'Output File' aswell as 'Output Format' for the next program start")
            layout.addRow("Auto-save Output Options:", self.auto_save)
            
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
