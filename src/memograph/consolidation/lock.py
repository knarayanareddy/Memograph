"""Exclusive consolidation lock.

Uses POSIX ``flock`` on an open file descriptor.  This is atomic, releases
automatically when a process dies, and does not rely on PIDs, mtimes, or a
check-then-write race.  ``last_consolidated_at`` lives in SQLite, not here.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ..errors import ConfigurationError

try:
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - POSIX-only project
    _fcntl = None  # type: ignore[assignment]


@dataclass(frozen=True)
class LockState:
    held: bool
    holder_pid: int | None = None
    acquired_at: datetime | None = None
    last_consolidated: datetime | None = None
    is_stale: bool = False
    stale_reason: str | None = None


class ConsolidationLock:
    LOCK_FILE_NAME: str = "consolidation.lock"

    def __init__(self, base_path: str | Path):
        if _fcntl is None:
            raise RuntimeError("ConsolidationLock requires POSIX fcntl support")
        self.base_path = Path(base_path)
        self.lock_path = self.base_path / self.LOCK_FILE_NAME
        self._fd: int | None = None

    def _open(self) -> int:
        self.base_path.mkdir(parents=True, exist_ok=True)
        return os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)

    def _try_lock(self, fd: int) -> bool:
        if _fcntl is None:
            raise ConfigurationError("ConsolidationLock requires POSIX fcntl support")
        try:
            _fcntl.flock(fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            return False

    def _release(self, fd: int) -> None:
        if _fcntl is None:
            raise ConfigurationError("ConsolidationLock requires POSIX fcntl support")
        try:
            _fcntl.flock(fd, _fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            os.close(fd)

    def is_available(self) -> bool:
        """Non-blocking probe; never used as the authoritative acquisition."""
        fd = self._open()
        acquired = self._try_lock(fd)
        if acquired:
            self._release(fd)
        else:
            os.close(fd)
        return acquired

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[bool]:
        """Yield ``True`` only while holding the exclusive OS lock."""
        fd = await asyncio.to_thread(self._open)
        acquired = await asyncio.to_thread(self._try_lock, fd)
        if not acquired:
            os.close(fd)
            yield False
            return
        self._fd = fd
        try:
            yield True
        finally:
            self._fd = None
            await asyncio.to_thread(self._release, fd)

    def get_state(self) -> LockState:
        held = not self.is_available()
        return LockState(
            held=held,
            acquired_at=datetime.now(UTC) if held else None,
        )

    def force_release(self) -> bool:
        """Remove the lock file.  Intended for administrative recovery only."""
        existed = self.lock_path.exists()
        self.lock_path.unlink(missing_ok=True)
        return existed

    def __repr__(self) -> str:
        state = self.get_state()
        return f"ConsolidationLock(held={state.held}, path={self.lock_path})"
