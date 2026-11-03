from __future__ import annotations

import asyncio
import json

from memograph.atomic import (
    atomic_append_line,
    atomic_write_json,
    atomic_write_text,
    read_text,
)


async def test_atomic_write_text_and_json(tmp_path):
    path = tmp_path / "nested" / "value.txt"
    await atomic_write_text(path, "hello\n")
    assert await read_text(path) == "hello\n"
    assert list(path.parent.glob(".value.txt.*.tmp")) == []

    json_path = tmp_path / "value.json"
    await atomic_write_json(json_path, {"ok": True, "items": [1, 2]})
    assert json.loads(await read_text(json_path)) == {"ok": True, "items": [1, 2]}


async def test_atomic_append(tmp_path):
    path = tmp_path / "transcript.jsonl"
    await atomic_append_line(path, '{"n": 1}')
    await atomic_append_line(path, '{"n": 2}')
    assert (await read_text(path)).splitlines() == ['{"n": 1}', '{"n": 2}']


async def test_concurrent_writes_are_atomic(tmp_path):
    path = tmp_path / "race.txt"
    values = [f"value-{item}" for item in range(10)]
    await asyncio.gather(*(atomic_write_text(path, value) for value in values))
    final = (await read_text(path)).strip()
    assert final in values
    assert list(path.parent.glob(".race.txt.*.tmp")) == []
