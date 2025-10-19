# samuraizer/gui/dialogs/components/settings/groups/general_settings.py

from typing import Optional
import logging
from PyQt6.QtWidgets import (
    QWidget, QFormLayout,
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

            info_label = QLabel(
                "Output options are now saved automatically with each profile."
            )
            info_label.setWordWrap(True)
            info_label.setStyleSheet("color: gray;")
            info_label.setFont(QFont("Segoe UI", 9))

            layout.addRow("Output persistence:", info_label)
            self.setLayout(layout)

        except Exception as e:
            logger.error(f"Error setting up general settings UI: {e}", exc_info=True)
            raise

    def load_settings(self) -> None:
        """Load general settings."""
        logger.debug("General settings load: no persisted values required")

    def save_settings(self) -> None:
        """Save general settings."""
        logger.debug("General settings save: nothing to persist")

    def validate(self) -> bool:
        """Validate general settings."""
        return True  # General settings don't need validation
