"""Atomic file writes.

Generated Markdown/JSON files are derived views of SQLite.  They are written
with ``os.replace`` so a reader never observes a partially written file.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def _fsync_directory(path: Path) -> None:
    try:
        fd = os.open(path.parent, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        _fsync_directory(path)
    except BaseException:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
        raise


async def atomic_write_text(path: str | Path, text: str) -> None:
    """Write UTF-8 text atomically without blocking the event loop."""
    await asyncio.to_thread(_atomic_write_text, Path(path), text)


async def atomic_write_json(path: str | Path, payload: Any) -> None:
    """Write JSON atomically with stable formatting."""
    await atomic_write_text(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def _atomic_append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line.rstrip("\n") + "\n")
        handle.flush()
        os.fsync(handle.fileno())


async def atomic_append_line(path: str | Path, line: str) -> None:
    """Append one transcript line with an fsync."""
    await asyncio.to_thread(_atomic_append_line, Path(path), line)


async def read_text(path: str | Path) -> str:
    """Read a UTF-8 text file without blocking the event loop."""
    return await asyncio.to_thread(Path(path).read_text, encoding="utf-8")


async def remove_file(path: str | Path) -> None:
    """Remove a file if present, ignoring a missing file."""

    def _remove() -> None:
        Path(path).unlink(missing_ok=True)

    await asyncio.to_thread(_remove)
