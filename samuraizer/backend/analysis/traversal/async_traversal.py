"""Asynchronous helpers wrapping traversal logic for non-blocking GUI usage."""

from __future__ import annotations

import asyncio
import os
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from contextlib import suppress
from functools import partial
from typing import Any, AsyncGenerator, Dict

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

    env_override = os.getenv("SAMURAIZER_ASYNC_STREAM_CHUNK")
    if env_override:
        try:
            override_value = int(env_override)
        except ValueError:
            override_value = None
        else:
            if override_value > 0:
                async_buffer_size = override_value

    async_buffer_size = max(1, async_buffer_size)

    loop = asyncio.get_running_loop()
    max_workers = max(1, kwargs.get("threads", 4))
    executor = ThreadPoolExecutor(max_workers=max_workers)

    queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=async_buffer_size)
    sentinel: object = object()
    stop_event = threading.Event()

    def blocking_put(item: Any, *, respect_stop: bool = True) -> None:
        """Synchronously enqueue ``item`` onto the asyncio queue from a thread."""

        future = asyncio.run_coroutine_threadsafe(queue.put(item), loop)

        while True:
            try:
                future.result(timeout=0.1)
                return
            except FuturesTimeoutError:
                if respect_stop and stop_event.is_set():
                    future.cancel()
                    raise asyncio.CancelledError
            except Exception:
                future.cancel()
                raise

    def producer() -> None:
        try:
            for payload in get_directory_structure_stream(*args, **kwargs):
                if stop_event.is_set():
                    break

                try:
                    blocking_put(payload)
                except asyncio.CancelledError:
                    break
        finally:
            if not stop_event.is_set():
                try:
                    blocking_put(sentinel, respect_stop=False)
                except Exception:
                    # TODO: replace with a non-blocking put variant if we observe
                    # contention when delivering the sentinel value.

                    def _fallback_put() -> None:
                        try:
                            queue.put_nowait(sentinel)
                        except asyncio.QueueFull:
                            pass

                    loop.call_soon_threadsafe(_fallback_put)

    producer_future = loop.run_in_executor(executor, producer)
    producer_task = asyncio.wrap_future(producer_future)

    try:
        while True:
            item = await queue.get()
            if item is sentinel:
                break
            yield item

        await producer_task
    finally:
        stop_event.set()

        if not producer_future.done():
            producer_future.cancel()

        with suppress(Exception):
            await producer_task

        await loop.run_in_executor(None, executor.shutdown, True)
