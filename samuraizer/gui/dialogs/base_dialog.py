# samuraizer/GUI/ui/dialogs/base_dialog.py

from typing import Optional, Any, Dict
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QDialogButtonBox, 
    QWidget, QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt, QSettings, QSize, QPoint
from PyQt6.QtGui import QCloseEvent, QShowEvent, QResizeEvent, QMoveEvent
import logging

logger = logging.getLogger(__name__)

class BaseDialog(QDialog):
    """
    Base dialog class with common functionality for all application dialogs.
    
    Features:
    - Standard layout and button handling
    - State persistence (position, size, etc.)
    - Error handling and logging
    - Cleanup hooks
    - Consistent styling
    """
    
    def __init__(
        self, 
        parent: Optional[QWidget] = None, 
        title: str = "", 
        modal: bool = True,
        minimum_size: QSize = QSize(400, 300),
        settings_prefix: str = ""
    ) -> None:
        """
        Initialize the base dialog.

        Args:
            parent: Parent widget
            title: Dialog title
            modal: Whether dialog is modal
            minimum_size: Minimum dialog size
            settings_prefix: Prefix for settings keys
        """
        super().__init__(parent)
        
        # Initialize instance variables
        self.settings = QSettings()
        self.settings_prefix = settings_prefix or self.__class__.__name__.lower()
        self._cleanup_handlers: Dict[str, Any] = {}
        self._is_initialized = False
        
        # Setup dialog properties
        self.setWindowTitle(title)
        self.setModal(modal)
        self.setMinimumSize(minimum_size)
        
        try:
            # Create main layout with proper margins and spacing
            self.main_layout = QVBoxLayout(self)
            self.main_layout.setSpacing(10)
            self.main_layout.setContentsMargins(10, 10, 10, 10)
            
            # Initialize UI
            self._initialize_ui()
            
        except Exception as e:
            logger.error(f"Error initializing {self.__class__.__name__}: {e}", 
                        exc_info=True)
            self.show_error("Initialization Error", str(e))

    def _initialize_ui(self) -> None:
        """Initialize the UI components in the correct order."""
        try:
            # Create content
            self.setup_ui()
            
            # Add buttons if needed
            if self.needs_buttons():
                self.create_buttons()
            
            # Restore state
            self.restore_state()
            
            self._is_initialized = True
            
        except Exception as e:
            logger.error(f"Error in UI initialization: {e}", exc_info=True)
            self.show_error("UI Error", str(e))

    def setup_ui(self) -> None:
        """
        Set up the dialog's UI content.
        Override this method to create the dialog's specific content.
        """
        pass

    def needs_buttons(self) -> bool:
        """
        Determine if the dialog needs standard buttons.
        Override to customize button behavior.

        Returns:
            bool: True if standard buttons should be added
        """
        return True

    def create_buttons(self) -> None:
        """Create and configure standard dialog buttons."""
        try:
            # Create button box with standard buttons
            self.button_box = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | 
                QDialogButtonBox.StandardButton.Cancel
            )
            
            # Connect signals
            self.button_box.accepted.connect(self.validate_and_accept)
            self.button_box.rejected.connect(self.safe_reject)
            
            # Configure default button
            ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
            if ok_button:
                ok_button.setDefault(True)
                ok_button.setFocus()
            
            # Add to layout
            self.main_layout.addWidget(self.button_box)
            
        except Exception as e:
            logger.error(f"Error creating buttons: {e}", exc_info=True)
            self.show_error("Button Creation Error", str(e))

    def validate_and_accept(self) -> None:
        """Validate input before accepting the dialog."""
        try:
            if self.validate():
                self.safe_accept()
        except Exception as e:
            logger.error(f"Error in validation: {e}", exc_info=True)
            self.show_error("Validation Error", str(e))

    def validate(self) -> bool:
        """
        Validate dialog input. Override to add custom validation.

        Returns:
            bool: True if validation passes
        """
        return True

    def safe_accept(self) -> None:
        """Safely handle dialog acceptance with error handling."""
        try:
            self.save_state()
            self.cleanup()
            super().accept()
        except Exception as e:
            logger.error(f"Error accepting dialog: {e}", exc_info=True)
            self.show_error("Accept Error", str(e))

    def safe_reject(self) -> None:
        """Safely handle dialog rejection with error handling."""
        try:
            self.cleanup()
            super().reject()
        except Exception as e:
            logger.error(f"Error rejecting dialog: {e}", exc_info=True)
            self.show_error("Reject Error", str(e))

    def get_settings_key(self, key: str) -> str:
        """Get a settings key with the proper prefix."""
        return f"{self.settings_prefix}/{key}"

    def save_state(self) -> None:
        """Save dialog state to settings."""
        try:
            # Save geometry and state
            self.settings.setValue(
                self.get_settings_key("geometry"), 
                self.saveGeometry()
            )
            self.settings.setValue(
                self.get_settings_key("state"), 
                self.saveState() if hasattr(self, 'saveState') else None
            )
            
            # Save position and size separately as backup
            self.settings.setValue(
                self.get_settings_key("pos"),
                self.pos()
            )
            self.settings.setValue(
                self.get_settings_key("size"),
                self.size()
            )
            
        except Exception as e:
            logger.error(f"Error saving dialog state: {e}", exc_info=True)

    def restore_state(self) -> None:
        """Restore dialog state from settings."""
        try:
            # Try to restore geometry
            geometry = self.settings.value(self.get_settings_key("geometry"))
            if geometry:
                self.restoreGeometry(geometry)
            
            # Try to restore state
            state = self.settings.value(self.get_settings_key("state"))
            if state and hasattr(self, 'restoreState'):
                self.restoreState(state)
            
            # Fallback to position and size if needed
            if not geometry:
                pos = self.settings.value(self.get_settings_key("pos"))
                size = self.settings.value(self.get_settings_key("size"))
                
                if isinstance(pos, QPoint):
                    self.move(pos)
                if isinstance(size, QSize):
                    self.resize(size)
            
        except Exception as e:
            logger.error(f"Error restoring dialog state: {e}", exc_info=True)

    def add_cleanup_handler(self, key: str, handler: Any) -> None:
        """
        Add a cleanup handler that will be called during cleanup.
        
        Args:
            key: Unique identifier for the handler
            handler: Callable or resource to clean up
        """
        self._cleanup_handlers[key] = handler

    def cleanup(self) -> None:
        """Perform cleanup operations."""
        try:
            # Call all cleanup handlers
            for key, handler in self._cleanup_handlers.items():
                try:
                    if callable(handler):
                        handler()
                    elif hasattr(handler, 'close'):
                        handler.close()
                except Exception as e:
                    logger.error(f"Error in cleanup handler {key}: {e}", 
                               exc_info=True)
                    
            # Clear handlers
            self._cleanup_handlers.clear()
            
        except Exception as e:
            logger.error(f"Error in cleanup: {e}", exc_info=True)

    def show_error(self, title: str, message: str) -> None:
        """
        Show an error message dialog.

        Args:
            title: Error dialog title
            message: Error message
        """
        QMessageBox.critical(self, title, message)

    def showEvent(self, event: Optional[QShowEvent]) -> None:
        """Handle dialog show event."""
        try:
            super().showEvent(event)
            if not hasattr(self, '_shown'):
                self._shown = True
                # Perform any one-time initialization here
        except Exception as e:
            logger.error(f"Error in show event: {e}", exc_info=True)

    def closeEvent(self, event: Optional[QCloseEvent]) -> None:
        """Handle dialog close event."""
        try:
            if self._is_initialized:
                self.save_state()
                self.cleanup()
            super().closeEvent(event)
        except Exception as e:
            logger.error(f"Error in close event: {e}", exc_info=True)
            if event is not None:
                event.accept()  # Ensure dialog closes even if there's an error

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:
        """Handle resize events."""
        try:
            super().resizeEvent(event)
            if self._is_initialized:
                self.save_state()
        except Exception as e:
            logger.error(f"Error in resize event: {e}", exc_info=True)

    def moveEvent(self, event: Optional[QMoveEvent]) -> None:
        """Handle move events."""
        try:
            super().moveEvent(event)
            if self._is_initialized:
                self.save_state()
        except Exception as e:
            logger.error(f"Error in move event: {e}", exc_info=True)
