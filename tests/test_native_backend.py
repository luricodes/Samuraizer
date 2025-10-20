import os
from pathlib import Path

import pytest

from samuraizer.backend.analysis.hash_service import HashService
from samuraizer.backend.analysis.traversal.traversal_processor import generate_directory_chunks

try:
    from samuraizer import _native
except ImportError:  # pragma: no cover - optional native module
    _native = None


@pytest.mark.skipif(_native is None, reason="Native module not available")
def test_native_hash_matches_python(tmp_path: Path):
    file_path = tmp_path / "example.txt"
    file_path.write_text("hello world", encoding="utf-8")

    native_hash = _native.compute_hash(str(file_path))
    python_hash = HashService.compute_file_hash(file_path)

    assert native_hash == python_hash


@pytest.mark.skipif(_native is None, reason="Native module not available")
def test_native_text_preview(tmp_path: Path):
    file_path = tmp_path / "sample.txt"
    content = "Sample content for preview"
    file_path.write_text(content, encoding="utf-8")

    preview = _native.read_text_preview(str(file_path), 1024, None)
    assert isinstance(preview, dict)
    assert preview["type"] == "text"
    assert "content" in preview and "preview_bytes" in preview


@pytest.mark.skipif(_native is None, reason="Native module not available")
def test_native_traversal_roundtrip(tmp_path: Path):
    (tmp_path / "nested").mkdir()
    file_a = tmp_path / "nested" / "a.txt"
    file_a.write_text("alpha", encoding="utf-8")
    file_b = tmp_path / "b.bin"
    file_b.write_bytes(b"\x00\x01\x02")

    options = dict(
        root_dir=tmp_path,
        max_file_size=1024,
        include_binary=True,
        excluded_folders=set(),
        excluded_files=set(),
        follow_symlinks=False,
        image_extensions={".png"},
        exclude_patterns=[],
        threads=1,
        encoding="utf-8",
        hashing_enabled=True,
        progress_callback=None,
        chunk_callback=None,
        cancellation_token=None,
        chunk_size=1,
        max_pending_tasks=None,
    )

    chunks = list(generate_directory_chunks(**options))
    assert chunks, "Expected traversal to yield chunks"
    summaries = [chunk.get("summary") for chunk in chunks if "summary" in chunk]
    assert summaries, "Expected summary from traversal"
