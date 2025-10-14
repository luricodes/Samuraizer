from __future__ import annotations

import logging
from typing import Any, Dict
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)


class TimezoneNormalizer:
    """Normalise and validate timezone settings across configuration profiles."""

    def normalise_timezone(self, data: Dict[str, Any]) -> bool:
        corrected = False

        def _coerce(container: Dict[str, Any]) -> None:
            nonlocal corrected
            timezone_cfg = container.get("timezone")
            if not isinstance(timezone_cfg, dict):
                container["timezone"] = {"use_utc": False}
                corrected = True
                return

            use_utc_value = timezone_cfg.get("use_utc")
            if not isinstance(use_utc_value, bool):
                timezone_cfg["use_utc"] = bool(use_utc_value)
                corrected = True

            tz_value = timezone_cfg.get("repository_timezone")
            if tz_value is None:
                if "repository_timezone" in timezone_cfg:
                    timezone_cfg.pop("repository_timezone", None)
                    corrected = True
                return
            if not isinstance(tz_value, str):
                timezone_cfg.pop("repository_timezone", None)
                corrected = True
                return

            tz_name = tz_value.strip()
            if not tz_name:
                timezone_cfg.pop("repository_timezone", None)
                corrected = True
                return
            if tz_name != tz_value:
                timezone_cfg["repository_timezone"] = tz_name
                corrected = True

            try:
                ZoneInfo(tz_name)
            except ZoneInfoNotFoundError:
                if tz_name.upper() == "UTC":
                    if timezone_cfg.get("use_utc") is not True:
                        timezone_cfg["use_utc"] = True
                        corrected = True
                    timezone_cfg.pop("repository_timezone", None)
                    logger.info(
                        "Repository timezone 'UTC' is not available on this system. Enabling UTC mode instead."
                    )
                else:
                    logger.warning(
                        "Repository timezone '%s' is not available on this system. Falling back to system timezone.",
                        tz_name,
                    )
                    timezone_cfg.pop("repository_timezone", None)
                corrected = True

        _coerce(data)
        profiles = data.get("profiles", {})
        if isinstance(profiles, dict):
            for profile in profiles.values():
                if isinstance(profile, dict):
                    _coerce(profile)
        return corrected


__all__ = ["TimezoneNormalizer"]
