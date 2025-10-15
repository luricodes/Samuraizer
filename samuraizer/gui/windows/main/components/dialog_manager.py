import logging
from typing import TYPE_CHECKING
from PyQt6.QtWidgets import QMessageBox

if TYPE_CHECKING:
    from ...base.window import BaseWindow
    from samuraizer.gui.dialogs.settings import SettingsDialog
    from samuraizer.gui.dialogs.about import AboutDialog
else:
    from ...base.window import BaseWindow
    from samuraizer.gui.dialogs import settings, about
    SettingsDialog = settings.SettingsDialog
    AboutDialog = about.AboutDialog

logger = logging.getLogger(__name__)

class DialogManager:
    """Manages dialog windows."""
    
    def __init__(self, parent: 'BaseWindow') -> None:
        self.parent = parent

    def show_settings(self) -> None:
        """Show the settings dialog."""
        try:
            settings_dialog = SettingsDialog(self.parent)
            settings_dialog.exec()
        except Exception as e:
            error_msg = f"Error showing settings: {str(e)}"
            logger.error(error_msg, exc_info=True)
            status_bar = getattr(self.parent, "status_bar", None)
            if status_bar is not None:
                status_bar.showMessage(error_msg)

    def show_about(self) -> None:
        """Show the about dialog."""
        try:
            about_dialog = AboutDialog(self.parent)
            about_dialog.exec()
        except Exception as e:
            error_msg = f"Error showing about: {str(e)}"
            logger.error(error_msg, exc_info=True)
            status_bar = getattr(self.parent, "status_bar", None)
            if status_bar is not None:
                status_bar.showMessage(error_msg)