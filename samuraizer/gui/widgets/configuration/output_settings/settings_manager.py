# samuraizer/gui/widgets/configuration/output_settings/settings_manager.py

import logging
from PyQt6.QtCore import QSettings

logger = logging.getLogger(__name__)

class SettingsManager:
    def __init__(self):
        self.settings = QSettings()

    def load_setting(self, key, default=None, type_=None):
        try:
            if type_ is not None:
                return self.settings.value(key, default, type=type_)
            return self.settings.value(key, default)
        except Exception as e:
            logger.error(f"Error loading setting '{key}': {e}", exc_info=True)
            return default

    def save_setting(self, key, value):
        try:
            self.settings.setValue(key, value)
            self.settings.sync()
            logger.debug(f"Saved setting '{key}': {value}")
        except Exception as e:
            logger.error(f"Error saving setting '{key}': {e}", exc_info=True)
