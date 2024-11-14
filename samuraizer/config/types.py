# samuraizer/config/types.py

from typing import TypedDict, List, Union, Protocol, Optional

class TimezoneConfig(TypedDict):
    use_utc: bool  # If True, always use UTC; if False, use repository_timezone if set, else system timezone
    repository_timezone: Optional[str]  # Optional timezone name for the repository (e.g., "America/New_York")

class ExclusionsConfig(TypedDict):
    folders: List[str]
    files: List[str]
    patterns: List[str]

class ConfigurationData(TypedDict):
    exclusions: ExclusionsConfig
    image_extensions: List[str]
    timezone: TimezoneConfig

class ConfigChangeNotifier(Protocol):
    """Protocol for objects that can notify about configuration changes"""
    def add_change_listener(self, callback: callable) -> None: ...
    def remove_change_listener(self, callback: callable) -> None: ...
