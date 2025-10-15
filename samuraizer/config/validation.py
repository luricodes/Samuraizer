from __future__ import annotations

from typing import Any, Iterable

from .defaults import CONFIG_SCHEMA

try:  # pragma: no cover
    from jsonschema import Draft202012Validator, ValidationError
except ModuleNotFoundError:  # pragma: no cover
    Draft202012Validator = None  # type: ignore[assignment]

    class ValidationError(RuntimeError):  # type: ignore[no-redef]
        """Placeholder used when jsonschema is unavailable."""

        def __init__(self, message: str = "") -> None:
            super().__init__(message or "jsonschema dependency not installed")

    class _MissingValidator:
        def iter_errors(self, _data: Any) -> Iterable[Any]:
            raise ImportError(
                "Configuration validation requires the 'jsonschema' package. "
                "Install it with 'pip install jsonschema' inside your Samuraizer environment."
            )

    _validator = _MissingValidator()
else:
    _validator = Draft202012Validator(CONFIG_SCHEMA)

__all__ = ["_validator", "ValidationError"]
