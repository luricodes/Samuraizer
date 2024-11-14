# samuraizer/config/events.py

from enum import Enum, auto
from dataclasses import dataclass
from typing import Any, Optional

class ConfigEventType(Enum):
    """Types of configuration events"""
    CONFIG_LOADED = auto()
    CONFIG_SAVED = auto()
    CONFIG_RESET = auto()
    EXCLUSION_ADDED = auto()
    EXCLUSION_REMOVED = auto()
    CONFIG_ERROR = auto()

@dataclass
class ConfigEvent:
    """Event data for configuration changes"""
    event_type: ConfigEventType
    source: str
    data: Optional[Any] = None
    error: Optional[Exception] = None

    @classmethod
    def create_error_event(cls, source: str, error: Exception) -> 'ConfigEvent':
        """Create an error event"""
        return cls(ConfigEventType.CONFIG_ERROR, source, error=error)

    @classmethod
    def create_change_event(cls, event_type: ConfigEventType, source: str, data: Any = None) -> 'ConfigEvent':
        """Create a change event"""
        return cls(event_type, source, data=data)