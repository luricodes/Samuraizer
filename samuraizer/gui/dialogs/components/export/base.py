# samuraizer/gui/dialogs/export/base.py
from typing import Optional
import logging
from PyQt6.QtWidgets import QGroupBox, QWidget
from PyQt6.QtCore import QSettings

logger = logging.getLogger(__name__)

class BaseExportGroup(QGroupBox):
    """Base class for export dialog groups."""
    
    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(title, parent)
        self.settings = QSettings()
        self.setup_ui()

    def setup_ui(self) -> None:
        """Set up the group's UI."""
        raise NotImplementedError("Subclasses must implement setup_ui")

    def load_settings(self) -> None:
        """Load settings for this group."""
        raise NotImplementedError("Subclasses must implement load_settings")

    def save_settings(self) -> None:
        """Save settings for this group."""
        raise NotImplementedError("Subclasses must implement save_settings")

    def validate(self) -> bool:
        """Validate settings for this group."""
        return True  # Default implementation
