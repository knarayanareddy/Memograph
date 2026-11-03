from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError as PydanticValidationError

from memograph import memory_manager as manager_module
from memograph.atomic import read_text, remove_file
from memograph.config import ConfidenceLevel, MemoryLimits
from memograph.errors import ValidationError
from memograph.models import TopicFile


async def test_crud_and_write_order(manager):
    result = await manager.remember("project_stack", "Uses FastAPI and SQLite", source="readme")
    assert result.success is True
    assert result.fact is not None
    assert result.topic is not None

    json_path = manager._topic_json_path("project_stack")
    md_path = manager._topic_md_path("project_stack")
    assert json_path.exists() and md_path.exists()
    assert manager.index_md_path.exists()
    assert "project_stack" in await read_text(manager.index_md_path)

    topics = await manager.recall("FastAPI")
    assert [topic.topic_id for topic in topics] == ["project_stack"]
    content_before = topics[0].facts[0].content
    fact_id = topics[0].facts[0].fact_id

    # Confidence-only update must not wipe content (the historical promote bug).
    assert await manager.update("project_stack", fact_id, new_confidence=ConfidenceLevel.OBSERVED)
    topic = await manager.get_topic("project_stack")
    assert topic.facts[0].content == content_before

    with pytest.raises(ValidationError):
        await manager.update("project_stack", fact_id, new_confidence=ConfidenceLevel.VERIFIED)
    assert await manager.update(
        "project_stack",
        fact_id,
        new_confidence=ConfidenceLevel.VERIFIED,
        verification_source="src/main.py",
    )
    assert await manager.update("project_stack", "missing_fact") is False
    assert await manager.forget("project_stack", fact_id) is True
    assert await manager.forget("project_stack", fact_id) is False
    assert await manager.forget("project_stack") is True
    assert await manager.forget("missing_topic") is False


async def test_path_validation(manager):
    with pytest.raises(ValidationError):
        await manager.remember("../evil", "fact", source="s")
    with pytest.raises(ValidationError):
        await manager.forget("/absolute")
    with pytest.raises(PydanticValidationError):
        await manager.save_topic(TopicFile(topic_id="../evil", topic_name="Evil"))
    assert not (manager.base_path.parent / "evil.json").exists()


async def test_prune_and_reconcile(manager):
    result = await manager.remember("project", "A fact", source="s")
    assert result.success is True
    json_path = manager._topic_json_path("project")
    await remove_file(json_path)

    assert await manager.prune() == 1
    index = await manager.get_index()
    assert index.get_pointer("project") is None

    # Startup-style reconciliation rebuilds topic files from SQLite.
    await manager.reconcile()
    assert json_path.exists()
    restored = TopicFile.from_json(await read_text(json_path))
    assert restored.facts[0].content == "A fact"

    await manager.reconcile()
    assert "Memograph Index" in await read_text(manager.index_md_path)


async def test_failed_derived_write_reconciles(manager, monkeypatch):
    original = manager_module.atomic_write_text

    async def failing_write(path, text):
        if Path(path) == manager.index_md_path:
            raise OSError("simulated disk full")
        return await original(path, text)

    monkeypatch.setattr(manager_module, "atomic_write_text", failing_write)
    with pytest.raises(OSError):
        await manager.remember("failure_topic", "Should not persist", source="s")

    status = await manager.status()
    assert status["topics"]["total"] == 0
    assert not manager._topic_json_path("failure_topic").exists()
    assert "failure_topic" not in await manager.get_context_injection()


async def test_transcripts_context_and_status(manager):
    session_id = await manager.start_session("session_one")
    assert session_id == "session_one"
    await manager.archive_turn("user", "What about FastAPI?")
    await manager.archive_turn("assistant", "FastAPI is used.")
    await manager.end_session()

    results = await manager.grep_transcripts("FastAPI")
    assert len(results) >= 1
    assert "FastAPI" in results[0]["snippet"]
    with pytest.raises(ValidationError):
        await manager.grep_transcripts("[", regex=True)
    signals = await manager.recent_signals(limit=5)
    assert any("FastAPI" in signal for signal in signals)

    await manager.remember("project", "Uses FastAPI", source="s")
    built = await manager.build_context("FastAPI")
    assert "hints, not ground truth" in built.text
    assert "Uses FastAPI" in built.text

    status = await manager.status()
    assert status["topics"]["total"] == 1
    assert status["index"]["pointers"] == 1
    assert status["index"]["bytes"] <= status["index"]["max_bytes"]


async def test_grep_enforces_pattern_length(manager):
    with pytest.raises(ValidationError, match="pattern too long"):
        await manager.grep_transcripts("a" * 201, regex=True)


async def test_grep_regex_timeout(config_factory):
    config = config_factory(limits=MemoryLimits(grep_timeout_seconds=0.001))
    async with manager_module.MemoryManager(config=config) as manager:
        await manager.start_session("session_timeout")
        await manager.archive_turn("user", "a" * 1000 + "b")
        await manager.end_session()
        with pytest.raises(ValidationError, match="timed out"):
            await manager.grep_transcripts("(a|aa)+$", regex=True)
