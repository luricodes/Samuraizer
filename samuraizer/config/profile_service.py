from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from typing import Any, Dict, MutableMapping, Set

from .exceptions import ConfigValidationError, ConfigError
from .utils import _deep_merge
from .profiles import _apply_profile_customisations, _resolve_default_base


@dataclass(frozen=True)
class ProfileResolutionResult:
    name: str
    config: Dict[str, Any]


class ProfileService:
    """Validation and resolution helpers for configuration profiles."""

    def validate_profiles(self, data: Dict[str, Any]) -> None:
        profiles = data.get("profiles", {})
        if not profiles:
            return
        for name, profile in profiles.items():
            inherit = profile.get("inherit", "default")
            if inherit != "default" and inherit not in profiles:
                raise ConfigValidationError(
                    f"Profile '{name}' inherits from unknown profile '{inherit}'"
                )
        for name in profiles:
            self._detect_cycle(name, profiles)

    def _detect_cycle(self, start: str, profiles: Dict[str, Dict[str, Any]]) -> None:
        seen: Set[str] = set()
        current = start
        while True:
            if current == "default":
                return
            if current in seen:
                raise ConfigValidationError(
                    f"Circular inheritance detected at profile '{current}'"
                )
            seen.add(current)
            parent = profiles[current].get("inherit", "default")
            if parent == "default":
                return
            if parent not in profiles:
                raise ConfigValidationError(
                    f"Profile '{current}' inherits from unknown profile '{parent}'"
                )
            current = parent

    def resolve(
        self,
        profile_name: str,
        raw_config: Dict[str, Any],
        cache: MutableMapping[str, ProfileResolutionResult],
    ) -> ProfileResolutionResult:
        if profile_name in cache:
            return cache[profile_name]

        if profile_name == "default":
            base = _resolve_default_base(raw_config)
            result = ProfileResolutionResult("default", base)
            cache["default"] = result
            return result

        profiles = raw_config.get("profiles", {})
        profile_data = profiles.get(profile_name)
        if profile_data is None:
            raise ConfigError(f"Profile '{profile_name}' is not defined")

        inherit = profile_data.get("inherit", "default")
        parent_result = self.resolve(inherit, raw_config, cache)
        overrides = {k: deepcopy(v) for k, v in profile_data.items() if k != "inherit"}
        merged = _deep_merge(parent_result.config, overrides)
        merged = _apply_profile_customisations(merged, overrides)
        result = ProfileResolutionResult(profile_name, merged)
        cache[profile_name] = result
        return result


__all__ = ["ProfileService", "ProfileResolutionResult"]
