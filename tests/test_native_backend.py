from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pytest

from samuraizer.backend.analysis import file_processor, hash_service
from samuraizer.backend.analysis.traversal import traversal_processor
from samuraizer.utils.file_utils import mime_detection

try:
    from samuraizer import _native
except ImportError:  # pragma: no cover - optional native module
    _native = None


def _collect_chunks(generator: Any) -> List[Dict[str, Any]]:
    return [chunk for chunk in generator]


@pytest.mark.skipif(_native is None, reason="Native module not available")
def test_native_hash_matches_python(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    file_path = tmp_path / "example.txt"
    file_path.write_text("hello world", encoding="utf-8")

    monkeypatch.setattr(hash_service, "_native", None)
    python_hash = hash_service.HashService.compute_file_hash(file_path)

    native_hash = _native.compute_hash(str(file_path))

    assert native_hash == python_hash


@pytest.mark.skipif(_native is None, reason="Native module not available")
def test_native_text_preview_matches_python(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    file_path = tmp_path / "sample.txt"
    content = "Sample content with café and unicode — preview"
    file_path.write_text(content, encoding="utf-8")

    preview_limit = 1024

    monkeypatch.setattr(file_processor, "_native", None)
    python_preview = file_processor._read_text_file(file_path, preview_limit, None)

    native_preview = _native.read_text_preview(str(file_path), preview_limit, None)

    assert native_preview == python_preview


@pytest.mark.skipif(_native is None, reason="Native module not available")
def test_native_binary_preview_matches_python(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    binary_file = tmp_path / "image.bin"
    binary_file.write_bytes(b"\x89PNG" + b"\x00" * 32)
    large_binary = tmp_path / "huge.bin"
    large_binary.write_bytes(b"\x00" * 4096)

    preview_limit = 64

    monkeypatch.setattr(file_processor, "_native", None)
    python_preview = file_processor._read_binary_file(binary_file, preview_limit)
    python_excluded = file_processor._read_binary_file(large_binary, preview_limit)

    native_preview = _native.read_binary_preview(str(binary_file), preview_limit)
    native_excluded = _native.read_binary_preview(str(large_binary), preview_limit)

    assert native_preview == python_preview
    assert native_excluded == python_excluded


@pytest.mark.skipif(_native is None, reason="Native module not available")
def test_native_binary_classifier_matches_python(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    text_file = tmp_path / "notes.txt"
    text_file.write_text("plain text", encoding="utf-8")
    binary_file = tmp_path / "data.bin"
    binary_file.write_bytes(b"\x00\x01\x02")

    monkeypatch.setattr(mime_detection, "_native", None)
    python_text = mime_detection.is_binary(text_file)
    python_binary = mime_detection.is_binary(binary_file)

    native_text = _native.classify_binary(str(text_file))
    native_binary = _native.classify_binary(str(binary_file))

    assert python_text == bool(native_text)
    assert python_binary == bool(native_binary)


@pytest.mark.skipif(_native is None, reason="Native module not available")
def test_native_traversal_matches_python(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
        threads=1,
        encoding="utf-8",
        hashing_enabled=False,
        progress_callback=None,
        chunk_callback=None,
        cancellation_token=None,
        chunk_size=2,
        max_pending_tasks=None,
    )

    monkeypatch.setattr(hash_service, "_native", None)
    monkeypatch.setattr(file_processor, "_native", None)
    monkeypatch.setattr(traversal_processor, "_native", None)
    python_chunks = _collect_chunks(
        traversal_processor._generate_directory_chunks_python(**options)
    )

    monkeypatch.setattr(hash_service, "_native", _native)
    monkeypatch.setattr(file_processor, "_native", _native)
    monkeypatch.setattr(traversal_processor, "_native", _native)
    native_chunks = _collect_chunks(
        traversal_processor._generate_directory_chunks_native(**options)
    )

    assert native_chunks == python_chunks


@pytest.mark.skipif(_native is None, reason="Native module not available")
def test_native_traversal_honours_cancellation(tmp_path: Path) -> None:
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

    chunks = _collect_chunks(traversal_processor._generate_directory_chunks_native(**options))

    entry_chunks = [chunk for chunk in chunks if "entries" in chunk]
    summary = next(chunk["summary"] for chunk in chunks if "summary" in chunk)

    assert summary["stopped_early"] is True
    assert summary["processed_files"] < 10
    assert len(entry_chunks) <= summary["processed_files"]
