# samuraizer/utils/helpers.py

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from typing import Optional, Set

from colorama import Fore, Style
from pathlib import Path

import charset_normalizer

logger = logging.getLogger(__name__)

HEURISTIC_SAMPLE_SIZE = 8192

# Fast-path file extension classification keeps libmagic off the hot path for
# obvious text or binary assets. The sets intentionally focus on common file
# types encountered during repository analysis and can be extended in the
# future if necessary.
TEXTUAL_EXTENSIONS: Set[str] = {
    ".c",
    ".cc",
    ".cfg",
    ".cmake",
    ".conf",
    ".cpp",
    ".cs",
    ".css",
    ".csv",
    ".dart",
    ".env",
    ".go",
    ".gradle",
    ".h",
    ".hpp",
    ".html",
    ".ini",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".kt",
    ".less",
    ".lock",
    ".lua",
    ".m",
    ".md",
    ".php",
    ".pl",
    ".properties",
    ".ps1",
    ".py",
    ".pyi",
    ".r",
    ".rb",
    ".rs",
    ".rst",
    ".sass",
    ".scala",
    ".scss",
    ".sh",
    ".sql",
    ".swift",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".vue",
    ".yaml",
    ".yml",
}

BINARY_EXTENSIONS: Set[str] = {
    ".7z",
    ".apng",
    ".avi",
    ".bmp",
    ".class",
    ".dll",
    ".dylib",
    ".exe",
    ".gif",
    ".gz",
    ".ico",
    ".iso",
    ".jar",
    ".jpeg",
    ".jpg",
    ".lz",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".ogg",
    ".otf",
    ".pdf",
    ".png",
    ".psd",
    ".pyd",
    ".rar",
    ".so",
    ".svgz",
    ".tar",
    ".tgz",
    ".ttf",
    ".wav",
    ".webm",
    ".webp",
    ".woff",
    ".woff2",
    ".xz",
    ".zip",
}

_SAFE_CONTROL_BYTES = {9, 10, 12, 13}
_PRINTABLE_ASCII = set(range(32, 127)) | {9, 10, 12, 13}


@dataclass(frozen=True)
class SampleStatistics:
    printable_ratio: float
    control_ratio: float
    nul_ratio: float


def read_file_sample(file_path: Path, sample_size: int = HEURISTIC_SAMPLE_SIZE) -> bytes:
    with open(file_path, "rb") as fh:
        return fh.read(sample_size)


def classify_by_extension(file_path: Path) -> Optional[bool]:
    suffix = file_path.suffix.lower()
    if suffix in TEXTUAL_EXTENSIONS:
        return False
    if suffix in BINARY_EXTENSIONS:
        return True
    return None


def _analyse_sample_statistics(sample: bytes) -> SampleStatistics:
    if not sample:
        return SampleStatistics(printable_ratio=1.0, control_ratio=0.0, nul_ratio=0.0)

    counts = Counter(sample)
    total = len(sample)
    printable = sum(count for byte, count in counts.items() if byte in _PRINTABLE_ASCII)
    control = sum(
        count for byte, count in counts.items() if byte < 32 and byte not in _SAFE_CONTROL_BYTES
    )
    nul_count = counts.get(0, 0)
    return SampleStatistics(
        printable_ratio=printable / total,
        control_ratio=control / total,
        nul_ratio=nul_count / total,
    )


def analyse_sample(sample: bytes) -> Optional[bool]:
    """Analyse the provided byte sample and return ``True`` if binary, ``False``
    if text, or ``None`` when the heuristics are inconclusive."""

    stats = _analyse_sample_statistics(sample)

    # Strong binary signals should immediately short-circuit to avoid heavier
    # processing. NULL bytes or a large number of control characters are common
    # in compressed or compiled artefacts.
    if stats.nul_ratio > 0.0:
        # Even a small proportion of NULL bytes is a strong indicator of binary
        # data. The threshold is intentionally low because text files rarely
        # contain them legitimately.
        if stats.nul_ratio >= 0.001 or sample.find(b"\x00\x00") != -1:
            return True

    if stats.control_ratio > 0.10 and stats.printable_ratio < 0.9:
        return True

    if stats.printable_ratio >= 0.95 and stats.control_ratio <= 0.02:
        return False

    if stats.printable_ratio <= 0.60:
        return True

    try:
        match = charset_normalizer.from_bytes(sample).best()
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.debug("charset_normalizer failed to analyse sample: %s", exc)
        match = None

    if match and match.encoding:
        # ``percent_coherence`` ranges from 0-100. Values above ~60 indicate
        # valid and consistent text according to charset-normalizer's model.
        if match.percent_coherence is not None and match.percent_coherence >= 60:
            return False
        if match.percent_chaos is not None and match.percent_chaos > 40:
            return True

    return None


def is_binary_alternative(file_path: Path, sample: Optional[bytes] = None) -> bool:
    """Fallback method for binary file detection relying on heuristics."""

    try:
        sample_bytes = sample if sample is not None else read_file_sample(file_path)
    except Exception as exc:
        logger.error(
            "%sError during alternative binary check for %s: %s%s",
            Fore.RED,
            file_path,
            exc,
            Style.RESET_ALL,
        )
        return False

    decision = analyse_sample(sample_bytes)
    # When the heuristics are inconclusive we prefer to treat the file as text
    # so that consumers can still inspect the content rather than silently
    # dropping it.
    return decision if decision is not None else False


__all__ = [
    "HEURISTIC_SAMPLE_SIZE",
    "TEXTUAL_EXTENSIONS",
    "BINARY_EXTENSIONS",
    "classify_by_extension",
    "read_file_sample",
    "analyse_sample",
    "is_binary_alternative",
]
