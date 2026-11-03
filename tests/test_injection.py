from __future__ import annotations

import pytest

from memograph.config import ConfidenceLevel
from memograph.errors import TokenBudgetError
from memograph.injection import TokenBudgetManager, get_context_spec
from memograph.models import IndexPointer, MemoryFact, MemoryIndex, TopicFile


def fixtures():
    pointer = IndexPointer(
        topic_id="project",
        topic_file_path="topics/project.json",
        summary="project facts",
        confidence=0.8,
    )
    index = MemoryIndex(pointers=[pointer])
    topic = TopicFile(
        topic_id="project",
        topic_name="Project",
        facts=[
            MemoryFact(
                content="Uses FastAPI and SQLite",
                confidence=ConfidenceLevel.OBSERVED,
                source="readme",
            )
        ],
    )
    return index, [topic]


def test_conservative_context_spec():
    default = get_context_spec("some-unknown-model")
    assert default.context_tokens == 8_192
    assert default.source == "conservative-default"
    custom = get_context_spec(custom_context_size=16_384)
    assert custom.context_tokens == 16_384
    assert custom.safe_output_tokens == 4_096


def test_build_context():
    index, topics = fixtures()
    builder = TokenBudgetManager()
    built = builder.build(index, topics, query="What framework?", skeptical=True)
    assert "hints, not ground truth" in built.text
    assert "Uses FastAPI and SQLite" in built.text
    assert built.topics_loaded == ["project"]
    assert built.total_tokens >= built.index_tokens
    assert built.pressure_level == "low"
    assert built.to_dict()["topics_loaded"] == ["project"]


def test_small_budget_raises():
    index, topics = fixtures()
    builder = TokenBudgetManager(custom_context_size=10)
    with pytest.raises(TokenBudgetError):
        builder.build(index, topics, skeptical=True)


def test_count_truncate_and_pressure():
    builder = TokenBudgetManager()
    assert builder.count("") == 0
    assert builder.count("abcd") == 1
    truncated = builder.truncate("x" * 10_000, 10)
    assert builder.count(truncated) <= 10
    assert truncated.endswith("[truncated]")
    assert builder.pressure_level(6_000) == "critical"
