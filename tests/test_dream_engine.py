from __future__ import annotations

import json

import pytest

from memograph.config import ConfidenceLevel
from memograph.errors import ConsolidationParseError


async def test_successful_dream_creates_fact(manager_with_fake_llm, fake_llm):
    fake_llm.responses.append(
        json.dumps(
            {
                "operations": [
                    {
                        "action": "create",
                        "topic_id": "dream_topic",
                        "content": "A consolidated fact",
                        "source": "transcript",
                        "confidence": "inferred",
                    }
                ]
            }
        )
    )
    result = await manager_with_fake_llm.dream_now(force=True)
    assert result.status == "completed"
    assert result.operations_applied == 1
    assert result.facts_created == 1
    topic = await manager_with_fake_llm.get_topic("dream_topic")
    assert topic is not None
    assert topic.facts[0].content == "A consolidated fact"
    assert topic.facts[0].confidence == ConfidenceLevel.INFERRED
    status = await manager_with_fake_llm.status()
    assert status["last_consolidated"] is not None


async def test_failed_dream_does_not_advance_state(manager_with_fake_llm, fake_llm):
    fake_llm.responses.append('{"operations": []}')
    first = await manager_with_fake_llm.dream_now(force=True)
    assert first.status == "completed"
    first_timestamp = (await manager_with_fake_llm.status())["last_consolidated"]

    fake_llm.responses.append("definitely not json")
    with pytest.raises(ConsolidationParseError):
        await manager_with_fake_llm.dream_now(force=True)
    second_timestamp = (await manager_with_fake_llm.status())["last_consolidated"]
    assert second_timestamp == first_timestamp

    runs = await manager_with_fake_llm.db.get_dream_runs(manager_with_fake_llm.agent_id, limit=2)
    assert any(run["status"] == "failed" for run in runs)


async def test_merge_and_promote_operations(manager_with_fake_llm, fake_llm):
    first = await manager_with_fake_llm.remember("project", "fact one", source="s")
    second = await manager_with_fake_llm.remember("project", "fact two", source="s")
    fact_ids = [first.fact.fact_id, second.fact.fact_id]
    fake_llm.responses.append(
        json.dumps(
            {
                "operations": [
                    {
                        "action": "merge",
                        "topic_id": "project",
                        "fact_ids": fact_ids,
                        "merged_content": "one merged fact",
                    }
                ]
            }
        )
    )
    merged = await manager_with_fake_llm.dream_now(force=True)
    assert merged.facts_merged == 1
    topic = await manager_with_fake_llm.get_topic("project")
    assert len(topic.facts) == 1
    assert topic.facts[0].content == "one merged fact"

    fake_llm.responses.append(
        json.dumps(
            {
                "operations": [
                    {
                        "action": "promote",
                        "topic_id": "project",
                        "fact_id": topic.facts[0].fact_id,
                        "new_confidence": "observed",
                    }
                ]
            }
        )
    )
    promoted = await manager_with_fake_llm.dream_now(force=True)
    assert promoted.confidence_promoted == 1
    topic = await manager_with_fake_llm.get_topic("project")
    assert topic.facts[0].content == "one merged fact"
    assert topic.facts[0].confidence == ConfidenceLevel.OBSERVED


async def test_injected_topic_id_is_rejected(manager_with_fake_llm, fake_llm):
    fake_llm.responses.append(
        json.dumps(
            {
                "operations": [
                    {
                        "action": "create",
                        "topic_id": "../evil",
                        "content": "escape",
                        "source": "transcript",
                    }
                ]
            }
        )
    )
    with pytest.raises(ConsolidationParseError):
        await manager_with_fake_llm.dream_now(force=True)
    assert not (manager_with_fake_llm.base_path.parent / "evil.json").exists()
    assert (await manager_with_fake_llm.status())["last_consolidated"] is None
