# samuraizer/gui/dialogs/components/settings/settings_dialog.py

from typing import Optional, TYPE_CHECKING
import logging
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QSize

from ...base_dialog import BaseDialog
from .groups import (
    GeneralSettingsGroup,
    ThemeSettingsGroup,
    CacheSettingsGroup
)
from .groups.timezone_settings import TimezoneSettingsGroup

if TYPE_CHECKING:
    from ....windows import MainWindow

logger = logging.getLogger(__name__)

class SettingsDialog(BaseDialog):
    def __init__(self, parent: Optional['QWidget'] = None) -> None:
        super().__init__(
            parent=parent,
            title="Settings",
            modal=True,
            minimum_size=QSize(350, 200),
            settings_prefix="settings_dialog"
        )
        self._showing_cache_warning = False
        self._initial_cache_state = None

    def setup_ui(self) -> None:
        """Set up the dialog's user interface."""
        try:
            # Create settings groups using modular components
            self.general_settings = GeneralSettingsGroup(self)
            self.theme_settings = ThemeSettingsGroup(self)
            self.cache_settings = CacheSettingsGroup(self)
            self.timezone_settings = TimezoneSettingsGroup(self)
            
            # Add components to layout
            self.main_layout.addWidget(self.general_settings)
            self.main_layout.addWidget(self.theme_settings)
            self.main_layout.addWidget(self.cache_settings)
            self.main_layout.addWidget(self.timezone_settings)
            
            # Add stretch to keep everything aligned at the top
            self.main_layout.addStretch()
            
            # Load settings
            self.load_settings()
            
        except Exception as e:
            logger.error(f"Error setting up settings dialog UI: {e}", exc_info=True)
            self.show_error("UI Error", f"Failed to initialize settings dialog: {str(e)}")

    def load_settings(self) -> None:
        """Load settings for all components."""
        try:
            self.general_settings.load_settings()
            self.theme_settings.load_settings()
            self.cache_settings.load_settings()
            self.timezone_settings.load_settings()
            logger.debug("Settings loaded successfully")
        except Exception as e:
            logger.error(f"Error loading settings: {e}", exc_info=True)
            self.show_error("Settings Error", f"Failed to load settings: {str(e)}")

    def save_settings(self) -> None:
        """Save settings from all components."""
        try:
            self.general_settings.save_settings()
            self.theme_settings.save_settings()
            self.cache_settings.save_settings()
            self.timezone_settings.save_settings()
            # Force settings to sync to disk
            self.settings.sync()
            logger.debug("Settings saved successfully")
        except Exception as e:
            logger.error(f"Error saving settings: {e}", exc_info=True)
            self.show_error("Settings Error", f"Failed to save settings: {str(e)}")

    def validate(self) -> bool:
        """Validate settings from all components."""
        try:
            valid = all([
                self.general_settings.validate(),
                self.theme_settings.validate(),
                self.cache_settings.validate(),
                self.timezone_settings.validate()
            ])
            if valid:
                # Save settings when validation passes
                self.save_settings()
            return valid
        except Exception as e:
            logger.error(f"Settings validation error: {e}", exc_info=True)
            self.show_error("Validation Error", str(e))
            return False

    def accept(self) -> None:
        """Override accept to ensure settings are saved."""
        try:
            if self.validate():
                super().accept()
        except Exception as e:
            logger.error(f"Error accepting settings dialog: {e}", exc_info=True)
            self.show_error("Accept Error", str(e))
