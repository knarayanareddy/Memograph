"""A small in-process sliding-window rate limiter."""

from __future__ import annotations

import asyncio
import time
from collections import deque


class RateLimiter:
    def __init__(self, limit_per_minute: int, window_seconds: float = 60.0):
        if limit_per_minute < 1:
            raise ValueError("limit_per_minute must be positive")
        self.limit = limit_per_minute
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, key: str) -> bool:
        now = time.monotonic()
        async with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            self._prune(now)
            return True

    def _prune(self, now: float) -> None:
        for key, hits in list(self._hits.items()):
            while hits and now - hits[0] >= self.window:
                hits.popleft()
            if not hits:
                del self._hits[key]

    async def reset(self, key: str | None = None) -> None:
        async with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)
