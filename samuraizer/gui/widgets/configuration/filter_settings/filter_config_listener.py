# samuraizer/gui/widgets/configuration/filter_settings/filter_config_listener.py

import logging
from typing import TYPE_CHECKING
from samuraizer.config.listener import ConfigurationListener
from samuraizer.config.events import ConfigEvent, ConfigEventType

if TYPE_CHECKING:
    from .file_filters import FileFiltersWidget

logger = logging.getLogger(__name__)

class FilterConfigListener(ConfigurationListener):
    """Listens for configuration changes and updates the file filters widget"""

    def __init__(self, file_filters_widget: 'FileFiltersWidget') -> None:
        super().__init__()
        self.widget = file_filters_widget
        
        # Subscribe to relevant events
        self.subscribe_to_event(ConfigEventType.CONFIG_LOADED)
        self.subscribe_to_event(ConfigEventType.CONFIG_RESET)
        self.subscribe_to_event(ConfigEventType.EXCLUSION_ADDED)
        self.subscribe_to_event(ConfigEventType.EXCLUSION_REMOVED)

    def _process_event(self, event: ConfigEvent) -> None:
        """Process configuration events and update the widget"""
        try:
            if event.event_type in {ConfigEventType.CONFIG_LOADED, ConfigEventType.CONFIG_RESET}:
                self._update_all_filters()
            elif event.event_type == ConfigEventType.EXCLUSION_ADDED:
                self._handle_exclusion_added(event)
            elif event.event_type == ConfigEventType.EXCLUSION_REMOVED:
                self._handle_exclusion_removed(event)
        except Exception as e:
            logger.error(f"Error processing configuration event in filter widget: {e}")

    def _update_all_filters(self) -> None:
        """Update all filter lists from current configuration"""
        try:
            # Get current configuration
            config = self.widget.config_manager.exclusion_config
            
            # Update folder list
            self.widget.folders_list.setItems(config.get_excluded_folders())
            
            # Update file list
            self.widget.files_list.setItems(config.get_excluded_files())
            
            # Update patterns list
            self.widget.patterns_list.setPatterns(config.get_exclude_patterns())
            
            # Update image extensions list
            self.widget.image_list.setItems(config.get_image_extensions())
            
        except Exception as e:
            logger.error(f"Error updating filter lists: {e}")

    def _handle_exclusion_added(self, event: ConfigEvent) -> None:
        """Handle addition of exclusion items"""
        if not event.data:
            return
            
        try:
            exclusion_type, value = event.data
            if exclusion_type == 'folder':
                self.widget.folders_list.addItem(value)
            elif exclusion_type == 'file':
                self.widget.files_list.addItem(value)
            elif exclusion_type == 'pattern':
                self.widget.patterns_list.addPattern(value)
            elif exclusion_type == 'image_extension':
                self.widget.image_list.addItem(value)
        except Exception as e:
            logger.error(f"Error handling exclusion addition: {e}")

    def _handle_exclusion_removed(self, event: ConfigEvent) -> None:
        """Handle removal of exclusion items"""
        if not event.data:
            return
            
        try:
            exclusion_type, value = event.data
            if exclusion_type == 'folder':
                self.widget.folders_list.removeItem(value)
            elif exclusion_type == 'file':
                self.widget.files_list.removeItem(value)
            elif exclusion_type == 'pattern':
                self.widget.patterns_list.removePattern(value)
            elif exclusion_type == 'image_extension':
                self.widget.image_list.removeItem(value)
        except Exception as e:
            logger.error(f"Error handling exclusion removal: {e}")
