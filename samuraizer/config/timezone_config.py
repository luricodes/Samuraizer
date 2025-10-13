# samuraizer/config/timezone_config.py

"""Timezone configuration backed by the unified configuration manager."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo, available_timezones

from .config_manager import UnifiedConfigManager

logger = logging.getLogger(__name__)


class TimezoneConfigManager:
    """Access timezone settings stored in the unified configuration."""

    def __init__(self, manager: Optional[UnifiedConfigManager] = None) -> None:
        self._manager = manager or UnifiedConfigManager()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_timezone_section(self) -> Dict[str, Any]:
        config = self._manager.get_active_profile_config()
        return config.get("timezone", {})

    # ------------------------------------------------------------------
    # Retrieval helpers
    # ------------------------------------------------------------------

    def get_system_timezone(self) -> timezone:
        local_dt = datetime.now()
        return local_dt.astimezone().tzinfo or timezone.utc

    def get_timezone(self) -> timezone:
        config = self._get_timezone_section()
        if config.get("use_utc", False):
            return timezone.utc

        repository_tz = config.get("repository_timezone")
        if repository_tz:
            try:
                return ZoneInfo(repository_tz)
            except Exception as exc:  # pragma: no cover - depends on tz database
                logger.error("Invalid repository timezone %s: %s", repository_tz, exc)
                return self.get_system_timezone()
        return self.get_system_timezone()

    def get_config(self) -> Dict[str, Any]:
        return self._get_timezone_section()

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def set_repository_timezone(self, tz_name: Optional[str]) -> None:
        if tz_name is not None and tz_name not in available_timezones():
            raise ValueError(f"Invalid timezone name: {tz_name}")
        self._manager.set_value("timezone.repository_timezone", tz_name)
        if tz_name is not None:
            self._manager.set_value("timezone.use_utc", False)

    def use_utc(self, use_utc: bool = True) -> None:
        self._manager.set_value("timezone.use_utc", use_utc)
        if use_utc:
            self._manager.set_value("timezone.repository_timezone", None)


__all__ = ["TimezoneConfigManager"]
