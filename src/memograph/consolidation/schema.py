"""Strict schema for LLM-produced consolidation operations.

LLM output is untrusted data.  Only these four actions are possible, every
field is validated, and no arbitrary keyword arguments are ever passed to the
memory manager.
"""

from __future__ import annotations

import json
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from ..config import ConfidenceLevel
from ..errors import ConsolidationParseError
from ..validation import validate_fact_content, validate_topic_id

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


class _OperationBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic_id: str

    @field_validator("topic_id")
    @classmethod
    def _topic_id(cls, value: str) -> str:
        return validate_topic_id(value)


class MergeOperation(_OperationBase):
    action: Literal["merge"] = "merge"
    fact_ids: list[str] = Field(min_length=1, max_length=20)
    merged_content: str

    @field_validator("merged_content")
    @classmethod
    def _content(cls, value: str) -> str:
        return validate_fact_content(value)


class ResolveOperation(_OperationBase):
    action: Literal["resolve_contradiction"] = "resolve_contradiction"
    fact_ids: list[str] = Field(min_length=1, max_length=20)
    resolution: str

    @field_validator("resolution")
    @classmethod
    def _content(cls, value: str) -> str:
        return validate_fact_content(value)


class PromoteOperation(_OperationBase):
    action: Literal["promote"] = "promote"
    fact_id: str = Field(min_length=1)
    new_confidence: ConfidenceLevel
    verification_source: str | None = None

    @model_validator(mode="after")
    def _verified_requires_source(self) -> PromoteOperation:
        if self.new_confidence == ConfidenceLevel.VERIFIED and not self.verification_source:
            raise ValueError("verification_source is required to promote to verified")
        return self


class CreateOperation(_OperationBase):
    action: Literal["create"] = "create"
    content: str
    source: str = Field(min_length=1, max_length=200)
    confidence: ConfidenceLevel = ConfidenceLevel.INFERRED
    verification_source: str | None = None

    @field_validator("content")
    @classmethod
    def _content(cls, value: str) -> str:
        return validate_fact_content(value)

    @model_validator(mode="after")
    def _verified_requires_source(self) -> CreateOperation:
        if self.confidence == ConfidenceLevel.VERIFIED and not self.verification_source:
            raise ValueError("verification_source is required for a verified fact")
        return self


ConsolidationOperation = Annotated[
    MergeOperation | ResolveOperation | PromoteOperation | CreateOperation,
    Field(discriminator="action"),
]


class ConsolidationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operations: list[ConsolidationOperation] = Field(default_factory=list, max_length=50)
    no_changes_needed: bool = False


def _json_candidates(text: str) -> list[str]:
    stripped = text.strip()
    candidates = [stripped]
    candidates.extend(match.group(1).strip() for match in _FENCE_RE.finditer(text))
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])
    return [candidate for candidate in candidates if candidate]


def parse_consolidation_plan(text: str) -> ConsolidationPlan:
    """Parse and validate LLM output into a :class:`ConsolidationPlan`."""
    if not isinstance(text, str) or not text.strip():
        raise ConsolidationParseError("Empty consolidation output")
    last_error: Exception | None = None
    for candidate in _json_candidates(text):
        try:
            data = json.loads(candidate)
            if isinstance(data, list):
                data = {"operations": data}
            if not isinstance(data, dict):
                raise ValueError("Consolidation output must be a JSON object")
            return ConsolidationPlan.model_validate(data)
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            last_error = exc
            continue
    raise ConsolidationParseError(f"Could not parse consolidation output: {last_error}")
