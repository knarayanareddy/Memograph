"""Request and response schemas for the REST API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(_StrictModel):
    status: str = "ok"
    version: str = ""


class RememberRequest(_StrictModel):
    topic_id: str
    content: str
    source: str = "api"
    confidence: str | None = None
    tags: list[str] = Field(default_factory=list)
    verification_hint: str | None = None


class WriteResultResponse(_StrictModel):
    success: bool
    skipped: bool = False
    skip_reason: str | None = None
    error: str | None = None
    fact_id: str | None = None


class ForgetRequest(_StrictModel):
    topic_id: str
    fact_id: str | None = None


class UpdateRequest(_StrictModel):
    topic_id: str
    fact_id: str
    new_content: str | None = None
    new_confidence: str | None = None
    verification_source: str | None = None


class ContextRequest(_StrictModel):
    query: str
    max_topics: int = Field(default=3, ge=1, le=20)
    token_budget: int | None = Field(default=None, ge=1)


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
    pattern: str
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
