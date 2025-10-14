"""Asynchronous helpers wrapping traversal logic for non-blocking GUI usage."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, AsyncGenerator, Dict, Optional, List

from .traversal_processor import get_directory_structure
from .traversal_stream import get_directory_structure_stream


async def get_directory_structure_async(*args: Any, **kwargs: Any) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Run the synchronous directory structure traversal in a thread pool."""

    max_workers = max(1, kwargs.get("threads", 4))
    loop = asyncio.get_running_loop()
    executor = ThreadPoolExecutor(max_workers=max_workers)
    try:
        func = partial(get_directory_structure, *args, **kwargs)
        return await loop.run_in_executor(executor, func)
    finally:
        await loop.run_in_executor(None, executor.shutdown, True)


async def get_directory_structure_stream_async(
    *args: Any,
    async_buffer_size: int = 256,
    **kwargs: Any,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Yield traversal payloads asynchronously by delegating to a thread."""
    _ = async_buffer_size  # Retained for compatibility

    loop = asyncio.get_running_loop()
    max_workers = max(1, kwargs.get("threads", 4))
    executor = ThreadPoolExecutor(max_workers=max_workers)

    def collect_items() -> List[Dict[str, Any]]:
        return list(get_directory_structure_stream(*args, **kwargs))

    try:
        items = await loop.run_in_executor(executor, collect_items)
        for item in items:
            yield item
    finally:
        await loop.run_in_executor(None, executor.shutdown, True)
