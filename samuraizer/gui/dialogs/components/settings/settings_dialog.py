# samuraizer/gui/dialogs/components/settings/settings_dialog.py

from typing import Optional, TYPE_CHECKING
import logging
from PyQt6.QtWidgets import QWidget, QTabWidget, QVBoxLayout
from PyQt6.QtCore import QSize

from ...base_dialog import BaseDialog
from .groups import (
    GeneralSettingsGroup,
    ThemeSettingsGroup,
    CacheSettingsGroup
)
from .groups.timezone_settings import TimezoneSettingsGroup
from .groups.llm_settings import LLMSettingsGroup

if TYPE_CHECKING:
    from ....windows import MainWindow

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
            self.general_settings = GeneralSettingsGroup(self)
            self.theme_settings = ThemeSettingsGroup(self)
            self.cache_settings = CacheSettingsGroup(self)
            self.timezone_settings = TimezoneSettingsGroup(self)
            self.llm_settings = LLMSettingsGroup(self)
            
            # Create tab pages with layouts
            # General tab
            general_tab = QWidget()
            general_layout = QVBoxLayout()
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
            
            # LLM tab
            llm_tab = QWidget()
            llm_layout = QVBoxLayout()
            llm_layout.addWidget(self.llm_settings)
            llm_layout.addStretch()
            llm_tab.setLayout(llm_layout)
            
            # Add tabs to tab widget
            self.tab_widget.addTab(general_tab, "General")
            self.tab_widget.addTab(system_tab, "System")
            self.tab_widget.addTab(llm_tab, "LLM API Settings")
            
            # Add tab widget to main layout
            self.main_layout.addWidget(self.tab_widget)
            
            # Load settings
            self.load_settings()
            
        except Exception as e:
            logger.error(f"Error setting up settings dialog UI: {e}", exc_info=True)
            self.show_error("UI Error", f"Failed to initialize settings dialog: {str(e)}")

    def load_settings(self) -> None:
        """Load settings for all components."""
        try:
            # Load settings for all groups regardless of current tab
            self.general_settings.load_settings()
            self.theme_settings.load_settings()
            self.cache_settings.load_settings()
            self.timezone_settings.load_settings()
            self.llm_settings.load_settings()
            logger.debug("Settings loaded successfully")
        except Exception as e:
            logger.error(f"Error loading settings: {e}", exc_info=True)
            self.show_error("Settings Error", f"Failed to load settings: {str(e)}")

    def save_settings(self) -> None:
        """Save settings from all components."""
        try:
            # Save settings for all groups regardless of current tab
            self.general_settings.save_settings()
            self.theme_settings.save_settings()
            self.cache_settings.save_settings()
            self.timezone_settings.save_settings()
            self.llm_settings.save_settings()
            # Force settings to sync to disk
            self.settings.sync()
            logger.debug("Settings saved successfully")
        except Exception as e:
            logger.error(f"Error saving settings: {e}", exc_info=True)
            self.show_error("Settings Error", f"Failed to save settings: {str(e)}")

    def validate(self) -> bool:
        """Validate settings from the current tab only."""
        try:
            current_tab_index = self.tab_widget.currentIndex()
            current_tab_text = self.tab_widget.tabText(current_tab_index)
            
            # Only validate the current tab's settings
            if current_tab_text == "General":
                valid = self.general_settings.validate() and self.theme_settings.validate()
            elif current_tab_text == "System":
                valid = self.cache_settings.validate() and self.timezone_settings.validate()
            elif current_tab_text == "LLM API Settings":
                valid = self.llm_settings.validate()
            else:
                valid = True
            
            if valid:
                # Save all settings when validation passes
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
                # Save all settings before accepting
                self.save_settings()
                super().accept()
        except Exception as e:
            logger.error(f"Error accepting settings dialog: {e}", exc_info=True)
            self.show_error("Accept Error", str(e))

    def get_main_window(self) -> Optional['MainWindow']:
        """Get the main window instance."""
        return self.parent()
