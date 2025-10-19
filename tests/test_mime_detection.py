from __future__ import annotations

from pathlib import Path
import sys

import pytest

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:  # pragma: no cover - defensive path setup
    sys.path.insert(0, ROOT)

from types import SimpleNamespace


class _FakeMagic:
    def __init__(self, mime: bool = True) -> None:  # pragma: no cover - simple stub
        self.mime = mime

    def from_buffer(self, _: bytes) -> str:  # pragma: no cover - simple stub
        return "text/plain"


sys.modules.setdefault("magic", SimpleNamespace(Magic=_FakeMagic))

from samuraizer.utils.file_utils import mime_detection


@pytest.fixture(autouse=True)
def clear_mime_cache():
    mime_detection._is_binary_cached.cache_clear()
    yield
    mime_detection._is_binary_cached.cache_clear()


def test_is_binary_recognises_text_extension(tmp_path: Path):
    file_path = tmp_path / "example.py"
    file_path.write_text("print('hello world')\n", encoding="utf-8")

    assert mime_detection.is_binary(file_path) is False


def test_is_binary_recognises_binary_extension(tmp_path: Path):
    file_path = tmp_path / "image.png"
    file_path.write_bytes(b"\x89PNG\r\n\x1a\n")

    assert mime_detection.is_binary(file_path) is True


def test_is_binary_heuristic_handles_minified_text(tmp_path: Path):
    file_path = tmp_path / "bundle"
    # Simulate minified JavaScript with a high proportion of printable ASCII.
    file_path.write_text(
        "!function(){for(var a=0;a<1000;a++)console.log('value',a)}();",
        encoding="utf-8",
    )

    assert mime_detection.is_binary(file_path) is False


def test_is_binary_falls_back_when_magic_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    file_path = tmp_path / "ambiguous.bin"
    # Include NULL bytes to ensure the heuristic fallback marks it as binary.
    file_path.write_bytes(b"\x00\x00\x01compressed-like-data")

    class FailingMagic:
        def from_buffer(self, _sample: bytes) -> str:
            raise RuntimeError("regex error 14 for `^pattern$`, (failed to get memory)")

    monkeypatch.setattr(mime_detection, "analyse_sample", lambda _sample: None)
    monkeypatch.setattr(mime_detection, "get_magic_instance", lambda: FailingMagic())

    assert mime_detection.is_binary(file_path) is True
