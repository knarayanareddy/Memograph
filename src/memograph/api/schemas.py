"""Request and response schemas for the REST API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(_StrictModel):
    status: str = "ok"
    version: str = ""
    auth_model: str = "single-user-shared-key"


class RememberRequest(_StrictModel):
    topic_id: str = Field(min_length=1, max_length=50)
    content: str = Field(min_length=1, max_length=1000)
    source: str = Field(default="api", min_length=1, max_length=200)
    confidence: str | None = Field(default=None, max_length=20)
    tags: list[str] = Field(default_factory=list, max_length=20)
    verification_hint: str | None = Field(default=None, max_length=200)


class WriteResultResponse(_StrictModel):
    success: bool
    skipped: bool = False
    skip_reason: str | None = None
    error: str | None = None
    fact_id: str | None = None


class ForgetRequest(_StrictModel):
    topic_id: str = Field(min_length=1, max_length=50)
    fact_id: str | None = Field(default=None, max_length=100)


class UpdateRequest(_StrictModel):
    topic_id: str = Field(min_length=1, max_length=50)
    fact_id: str = Field(min_length=1, max_length=100)
    new_content: str | None = Field(default=None, max_length=1000)
    new_confidence: str | None = Field(default=None, max_length=20)
    verification_source: str | None = Field(default=None, max_length=200)


class ContextRequest(_StrictModel):
    query: str = Field(min_length=1, max_length=1000)
    max_topics: int = Field(default=3, ge=1, le=20)
    token_budget: int | None = Field(default=None, ge=1, le=100_000)


class ContextResponse(_StrictModel):
    text: str
    total_tokens: int
    index_tokens: int
    topic_tokens: int
    topics_loaded: list[str]
    pressure_level: str
    available_input: int


class DreamRequest(_StrictModel):
    force: bool = False


class GrepRequest(_StrictModel):
    pattern: str = Field(min_length=1, max_length=200)
    max_results: int = Field(default=20, ge=1, le=100)
    regex: bool = False


class IndexResponse(_StrictModel):
    index: str


class PruneResponse(_StrictModel):
    pointers_removed: int


class EventMessage(_StrictModel):
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: str
