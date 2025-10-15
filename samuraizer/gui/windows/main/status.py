# windows/main/status.py
from typing import Optional, TYPE_CHECKING
import logging
from PyQt6.QtWidgets import QStatusBar
from PyQt6.QtCore import Qt

if TYPE_CHECKING:
    from samuraizer.gui.windows.main.components.window import MainWindow

logger = logging.getLogger(__name__)

class MainStatusBar(QStatusBar):
    """Main application status bar."""
    
    def __init__(self, parent: 'MainWindow') -> None:
        """Initialize the status bar.
        
        Args:
            parent: Parent MainWindow instance
        """
        super().__init__(parent)
        self.main_window = parent
        self.setup_ui()
        
    def setup_ui(self) -> None:
        """Set up the status bar UI."""
        try:
            # Set initial message
            self.showMessage("Ready")
            
            # Set size grip
            self.setSizeGripEnabled(True)
            
            # Set style
            self.setStyleSheet("""
                QStatusBar {
                    border-top: 1px solid #ccc;
                }
            """)
            
        except Exception as e:
            logger.error(f"Error setting up status bar: {e}", exc_info=True)
            raise
        
    def showMessage(self, message: Optional[str], timeout: int = 0) -> None:
        """Show a status message.

        Args:
            message: Status message to display
            timeout: Message display duration in milliseconds (0 = permanent)
        """
        try:
            # Log the status update
            logger.debug(f"Status update: {message}")

            # Show message with alignment
            super().showMessage(message, timeout)
            
        except Exception as e:
            logger.error(f"Error showing status message: {e}", exc_info=True)
            # Try to show error in status bar
            try:
                super().showMessage(f"Error updating status: {str(e)}")
            except:
                pass  # If this fails too, just silently fail
                
    def clearMessage(self) -> None:
        """Clear the current status message."""
        try:
            super().clearMessage()
            logger.debug("Status message cleared")
        except Exception as e:
            logger.error(f"Error clearing status message: {e}", exc_info=True)
