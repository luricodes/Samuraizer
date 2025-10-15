# samuraizer/gui/dialogs/components/settings/settings_dialog.py

from typing import Optional, TYPE_CHECKING, cast
import logging
from PyQt6.QtWidgets import QWidget, QTabWidget, QVBoxLayout
from PyQt6.QtCore import QSize

from ..base_dialog import BaseDialog
from .groups import (
    GeneralSettingsGroup,
    ThemeSettingsGroup,
    CacheSettingsGroup,
    ProfileSettingsGroup,
    TimezoneSettingsGroup,
)

if TYPE_CHECKING:
    from ...windows import MainWindow

logger = logging.getLogger(__name__)

class SettingsDialog(BaseDialog):
    def __init__(self, parent: Optional['QWidget'] = None) -> None:
        super().__init__(
            parent=parent,
            title="Settings",
            modal=True,
            minimum_size=QSize(450, 500),
            settings_prefix="settings_dialog"
        )
        self._showing_cache_warning = False
        self._initial_cache_state = None

    def setup_ui(self) -> None:
        """Set up the dialog's user interface."""
        try:
            # Create tab widget
            self.tab_widget = QTabWidget()
            
            # Create settings groups using modular components
            self.profile_settings = ProfileSettingsGroup(self)
            self.general_settings = GeneralSettingsGroup(self)
            self.theme_settings = ThemeSettingsGroup(self)
            self.cache_settings = CacheSettingsGroup(self)
            self.timezone_settings = TimezoneSettingsGroup(self)
            
            # Create tab pages with layouts
            # General tab
            general_tab = QWidget()
            general_layout = QVBoxLayout()
            general_layout.addWidget(self.profile_settings)
            general_layout.addWidget(self.general_settings)
            general_layout.addWidget(self.theme_settings)
            general_layout.addStretch()
            general_tab.setLayout(general_layout)
            
            # System tab
            system_tab = QWidget()
            system_layout = QVBoxLayout()
            system_layout.addWidget(self.cache_settings)
            system_layout.addWidget(self.timezone_settings)
            system_layout.addStretch()
            system_tab.setLayout(system_layout)
            
            # Add tabs to tab widget
            self.tab_widget.addTab(general_tab, "General")
            self.tab_widget.addTab(system_tab, "System")
            
            # Add tab widget to main layout
            self.main_layout.addWidget(self.tab_widget)
            
            # Load all settings initially
            self.load_all_settings()
            
        except Exception as e:
            logger.error(f"Error setting up settings dialog UI: {e}", exc_info=True)
            self.show_error("UI Error", f"Failed to initialize settings dialog: {str(e)}")

    def load_all_settings(self) -> None:
        """Load settings for all components."""
        try:
            self.general_settings.load_settings()
            self.theme_settings.load_settings()
            self.cache_settings.load_settings()
            self.timezone_settings.load_settings()
            self.profile_settings.load_settings()
            logger.debug("All settings loaded successfully")
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
            self.profile_settings.save_settings()
            
            # Force settings to sync to disk
            self.settings.sync()
            logger.debug("Settings saved successfully")
        except Exception as e:
            logger.error(f"Error saving settings: {e}", exc_info=True)
            self.show_error("Settings Error", f"Failed to save settings: {str(e)}")

    def validate(self) -> bool:
        """Validate settings from all components."""
        try:
            valid = (
                self.profile_settings.validate()
                and self.general_settings.validate()
                and self.theme_settings.validate()
                and self.cache_settings.validate()
                and self.timezone_settings.validate()
            )
            return valid
        except Exception as e:
            logger.error(f"Settings validation error: {e}", exc_info=True)
            self.show_error("Validation Error", str(e))
            return False

    def accept(self) -> None:
        """Override accept to ensure settings are saved."""
        try:
            if self.validate():
                # Save all settings before accepting
                self.save_settings()
                super().accept()
        except Exception as e:
            logger.error(f"Error accepting settings dialog: {e}", exc_info=True)
            self.show_error("Accept Error", str(e))

    def get_main_window(self) -> Optional['MainWindow']:
        """Get the main window instance."""
        parent = self.parent()
        if parent is None:
            return None
        try:
            from ...windows.main.components.window import MainWindow as MainWindowClass
        except Exception:  # pragma: no cover - defensive
            return None
        if isinstance(parent, MainWindowClass):
            return cast('MainWindow', parent)
        return None
