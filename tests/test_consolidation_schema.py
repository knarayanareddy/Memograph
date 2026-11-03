from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from memograph.consolidation.schema import (
    ConsolidationPlan,
    CreateOperation,
    MergeOperation,
    parse_consolidation_plan,
)
from memograph.errors import ConsolidationParseError


def test_parse_raw_and_fenced_json():
    raw = '{"operations": [{"action": "merge", "topic_id": "project", "fact_ids": ["f1"], "merged_content": "One fact"}]}'
    plan = parse_consolidation_plan(raw)
    assert isinstance(plan.operations[0], MergeOperation)
    fenced = "```json\n" + raw + "\n```"
    assert isinstance(parse_consolidation_plan(fenced).operations[0], MergeOperation)
    assert parse_consolidation_plan(
        '{"operations": [], "no_changes_needed": true}'
    ).no_changes_needed


def test_list_input_is_wrapped():
    plan = parse_consolidation_plan(
        '[{"action": "create", "topic_id": "project", "content": "A fact", "source": "s"}]'
    )
    assert isinstance(plan.operations[0], CreateOperation)


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        '{"operations": [{"action": "delete_everything", "topic_id": "project"}]}',
        '{"operations": [{"action": "create", "topic_id": "../evil", "content": "x", "source": "s"}]}',
        '{"operations": [{"action": "promote", "topic_id": "project", "fact_id": "f1", "new_confidence": "verified"}]}',
        '{"operations": [{"action": "create", "topic_id": "project", "content": "x", "source": "s", "confidence": "verified"}]}',
        '{"operations": [], "unexpected": true}',
    ],
)
def test_invalid_plans_are_rejected(payload):
    with pytest.raises(ConsolidationParseError):
        parse_consolidation_plan(payload)


def test_verified_promotion_requires_source():
    payload = (
        '{"operations": [{"action": "promote", "topic_id": "project", '
        '"fact_id": "f1", "new_confidence": "verified", '
        '"verification_source": "src/main.py"}]}'
    )
    plan = parse_consolidation_plan(payload)
    assert plan.operations[0].verification_source == "src/main.py"


def test_plan_rejects_too_many_operations():
    operations = [
        {
            "action": "create",
            "topic_id": "project",
            "content": f"fact {item}",
            "source": "s",
        }
        for item in range(51)
    ]
    with pytest.raises(PydanticValidationError):
        ConsolidationPlan.model_validate({"operations": operations})
