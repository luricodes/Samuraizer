from __future__ import annotations

from typing import Any, Iterable, Protocol, cast

from .defaults import CONFIG_SCHEMA

class ValidatorProtocol(Protocol):
    def iter_errors(self, data: Any) -> Iterable[Any]:
        ...


_validator: ValidatorProtocol

try:  # pragma: no cover
    from jsonschema import Draft202012Validator, ValidationError
except ModuleNotFoundError:  # pragma: no cover

    class ValidationError(RuntimeError):  # type: ignore[no-redef]
        """Placeholder used when jsonschema is unavailable."""

        def __init__(self, message: str = "") -> None:
            super().__init__(message or "jsonschema dependency not installed")

    class _MissingValidator(ValidatorProtocol):
        def iter_errors(self, _data: Any) -> Iterable[Any]:
            raise ImportError(
                "Configuration validation requires the 'jsonschema' package. "
                "Install it with 'pip install jsonschema' inside your Samuraizer environment."
            )

    _validator = _MissingValidator()
else:
    _validator = cast(ValidatorProtocol, Draft202012Validator(CONFIG_SCHEMA))

__all__ = ["_validator", "ValidationError"]
