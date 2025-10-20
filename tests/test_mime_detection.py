from __future__ import annotations

from pathlib import Path

import pytest

from samuraizer.utils.file_utils import mime_detection

try:  # pragma: no cover - ships with the wheel
    from samuraizer import _native
except ImportError:  # pragma: no cover - defensive guard for type checkers
    _native = None


@pytest.fixture(autouse=True)
def clear_cache() -> None:
    mime_detection._classify_cached.cache_clear()
    yield
    mime_detection._classify_cached.cache_clear()


@pytest.mark.skipif(_native is None, reason="Native module not available")
def test_is_binary_recognises_text_and_binary(tmp_path: Path) -> None:
    text_file = tmp_path / "example.py"
    text_file.write_text("print('hello world')\n", encoding="utf-8")

    binary_file = tmp_path / "image.bin"
    binary_file.write_bytes(b"\x89PNG\r\n\x1a\n")

    assert mime_detection.is_binary(text_file) is False
    assert mime_detection.is_binary(binary_file) is True


@pytest.mark.skipif(_native is None, reason="Native module not available")
def test_cache_invalidates_on_file_change(tmp_path: Path) -> None:
    file_path = tmp_path / "toggle"
    file_path.write_text("plain text", encoding="utf-8")

    assert mime_detection.is_binary(file_path) is False

    file_path.write_bytes(b"\x00\x01\x02")

    # Ensure mtime has changed; otherwise the cache key could collide on very fast filesystems.
    file_path.touch()

    assert mime_detection.is_binary(file_path) is True
