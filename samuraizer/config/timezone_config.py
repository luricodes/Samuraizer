# samuraizer/config/timezone_config.py

"""Timezone configuration backed by the unified configuration manager."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from .config_manager import UnifiedConfigManager

logger = logging.getLogger(__name__)


class TimezoneConfigManager:
    """Access timezone settings stored in the unified configuration."""

    def __init__(self, manager: Optional[UnifiedConfigManager] = None) -> None:
        self._manager = manager or UnifiedConfigManager()
        try:
            available = set(available_timezones())
        except Exception as exc:  # pragma: no cover - depends on host tzdata
            logger.debug("Unable to enumerate available timezones: %s", exc)
            available = set()
        available.add("UTC")
        self._available_timezones: Set[str] = available

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_timezone_section(self) -> Dict[str, Any]:
        config = self._manager.get_active_profile_config()
        section = config.get("timezone", {})
        use_utc = bool(section.get("use_utc", False))
        repository_tz = section.get("repository_timezone")
        if isinstance(repository_tz, str):
            repository_tz = repository_tz.strip() or None
        else:
            repository_tz = None
        return {"use_utc": use_utc, "repository_timezone": repository_tz}

    def _is_timezone_available(self, tz_name: Optional[str]) -> bool:
        if not tz_name:
            return False
        if tz_name in self._available_timezones:
            return True
        try:
            ZoneInfo(tz_name)
            self._available_timezones.add(tz_name)
            return True
        except ZoneInfoNotFoundError:
            return False

    def _coerce_timezone(self, tz_name: Optional[str], *, log: bool = False) -> Optional[str]:
        if not tz_name:
            return None
        tz_clean = tz_name.strip()
        if not tz_clean:
            return None
        if tz_clean.upper() == "UTC":
            return "UTC"
        if self._is_timezone_available(tz_clean):
            return tz_clean
        if log:
            logger.warning("Timezone '%s' is not available on this system.", tz_clean)
        return None

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

        original_tz = config.get("repository_timezone")
        repository_tz = self._coerce_timezone(original_tz, log=True)
        if repository_tz:
            if repository_tz.upper() == "UTC":
                return timezone.utc
            try:
                return ZoneInfo(repository_tz)
            except ZoneInfoNotFoundError:  # pragma: no cover - defensive
                logger.warning(
                    "Repository timezone '%s' became unavailable. Falling back to system timezone.",
                    repository_tz,
                )
        elif original_tz:
            logger.warning(
                "Repository timezone '%s' is not available. Falling back to system timezone.",
                original_tz,
            )
        return self.get_system_timezone()

    def get_config(self) -> Dict[str, Any]:
        section = self._get_timezone_section()
        coerced = self._coerce_timezone(section.get("repository_timezone"))
        section["repository_timezone"] = coerced
        return section

    @property
    def config(self) -> Dict[str, Any]:
        return self.get_config()

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def set_repository_timezone(self, tz_name: Optional[str]) -> None:
        normalised = self._coerce_timezone(tz_name)
        if tz_name and normalised is None:
            raise ValueError(f"Timezone '{tz_name}' is not available on this system")
        self._manager.set_value("timezone.repository_timezone", normalised)
        if normalised is not None:
            self._manager.set_value("timezone.use_utc", False)

    def use_utc(self, use_utc: bool = True) -> None:
        self._manager.set_value("timezone.use_utc", use_utc)
        if use_utc:
            self._manager.set_value("timezone.repository_timezone", None)

    # ------------------------------------------------------------------
    # Discovery helpers
    # ------------------------------------------------------------------

    def list_timezones(self) -> List[str]:
        return sorted(self._available_timezones)


__all__ = ["TimezoneConfigManager"]
