from __future__ import annotations

import asyncio

from memograph.consolidation.lock import ConsolidationLock


async def test_exclusive_lock(tmp_path):
    first = ConsolidationLock(tmp_path)
    second = ConsolidationLock(tmp_path)
    assert first.is_available() is True
    async with first.acquire() as acquired:
        assert acquired is True
        assert first.get_state().held is True
        assert second.is_available() is False
        async with second.acquire() as other:
            assert other is False
    assert first.is_available() is True
    assert second.is_available() is True


async def test_racing_tasks_only_one_wins(tmp_path):
    async def grab() -> bool:
        lock = ConsolidationLock(tmp_path)
        async with lock.acquire() as acquired:
            if acquired:
                await asyncio.sleep(0.05)
            return acquired

    results = await asyncio.gather(grab(), grab())
    assert sorted(results) == [False, True]


async def test_lock_does_not_use_mtime_as_state(tmp_path):
    lock = ConsolidationLock(tmp_path)
    assert lock.is_available() is True
    before = lock.lock_path.stat().st_mtime
    async with lock.acquire() as acquired:
        assert acquired is True
    after = lock.lock_path.stat().st_mtime
    assert before == after
    assert lock.get_state().last_consolidated is None


async def test_force_release(tmp_path):
    lock = ConsolidationLock(tmp_path)
    assert lock.is_available() is True
    assert lock.force_release() is True
    assert lock.force_release() is False
