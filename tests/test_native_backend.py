from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pytest

from samuraizer.backend.analysis import hash_service
from samuraizer.backend.analysis.traversal import traversal_processor
from samuraizer.utils.file_utils import mime_detection

try:  # pragma: no cover - the extension ships with the wheel
    from samuraizer import _native
except ImportError:  # pragma: no cover - defensive guard for type checkers
    _native = None


def _collect_chunks(generator: Any) -> List[Dict[str, Any]]:
    return list(generator)


@pytest.mark.skipif(_native is None, reason="Native module not available")
def test_hash_service_round_trip(tmp_path: Path) -> None:
    file_path = tmp_path / "example.txt"
    file_path.write_text("hello world", encoding="utf-8")

    native_hash = _native.compute_hash(str(file_path))
    python_hash = hash_service.HashService.compute_file_hash(file_path)

    assert native_hash == python_hash
    assert isinstance(python_hash, str)
    assert len(python_hash) == 16


@pytest.mark.skipif(_native is None, reason="Native module not available")
def test_text_and_binary_previews(tmp_path: Path) -> None:
    text_path = tmp_path / "payload.txt"
    text_path.write_text("Sample café text", encoding="utf-8")

    binary_path = tmp_path / "payload.bin"
    binary_path.write_bytes(b"\x89PNG" + b"\x00" * 32)

    text_preview = _native.read_text_preview(str(text_path), 1024, None)
    binary_preview = _native.read_binary_preview(str(binary_path), 64)

    assert text_preview["type"] == "text"
    assert "café" in text_preview["content"]
    assert binary_preview["type"] == "binary"
    assert binary_preview["encoding"] == "base64"


@pytest.mark.skipif(_native is None, reason="Native module not available")
def test_mime_detection_delegates_to_native(tmp_path: Path) -> None:
    text_file = tmp_path / "notes.md"
    text_file.write_text("hello", encoding="utf-8")

    binary_file = tmp_path / "data.bin"
    binary_file.write_bytes(b"\x00\x01\x02")

    assert mime_detection.is_binary(text_file) is False
    assert mime_detection.is_binary(binary_file) is True


@pytest.mark.skipif(_native is None, reason="Native module not available")
def test_traversal_pipeline(tmp_path: Path) -> None:
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "a.txt").write_text("alpha", encoding="utf-8")
    (tmp_path / "nested" / "b.log").write_text("beta", encoding="utf-8")
    (tmp_path / "keep.bin").write_bytes(b"\x00\x01\x02")
    (tmp_path / "large.bin").write_bytes(b"\x00" * 2048)

    options = dict(
        root_dir=tmp_path,
        max_file_size=512,
        include_binary=True,
        excluded_folders=set(),
        excluded_files={"ignore.me"},
        follow_symlinks=False,
        image_extensions={".png"},
        exclude_patterns=["*.log"],
        threads=2,
        encoding="utf-8",
        hashing_enabled=True,
        progress_callback=None,
        chunk_callback=None,
        cancellation_token=None,
        chunk_size=2,
        max_pending_tasks=None,
    )

    chunks = _collect_chunks(traversal_processor.generate_directory_chunks(**options))

    entries = [chunk for chunk in chunks if "entries" in chunk]
    summary = [chunk for chunk in chunks if "summary" in chunk][0]["summary"]

    processed_files = sum(len(chunk["entries"]) for chunk in entries)

    assert summary["included_files"] == processed_files
    assert summary["hash_algorithm"] == "xxhash"

    flattened = [item for chunk in entries for item in chunk["entries"]]
    filenames = {entry["filename"] for entry in flattened}
    assert "a.txt" in filenames
    assert "keep.bin" in filenames
    assert "b.log" not in filenames


@pytest.mark.skipif(_native is None, reason="Native module not available")
def test_traversal_honours_cancellation(tmp_path: Path) -> None:
    class DummyCancellation:
        def __init__(self, trigger_after: int) -> None:
            self.trigger_after = trigger_after
            self.calls = 0

        def is_cancellation_requested(self) -> bool:
            self.calls += 1
            return self.calls >= self.trigger_after

    for index in range(10):
        (tmp_path / f"file_{index}.txt").write_text(f"payload {index}", encoding="utf-8")

    token = DummyCancellation(trigger_after=4)

    options = dict(
        root_dir=tmp_path,
        max_file_size=1024,
        include_binary=False,
        excluded_folders=set(),
        excluded_files=set(),
        follow_symlinks=False,
        image_extensions=set(),
        exclude_patterns=[],
        threads=2,
        encoding="utf-8",
        hashing_enabled=False,
        progress_callback=None,
        chunk_callback=None,
        cancellation_token=token,
        chunk_size=1,
        max_pending_tasks=None,
    )

    chunks = _collect_chunks(traversal_processor.generate_directory_chunks(**options))

    entry_chunks = [chunk for chunk in chunks if "entries" in chunk]
    summary = next(chunk["summary"] for chunk in chunks if "summary" in chunk)

    assert summary["stopped_early"] is True
    assert summary["processed_files"] < 10
    assert len(entry_chunks) <= summary["processed_files"]
