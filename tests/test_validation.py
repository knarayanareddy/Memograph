from __future__ import annotations

import hashlib

import pytest

from memograph.errors import ValidationError
from memograph.validation import (
    normalize_topic_id,
    safe_relative_path,
    safe_topic_path,
    stable_id,
    validate_fact_content,
    validate_summary,
    validate_topic_id,
)


def test_topic_ids():
    assert validate_topic_id("project_stack") == "project_stack"
    assert validate_topic_id("a") == "a"
    for invalid in ["", "1topic", "Topic", "topic-with-dash", "../evil", "x" * 51]:
        with pytest.raises(ValidationError):
            validate_topic_id(invalid)


def test_path_containment(tmp_path):
    base = tmp_path / "store"
    assert safe_relative_path(base, "topics/ok.json").is_relative_to(base.resolve())
    with pytest.raises(ValidationError):
        safe_relative_path(base, "../evil.json")
    with pytest.raises(ValidationError):
        safe_relative_path(base, "/etc/passwd")
    assert safe_topic_path(base, "ok_topic", ".json").name == "ok_topic.json"
    with pytest.raises(ValidationError):
        safe_topic_path(base, "../evil", ".json")
    with pytest.raises(ValidationError):
        safe_topic_path(base, "ok_topic", ".txt")


def test_content_and_summary():
    assert validate_fact_content("A fact") == "A fact"
    with pytest.raises(ValidationError):
        validate_fact_content("")
    with pytest.raises(ValidationError):
        validate_fact_content("x" * 1001)
    with pytest.raises(ValidationError):
        validate_fact_content("bad\x00value")
    assert validate_summary("  a   summary  ") == "a summary"
    with pytest.raises(ValidationError):
        validate_summary("x" * 81)


def test_normalize_and_stable_ids():
    assert normalize_topic_id("Project Architecture") == "project_architecture"
    assert normalize_topic_id("123 test") == "topic_123_test"
    expected = hashlib.sha256(b"payload").hexdigest()[:8]
    assert stable_id("payload", prefix="topic", length=8) == f"topic_{expected}"
    assert stable_id("payload") == stable_id("payload")
    assert stable_id("payload") != stable_id("other")
