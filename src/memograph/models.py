"""Canonical data models.

This is the only model definition in the project.  SQLite is the source of
truth; ``MEMORY.md`` and ``topics/*.md`` are generated, read-friendly views.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .config import ConfidenceLevel
from .errors import IndexLimitError
from .validation import (
    stable_id,
    validate_fact_content,
    validate_summary,
    validate_topic_id,
)

MAX_POINTER_CHARS = 150
MAX_SUMMARY_CHARS = 80
MAX_FACT_CHARS = 1000


def _utcnow() -> datetime:
    return datetime.now(UTC)


class IndexPointer(BaseModel):
    """One line in the always-loaded ``MEMORY.md`` index."""

    model_config = ConfigDict(extra="forbid")

    topic_id: str
    topic_file_path: str
    summary: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    last_updated: datetime = Field(default_factory=_utcnow)
    last_accessed: datetime | None = None
    access_count: int = Field(default=0, ge=0)
    is_stale: bool = False
    verification_source: str | None = None

    @field_validator("topic_id")
    @classmethod
    def _topic_id(cls, value: str) -> str:
        return validate_topic_id(value)

    @field_validator("summary")
    @classmethod
    def _summary(cls, value: str) -> str:
        return validate_summary(value, MAX_SUMMARY_CHARS)

    @field_validator("topic_file_path")
    @classmethod
    def _path(cls, value: str) -> str:
        # Relative, POSIX-style paths only.  The manager resolves and contains it.
        if not value or value.startswith("/") or "\\" in value or ".." in value.split("/"):
            raise ValueError("topic_file_path must be a safe relative path")
        return value

    def build_pointer_line(self, max_chars: int = MAX_POINTER_CHARS) -> str:
        """Build a deterministic line that never exceeds ``max_chars``.

        Truncation is applied to the summary and then the path, never to the
        date/confidence suffix, so the line remains parseable.
        """
        stale = " [stale]" if self.is_stale else ""
        prefix = f"[{self.topic_id}]{stale} "
        date = self.last_updated.strftime("%Y-%m-%d")
        conf = f"{self.confidence:.1f}"
        summary = self.summary
        path = self.topic_file_path
        suffix = f" -> {path} ({date}, conf={conf})"
        line = f"{prefix}{summary}{suffix}"
        if len(line) <= max_chars:
            return line

        overflow = len(line) - max_chars
        if len(summary) > overflow + 1:
            summary = summary[: max(1, len(summary) - overflow - 1)] + "…"
            line = f"{prefix}{summary}{suffix}"
        if len(line) > max_chars:
            overflow = len(line) - max_chars
            if len(path) > overflow + 1:
                path = path[: max(1, len(path) - overflow - 1)] + "…"
                suffix = f" -> {path} ({date}, conf={conf})"
                line = f"{prefix}{summary}{suffix}"
        return line[:max_chars]

    @property
    def pointer_line(self) -> str:
        # Computed, not cached: stale/confidence changes always take effect.
        return self.build_pointer_line()


class MemoryIndex(BaseModel):
    """The generated ``MEMORY.md`` representation with enforced hard limits."""

    model_config = ConfigDict(extra="forbid")

    MAX_LINES: ClassVar[int] = 200
    MAX_BYTES: ClassVar[int] = 25_600
    MAX_POINTER_CHARS: ClassVar[int] = MAX_POINTER_CHARS

    agent_id: str = "default"
    pointers: list[IndexPointer] = Field(default_factory=list)
    version: int = 1
    last_consolidated: datetime | None = None

    def get_pointer(self, topic_id: str) -> IndexPointer | None:
        return next((p for p in self.pointers if p.topic_id == topic_id), None)

    def upsert_pointer(self, pointer: IndexPointer) -> None:
        """Atomically validate and replace a pointer."""
        candidates = [p for p in self.pointers if p.topic_id != pointer.topic_id]
        candidates.append(pointer)
        candidate = self.model_copy(update={"pointers": candidates})
        candidate.validate_limits()
        self.pointers = candidates

    def remove_pointer(self, topic_id: str) -> bool:
        before = len(self.pointers)
        self.pointers = [p for p in self.pointers if p.topic_id != topic_id]
        return len(self.pointers) < before

    def sorted_by_confidence(self) -> list[IndexPointer]:
        return sorted(self.pointers, key=lambda p: (-p.confidence, p.topic_id))

    def validate_limits(self) -> None:
        markdown = self.to_markdown()
        lines = markdown.splitlines()
        byte_size = len(markdown.encode("utf-8"))
        if len(lines) > self.MAX_LINES:
            raise IndexLimitError(f"Index has {len(lines)} lines; limit is {self.MAX_LINES}")
        if byte_size > self.MAX_BYTES:
            raise IndexLimitError(f"Index has {byte_size} bytes; limit is {self.MAX_BYTES}")
        for pointer in self.pointers:
            if len(pointer.pointer_line) > self.MAX_POINTER_CHARS:
                raise IndexLimitError(
                    f"Pointer for {pointer.topic_id} exceeds {self.MAX_POINTER_CHARS} characters"
                )

    def to_markdown(self) -> str:
        when = (
            self.last_consolidated.strftime("%Y-%m-%d %H:%M UTC")
            if self.last_consolidated
            else "Never"
        )
        lines = [
            f"# Memograph Index - Agent: {self.agent_id}",
            f"Last consolidated: {when}",
            f"Pointers: {len(self.pointers)}",
            "---",
        ]
        lines.extend(p.pointer_line for p in self.sorted_by_confidence())
        return "\n".join(lines) + "\n"

    def get_context_injection(self) -> str:
        return self.to_markdown()


class MemoryFact(BaseModel):
    """A single atomic, skeptically-framed fact."""

    model_config = ConfigDict(extra="forbid")

    fact_id: str = Field(
        default_factory=lambda: stable_id(uuid.uuid4().hex, prefix="fact", length=8)
    )
    content: str
    confidence: ConfidenceLevel = ConfidenceLevel.OBSERVED
    source: str
    verification_hint: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    last_verified: datetime | None = None
    contradicts_ids: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)

    @field_validator("content")
    @classmethod
    def _content(cls, value: str) -> str:
        return validate_fact_content(value, MAX_FACT_CHARS)

    @field_validator("source")
    @classmethod
    def _source(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("source must be non-empty")
        return value.strip()

    def to_markdown_line(self) -> str:
        mark = {
            ConfidenceLevel.VERIFIED: "[verified]",
            ConfidenceLevel.OBSERVED: "[observed]",
            ConfidenceLevel.INFERRED: "[inferred]",
            ConfidenceLevel.STALE: "[stale]",
        }[self.confidence]
        verified = self.last_verified.strftime("%Y-%m-%d") if self.last_verified else "never"
        extra = ""
        if self.contradicts_ids:
            extra = f" | contradicts: {', '.join(self.contradicts_ids)}"
        return (
            f"- {mark} `{self.fact_id}` {self.content}\n"
            f"  source: {self.source} | verified: {verified}{extra}"
        )


class TopicFile(BaseModel):
    """Layer-2 topic file; JSON is machine-readable, Markdown is generated."""

    model_config = ConfigDict(extra="forbid")

    topic_id: str
    topic_name: str
    agent_id: str = "default"
    facts: list[MemoryFact] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    file_path: str = ""
    created_at: datetime = Field(default_factory=_utcnow)
    last_modified: datetime = Field(default_factory=_utcnow)

    @field_validator("topic_id")
    @classmethod
    def _topic_id(cls, value: str) -> str:
        return validate_topic_id(value)

    @property
    def avg_confidence(self) -> float:
        scores = {
            ConfidenceLevel.VERIFIED: 1.0,
            ConfidenceLevel.OBSERVED: 0.6,
            ConfidenceLevel.INFERRED: 0.4,
            ConfidenceLevel.STALE: 0.1,
        }
        if not self.facts:
            return 0.5
        return sum(scores[f.confidence] for f in self.facts) / len(self.facts)

    def get_fact(self, fact_id: str) -> MemoryFact | None:
        return next((f for f in self.facts if f.fact_id == fact_id), None)

    def to_summary(self, max_chars: int = MAX_SUMMARY_CHARS) -> str:
        tags = f" [{', '.join(self.tags[:2])}]" if self.tags else ""
        return validate_summary(f"{len(self.facts)} facts about {self.topic_name}{tags}", max_chars)

    def to_markdown(self) -> str:
        verified = sum(f.confidence == ConfidenceLevel.VERIFIED for f in self.facts)
        stale = sum(f.confidence == ConfidenceLevel.STALE for f in self.facts)
        lines = [
            f"# Topic: {self.topic_name}",
            f"ID: `{self.topic_id}` | Agent: {self.agent_id}",
            f"Tags: {', '.join(self.tags) or 'none'}",
            f"Facts: {len(self.facts)} (verified={verified}, stale={stale})",
            f"Last modified: {self.last_modified.strftime('%Y-%m-%d %H:%M UTC')}",
            "---",
            "## Facts",
        ]
        if not self.facts:
            lines.append("*No facts stored yet.*")
        else:
            for fact in self.facts:
                lines.append(fact.to_markdown_line())
        return "\n".join(lines) + "\n"

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, payload: str) -> TopicFile:
        return cls.model_validate_json(payload)
