"""Utilities for working with text encodings."""

from __future__ import annotations

import logging
from codecs import lookup
from typing import Optional

logger = logging.getLogger(__name__)

_AUTO_ENCODING_ALIASES = {
    "auto",
    "automatic",
    "auto-detect",
    "autodetect",
    "detect",
}


def normalize_encoding_hint(value: Optional[str]) -> Optional[str]:
    """Normalize a user-provided encoding hint.

    ``None`` and empty strings are treated as ``None``. Known aliases that
    indicate automatic detection (e.g. ``"auto"``) are also resolved to
    ``None``. If the supplied encoding name is unknown to Python's codec
    registry we emit a warning and fall back to ``None`` so that downstream
    consumers can attempt automatic detection.
    """

    if value is None:
        return None

    normalized = value.strip()
    if not normalized:
        return None

    lowered = normalized.lower()
    if lowered in _AUTO_ENCODING_ALIASES:
        logger.debug("Encoding hint '%s' resolved to automatic detection", value)
        return None

    try:
        lookup(normalized)
    except LookupError:
        logger.warning(
            "Unknown encoding hint '%s'; falling back to automatic detection", value
        )
        return None

    return normalized


__all__ = ["normalize_encoding_hint"]

