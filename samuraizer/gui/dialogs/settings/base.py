from __future__ import annotations

from contextlib import contextmanager
from typing import Optional
import logging
from PyQt6.QtWidgets import QGroupBox, QWidget
from PyQt6.QtCore import QSettings

from samuraizer.config.config_manager import ConfigurationManager

logger = logging.getLogger(__name__)

class BaseSettingsGroup(QGroupBox):
    """Base class for settings groups."""
    
    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(title, parent)
        self.settings = QSettings()
        self.config_manager = ConfigurationManager()
        self._suspend_config_updates = False
        try:
            self.config_manager.add_change_listener(self._handle_config_change)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Unable to register configuration listener: %s", exc)
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

    def on_config_changed(self) -> None:
        """Triggered when the unified configuration changes."""
        try:
            self.load_settings()
        except NotImplementedError:
            pass
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Error refreshing settings group %s: %s", self.objectName(), exc)

    @contextmanager
    def suspend_config_updates(self):
        """Temporarily suspend reacting to configuration updates."""
        previous = self._suspend_config_updates
        self._suspend_config_updates = True
        try:
            yield
        finally:
            self._suspend_config_updates = previous

    def _handle_config_change(self) -> None:
        if self._suspend_config_updates:
            return
        self.on_config_changed()
