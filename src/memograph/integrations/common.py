"""Shared helpers for synchronous framework SDK adapters."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from typing import Any, TypeVar

T = TypeVar("T")


def clip_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)] + "…"


class AsyncBridge:
    """Run async Memograph operations on a dedicated event-loop thread.

    LangChain and CrewAI expose synchronous memory interfaces, while
    ``MemoryManager`` and ``aiosqlite`` are bound to one event loop. A single
    background loop keeps every operation on the loop that opened the database.
    """

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._closed = False
        self._thread = threading.Thread(target=self._run, name="memograph-async", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5.0)

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._ready.set()
        self._loop.run_forever()

    def run(self, coro: Coroutine[Any, Any, T], timeout: float = 30.0) -> T:
        if self._closed:
            coro.close()
            raise RuntimeError("AsyncBridge is closed")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5.0)
        self._loop.close()

    def __enter__(self) -> AsyncBridge:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
