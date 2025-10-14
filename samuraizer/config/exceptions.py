from __future__ import annotations


class ConfigError(Exception):
    """Base exception for configuration errors."""


class ConfigValidationError(ConfigError):
    """Raised when configuration validation fails."""


class ConfigMigrationError(ConfigError):
    """Raised when configuration migration fails."""


class ConfigIOError(ConfigError):
    """Raised when configuration read/write fails."""


__all__ = [
    "ConfigError",
    "ConfigValidationError",
    "ConfigMigrationError",
    "ConfigIOError",
]
