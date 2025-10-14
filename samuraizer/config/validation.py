from __future__ import annotations

try:
    from jsonschema import Draft202012Validator, ValidationError
except ModuleNotFoundError as exc:  # pragma: no cover
    raise ImportError(
        "The 'jsonschema' package is required for configuration validation. "
        "Install it with 'pip install jsonschema' inside your Samuraizer environment."
    ) from exc

from .defaults import CONFIG_SCHEMA

_validator = Draft202012Validator(CONFIG_SCHEMA)

__all__ = ["_validator", "ValidationError"]
