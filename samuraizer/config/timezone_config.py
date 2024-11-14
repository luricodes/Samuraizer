# samuraizer/config/timezone_config.py

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any
from zoneinfo import ZoneInfo, available_timezones

logger = logging.getLogger(__name__)

class TimezoneConfigManager:
    """Manages timezone configuration for the Samuraizer."""
    
    def __init__(self) -> None:
        self.config_file = Path.home() / '.samuraizer' / 'timezone_config.json'
        self.default_config = {
            'use_utc': False,  # By default, use system timezone
            'repository_timezone': None  # None means use system timezone
        }
        self._load_config()

    def _load_config(self) -> None:
        """Load timezone configuration from file or create with defaults."""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
                # Validate loaded config
                if not all(key in self.config for key in self.default_config):
                    self.config = self.default_config.copy()
            else:
                self.config = self.default_config.copy()
                self._save_config()
        except Exception as e:
            logger.error(f"Error loading timezone config: {e}")
            self.config = self.default_config.copy()

    def _save_config(self) -> None:
        """Save current timezone configuration to file."""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving timezone config: {e}")

    def get_system_timezone(self) -> timezone:
        """
        Get the system's local timezone.
        
        Returns:
            The system's timezone
        """
        local_dt = datetime.now()
        return local_dt.astimezone().tzinfo

    def get_timezone(self) -> timezone:
        """
        Get the appropriate timezone based on configuration.
        
        Returns:
            timezone: The configured timezone (UTC, repository timezone, or system timezone)
        """
        if self.config['use_utc']:
            return timezone.utc
        
        repo_tz = self.config['repository_timezone']
        if repo_tz:
            try:
                return ZoneInfo(repo_tz)
            except Exception as e:
                logger.error(f"Invalid repository timezone {repo_tz}: {e}")
                return self.get_system_timezone()
        
        # If no specific timezone is set and not using UTC, return system timezone
        return self.get_system_timezone()

    def set_repository_timezone(self, tz_name: Optional[str]) -> None:
        """
        Set the repository timezone.
        
        Args:
            tz_name: Timezone name (e.g., 'America/New_York') or None to use system timezone
        """
        if tz_name is not None and tz_name not in available_timezones():
            raise ValueError(f"Invalid timezone name: {tz_name}")
        
        self.config['repository_timezone'] = tz_name
        # When setting a specific timezone, ensure UTC is disabled
        if tz_name is not None:
            self.config['use_utc'] = False
        self._save_config()

    def use_utc(self, use_utc: bool = True) -> None:
        """
        Set whether to use UTC for all timestamps.
        
        Args:
            use_utc: If True, use UTC; if False, use repository timezone or system timezone
        """
        self.config['use_utc'] = use_utc
        if use_utc:
            # Clear repository timezone when switching to UTC
            self.config['repository_timezone'] = None
        self._save_config()

    def get_config(self) -> Dict[str, Any]:
        """Get current timezone configuration."""
        return self.config.copy()
