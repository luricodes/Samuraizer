# samuraizer/config/listener.py

from abc import ABC, abstractmethod
import logging
from typing import Optional, Set
from .events import ConfigEvent, ConfigEventType

logger = logging.getLogger(__name__)


class ConfigurationListener(ABC):
    """Base class for configuration change listeners"""

    def __init__(self) -> None:
        self._subscribed_events: Set[ConfigEventType] = set()

    def subscribe_to_event(self, event_type: ConfigEventType) -> None:
        """Subscribe to a specific event type"""
        self._subscribed_events.add(event_type)

    def unsubscribe_from_event(self, event_type: ConfigEventType) -> None:
        """Unsubscribe from a specific event type"""
        self._subscribed_events.discard(event_type)

    def handle_event(self, event: ConfigEvent) -> None:
        """Handle a configuration event"""
        if event.event_type in self._subscribed_events:
            try:
                self._process_event(event)
            except Exception as e:
                logger.error(f"Error processing configuration event: {e}")

    @abstractmethod
    def _process_event(self, event: ConfigEvent) -> None:
        """Process a configuration event.

        Must be implemented by subclasses to handle specific event types.
        """
        pass
