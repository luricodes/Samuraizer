import asyncio
import time

import pytest

# Ensure the repository root is importable when running this test file directly.
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:  # pragma: no cover - defensive path setup
    sys.path.insert(0, ROOT)

# Provide a lightweight stub for the optional ``magic`` dependency so tests do not
# require the native libmagic shared library.


class _FakeMagic:
    def __init__(self, mime: bool = True) -> None:  # pragma: no cover - simple stub
        self.mime = mime

    def from_buffer(self, _: bytes) -> str:  # pragma: no cover - simple stub
        return "text/plain"


sys.modules.setdefault("magic", SimpleNamespace(Magic=_FakeMagic))

from samuraizer.backend.analysis.traversal import async_traversal


@pytest.mark.parametrize("buffer_size", [1, 2])
def test_get_directory_structure_stream_async_streams_incrementally(monkeypatch, buffer_size):
    total = 10
    produced = []

    def fake_stream(*args, **kwargs):
        for index in range(total):
            produced.append(index)
            time.sleep(0.01)
            yield {"idx": index}

    monkeypatch.setattr(
        async_traversal, "get_directory_structure_stream", fake_stream
    )

    async def consume() -> tuple[list[int], int]:
        agen = async_traversal.get_directory_structure_stream_async(
            async_buffer_size=buffer_size
        )
        first = await agen.__anext__()
        mid_count = len(produced)
        second = await agen.__anext__()
        async for _ in agen:
            pass
        return [first["idx"], second["idx"]], mid_count

    results, mid_count = asyncio.run(consume())

    assert results == [0, 1]
    assert mid_count < total


def test_env_override_applies(monkeypatch):
    total = 3
    produced = []

    def fake_stream(*args, **kwargs):
        for index in range(total):
            produced.append(index)
            yield {"idx": index}

    monkeypatch.setenv("SAMURAIZER_ASYNC_STREAM_CHUNK", "1")
    monkeypatch.setattr(
        async_traversal, "get_directory_structure_stream", fake_stream
    )

    async def consume() -> list[int]:
        items = []
        async for payload in async_traversal.get_directory_structure_stream_async():
            items.append(payload["idx"])
        return items

    results = asyncio.run(consume())

    assert results == [0, 1, 2]
    assert produced == results
