"""Bounded, in-process event fan-out for WebSocket subscribers."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any


def make_event(event_type: str, **payload: Any) -> dict[str, Any]:
    return {
        "type": event_type,
        "payload": payload,
        "timestamp": datetime.now(UTC).isoformat(),
    }


class EventBroker:
    def __init__(self, max_queue_size: int = 100):
        self.max_queue_size = max_queue_size
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def publish(self, event: dict[str, Any]) -> int:
        delivered = 0
        for queue in tuple(self._subscribers):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:  # pragma: no cover - defensive
                    pass
            try:
                queue.put_nowait(event)
                delivered += 1
            except asyncio.QueueFull:  # pragma: no cover - defensive
                continue
        return delivered

    @asynccontextmanager
    async def subscription(self) -> AsyncIterator[asyncio.Queue[dict[str, Any]]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=self.max_queue_size)
        self._subscribers.add(queue)
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)

    async def close(self) -> None:
        self._subscribers.clear()
