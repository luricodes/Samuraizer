# samuraizer/gui/dialogs/components/about/about_dialog.py

from typing import Optional, TYPE_CHECKING
import logging
from PyQt6.QtWidgets import QWidget, QLabel, QDialogButtonBox
from PyQt6.QtCore import Qt, QSize

from ..base_dialog import BaseDialog
from .title_section import TitleSection
from .description_section import DescriptionSection
from .author_section import AuthorSection

if TYPE_CHECKING:
    from ....gui.windows.main.components.window import MainWindow

logger = logging.getLogger(__name__)

class AboutDialog(BaseDialog):
    """
    About dialog showing application information and credits.
    Inherits from BaseDialog for consistent behavior and error handling.
    """
    
    def __init__(self, parent: Optional['QWidget'] = None) -> None:
        """Initialize the About dialog."""
        super().__init__(
            parent,
            title="About Samuraizer",
            modal=True,
            minimum_size=QSize(400, 300)
        )
        
    def setup_ui(self) -> None:
        """Set up the dialog's user interface."""
        try:
            # Title section
            self.main_layout.addWidget(TitleSection(self))
            
            # Version section
            version_label = QLabel("Version 1.0.0")
            version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.main_layout.addWidget(version_label)
            
            # Description section
            self.main_layout.addWidget(DescriptionSection(self))
            
            # Author section
            self.main_layout.addWidget(AuthorSection(self))
            
            # Add stretch to keep everything aligned properly
            self.main_layout.addStretch()
            
        except Exception as e:
            logger.error(f"Error setting up About dialog UI: {e}", exc_info=True)
            self.show_error("UI Error", "Failed to initialize About dialog")

    def needs_buttons(self) -> bool:
        """Override to specify we only need an OK button."""
        return True

    def create_buttons(self) -> None:
        """Create dialog buttons - only OK button for About dialog."""
        try:
            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
            button_box.accepted.connect(self.accept)
            self.main_layout.addWidget(button_box)
        except Exception as e:
            logger.error(f"Error creating buttons: {e}", exc_info=True)
            self.show_error("Error", "Failed to create dialog buttons")
