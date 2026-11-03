from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from memograph.config import ConfidenceLevel
from memograph.errors import IndexLimitError
from memograph.models import IndexPointer, MemoryFact, MemoryIndex, TopicFile


def make_pointer(index: int, long_path: bool = False) -> IndexPointer:
    path = "topics/" + ("p" * 300) + f"_{index}.json" if long_path else f"topics/topic_{index}.json"
    return IndexPointer(
        topic_id=f"topic_{index}",
        topic_file_path=path,
        summary=f"summary {index}",
        confidence=0.5,
    )


def test_pointer_line_is_bounded_and_not_cached():
    pointer = IndexPointer(
        topic_id="a" * 50,
        topic_file_path="topics/" + ("p" * 300) + ".json",
        summary="s" * 80,
        confidence=0.5,
    )
    line = pointer.pointer_line
    assert len(line) <= 150
    stale = pointer.model_copy(update={"is_stale": True})
    assert "[stale]" in stale.pointer_line
    assert stale.pointer_line != line


def test_index_line_and_byte_limits():
    index = MemoryIndex(agent_id="default")
    for item in range(196):  # 4 header lines + 196 pointers = 200 lines
        index.upsert_pointer(make_pointer(item))
    assert len(index.to_markdown().splitlines()) == 200
    with pytest.raises(IndexLimitError):
        index.upsert_pointer(make_pointer(196))

    # 190 pointers stay under the 200-line cap but exceed the 25,600-byte cap
    # because each computed pointer line is still close to 150 characters.
    oversized = MemoryIndex(
        agent_id="default",
        pointers=[make_pointer(item, long_path=True) for item in range(190)],
    )
    with pytest.raises(IndexLimitError):
        oversized.validate_limits()


def test_index_helpers():
    index = MemoryIndex()
    first = make_pointer(1)
    index.upsert_pointer(first)
    index.upsert_pointer(first.model_copy(update={"confidence": 0.9}))
    assert len(index.pointers) == 1
    assert index.get_pointer("topic_1").confidence == 0.9
    assert index.remove_pointer("topic_1") is True
    assert index.remove_pointer("topic_1") is False


def test_topic_models():
    facts = [
        MemoryFact(content="verified fact", confidence=ConfidenceLevel.VERIFIED, source="s"),
        MemoryFact(content="observed fact", confidence=ConfidenceLevel.OBSERVED, source="s"),
    ]
    topic = TopicFile(topic_id="project", topic_name="Project", facts=facts)
    assert topic.avg_confidence == pytest.approx(0.8)
    assert topic.get_fact(facts[0].fact_id) is facts[0]
    assert "Topic: Project" in topic.to_markdown()
    assert len(topic.to_summary()) <= 80
    restored = TopicFile.from_json(topic.to_json())
    assert restored.facts[0].fact_id == facts[0].fact_id
    assert restored.facts[0].confidence == ConfidenceLevel.VERIFIED


def test_invalid_models():
    with pytest.raises(PydanticValidationError):
        MemoryFact(content="", source="s")
    with pytest.raises(PydanticValidationError):
        MemoryFact(content="x" * 1001, source="s")
    with pytest.raises(PydanticValidationError):
        TopicFile(topic_id="../evil", topic_name="Evil")
    with pytest.raises(PydanticValidationError):
        IndexPointer(
            topic_id="ok",
            topic_file_path="../escape.json",
            summary="s",
            confidence=0.5,
        )
