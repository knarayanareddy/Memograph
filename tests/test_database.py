from __future__ import annotations

import pytest

from memograph.config import ConfidenceLevel
from memograph.errors import ValidationError
from memograph.models import IndexPointer, MemoryFact, TopicFile


def make_topic() -> TopicFile:
    return TopicFile(
        topic_id="project",
        topic_name="Project",
        facts=[
            MemoryFact(
                fact_id="fact_1",
                content="Uses Python 3.11",
                confidence=ConfidenceLevel.OBSERVED,
                source="readme",
            )
        ],
        tags=["python"],
        file_path="topics/project.json",
    )


async def test_schema_and_agent(db):
    assert await db.fetchval("SELECT version FROM schema_version LIMIT 1") == 1
    await db.ensure_agent("a1", "Agent One")
    await db.ensure_agent("a1")
    assert await db.fetchval("SELECT COUNT(*) FROM agents WHERE id = ?", ("a1",)) == 1


async def test_topic_and_fact_crud(db):
    await db.ensure_agent("a1")
    topic = make_topic()
    await db.upsert_topic("a1", topic, topic.file_path)
    await db.replace_topic_facts("a1", topic)
    loaded = await db.get_topic("a1", "project")
    assert loaded is not None
    assert loaded.tags == ["python"]
    assert loaded.facts[0].content == "Uses Python 3.11"

    assert await db.update_fact_confidence("a1", "project", "fact_1", "verified")
    rows = await db.get_facts("a1", "project")
    assert rows[0]["confidence_level"] == "verified"
    assert await db.delete_fact("a1", "project", "fact_1") is True
    assert await db.get_facts("a1", "project") == []


async def test_index_pointers(db):
    await db.ensure_agent("a1")
    pointer = IndexPointer(
        topic_id="project",
        topic_file_path="topics/project.json",
        summary="project facts",
        confidence=0.7,
    )
    await db.upsert_index_pointer("a1", pointer)
    rows = await db.get_index_pointers("a1")
    assert len(rows) == 1
    assert rows[0]["pointer_line"] == pointer.pointer_line
    assert rows[0]["is_stale"] is False
    await db.delete_index_pointer("a1", "project")
    assert await db.get_index_pointers("a1") == []


async def test_sessions_and_dream_state(db):
    await db.ensure_agent("a1")
    await db.create_session("a1", "session_1", "2026-01-01T00:00:00+00:00")
    await db.end_session("a1", "session_1", 3)
    assert await db.count_sessions_since("a1", "1970-01-01T00:00:00+00:00") == 1

    await db.upsert_dream_state("a1", "dream_1", "2026-01-02T00:00:00+00:00", 0)
    state = await db.get_dream_state("a1")
    assert state["last_run_id"] == "dream_1"
    assert state["last_consolidated_at"] == "2026-01-02T00:00:00+00:00"


async def test_dream_run_whitelist(db):
    await db.ensure_agent("a1")
    await db.create_dream_run("a1", "dream_1", "manual", "2026-01-01T00:00:00+00:00")
    await db.update_dream_run("a1", "dream_1", status="completed", duration_ms=42)
    runs = await db.get_dream_runs("a1")
    assert runs[0]["status"] == "completed"
    assert runs[0]["duration_ms"] == 42
    with pytest.raises(ValidationError):
        await db.update_dream_run(
            "a1",
            "dream_1",
            **{"status = 'x'; DROP TABLE facts; --": "completed"},
        )


async def test_usage_stats(db):
    await db.ensure_agent("a1")
    await db.log_llm_call(
        agent_id="a1",
        provider="fake",
        model="fake-model",
        purpose="test",
        prompt_tokens=100,
        completion_tokens=50,
        latency_ms=10,
    )
    stats = await db.get_usage_stats("a1")
    assert stats["total_calls"] == 1
    assert stats["total_tokens"] == 150
