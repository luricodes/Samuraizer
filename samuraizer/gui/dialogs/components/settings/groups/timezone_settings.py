# samuraizer/gui/dialogs/components/settings/groups/timezone_settings.py

import logging
from typing import Optional
from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QComboBox,
    QCheckBox, QLabel, QWidget
)
from zoneinfo import available_timezones

from samuraizer.config.timezone_config import TimezoneConfigManager

logger = logging.getLogger(__name__)

class TimezoneSettingsGroup(QGroupBox):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Timezone Settings", parent)
        self.timezone_config = TimezoneConfigManager()
        self.setup_ui()

    def setup_ui(self) -> None:
        """Set up the timezone settings UI."""
        layout = QVBoxLayout()

        # UTC checkbox
        self.use_utc_checkbox = QCheckBox("Use UTC for all timestamps")
        self.use_utc_checkbox.stateChanged.connect(self._on_utc_changed)
        layout.addWidget(self.use_utc_checkbox)

        # Repository timezone selection
        layout.addWidget(QLabel("Repository Timezone:"))
        self.timezone_combo = QComboBox()
        
        # Add system default as first option
        system_tz = self.timezone_config.get_system_timezone()
        self.timezone_combo.addItem(f"System Default ({system_tz})")
        
        # Add all available timezones
        for tz in sorted(available_timezones()):
            self.timezone_combo.addItem(tz)

        self.timezone_combo.currentIndexChanged.connect(self._on_timezone_changed)
        layout.addWidget(self.timezone_combo)
        
        # Add description label
        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        layout.addWidget(self.description_label)
        
        self.setLayout(layout)
        
        # Load current settings
        self.load_settings()
        self._update_description()

    def _on_utc_changed(self, state: int) -> None:
        """Handle UTC checkbox state changes."""
        is_checked = bool(state)
        self.timezone_combo.setEnabled(not is_checked)
        if is_checked:
            self.timezone_config.use_utc(True)
        else:
            # When unchecking UTC, revert to system default
            self.timezone_combo.setCurrentIndex(0)
            self.timezone_config.use_utc(False)
        self._update_description()

    def _on_timezone_changed(self, index: int) -> None:
        """Handle timezone combo box changes."""
        if self.use_utc_checkbox.isChecked():
            return
            
        if index == 0:  # System Default
            self.timezone_config.set_repository_timezone(None)
        else:
            tz_name = self.timezone_combo.currentText()
            self.timezone_config.set_repository_timezone(tz_name)
        self._update_description()

    def _update_description(self) -> None:
        """Update the description label based on current settings."""
        if self.use_utc_checkbox.isChecked():
            self.description_label.setText(
                "Using UTC for all timestamps. This ensures consistent "
                "timestamp representation across different time zones."
            )
        else:
            current_tz = self.timezone_config.get_timezone()
            if self.timezone_combo.currentIndex() == 0:
                self.description_label.setText(
                    f"Using system timezone: {current_tz}. "
                    "Timestamps will be displayed in your local time."
                )
            else:
                self.description_label.setText(
                    f"Using repository timezone: {current_tz}. "
                    "Timestamps will be displayed in the selected timezone."
                )

    def load_settings(self) -> None:
        """Load current timezone settings."""
        try:
            config = self.timezone_config.get_config()
            
            # Set UTC checkbox
            self.use_utc_checkbox.setChecked(config['use_utc'])
            
            # Set timezone combo
            current_tz = config['repository_timezone']
            if current_tz:
                index = self.timezone_combo.findText(current_tz)
                if index >= 0:
                    self.timezone_combo.setCurrentIndex(index)
            else:
                self.timezone_combo.setCurrentIndex(0)  # System Default
                
            # Update timezone combo enabled state
            self.timezone_combo.setEnabled(not config['use_utc'])
            
            # Update description
            self._update_description()
            
        except Exception as e:
            logger.error(f"Error loading timezone settings: {e}")

    def save_settings(self) -> None:
        """Save current timezone settings."""
        try:
            use_utc = self.use_utc_checkbox.isChecked()
            self.timezone_config.use_utc(use_utc)
            
            if not use_utc:
                if self.timezone_combo.currentIndex() == 0:
                    self.timezone_config.set_repository_timezone(None)
                else:
                    tz_text = self.timezone_combo.currentText()
                    self.timezone_config.set_repository_timezone(tz_text)
                    
        except Exception as e:
            logger.error(f"Error saving timezone settings: {e}")

    def validate(self) -> bool:
        """Validate timezone settings."""
        try:
            if not self.use_utc_checkbox.isChecked():
                current_index = self.timezone_combo.currentIndex()
                if current_index > 0:  # Not System Default
                    tz_text = self.timezone_combo.currentText()
                    if tz_text not in available_timezones():
                        logger.error(f"Invalid timezone selected: {tz_text}")
                        return False
            return True
        except Exception as e:
            logger.error(f"Error validating timezone settings: {e}")
            return False
