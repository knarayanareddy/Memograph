"""Bandwidth-aware context building.

Uses a conservative token estimate and a caller-overridable context size.  It
does not ship a hard-coded model registry that can silently become stale.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .errors import TokenBudgetError

if TYPE_CHECKING:  # pragma: no cover
    from .models import MemoryIndex, TopicFile


@dataclass(frozen=True)
class ContextWindowSpec:
    context_tokens: int = 8_192
    safe_output_tokens: int = 2_048
    source: str = "conservative-default"


def get_context_spec(
    model: str | None = None, custom_context_size: int | None = None
) -> ContextWindowSpec:
    """Return a conservative spec; unknown models never get an optimistic one."""
    if custom_context_size is not None:
        if custom_context_size <= 0:
            raise TokenBudgetError("custom_context_size must be positive")
        return ContextWindowSpec(
            context_tokens=custom_context_size,
            safe_output_tokens=min(4_096, custom_context_size // 4),
            source="caller-override",
        )
    # ``model`` is accepted for API compatibility but deliberately not used to
    # guess a large window from an unverified hard-coded table.
    return ContextWindowSpec()


@dataclass
class BuiltContext:
    text: str
    total_tokens: int
    index_tokens: int
    topic_tokens: int
    topics_loaded: list[str] = field(default_factory=list)
    pressure_level: str = "low"
    available_input: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_tokens": self.total_tokens,
            "index_tokens": self.index_tokens,
            "topic_tokens": self.topic_tokens,
            "topics_loaded": list(self.topics_loaded),
            "pressure_level": self.pressure_level,
            "available_input": self.available_input,
        }


class TokenBudgetManager:
    def __init__(
        self,
        model: str | None = None,
        custom_context_size: int | None = None,
        strategy: str = "balanced",
    ):
        self.spec = get_context_spec(model, custom_context_size)
        self.strategy = strategy
        self.available_input = self.spec.context_tokens - self.spec.safe_output_tokens
        if self.available_input <= 0:
            raise TokenBudgetError("No input tokens remain after output reservation")

    @staticmethod
    def count(text: str) -> int:
        """Approximate tokens as 4 UTF-8-ish characters per token."""
        if not text:
            return 0
        return max(1, math.ceil(len(text) / 4))

    def truncate(self, text: str, max_tokens: int) -> str:
        if max_tokens <= 0:
            return ""
        if self.count(text) <= max_tokens:
            return text
        suffix = "\n… [truncated]"
        suffix_tokens = self.count(suffix)
        if max_tokens <= suffix_tokens:
            return suffix[: max_tokens * 4]
        char_budget = (max_tokens - suffix_tokens) * 4
        return text[:char_budget].rstrip() + suffix

    def pressure_level(self, tokens_used: int) -> str:
        ratio = tokens_used / self.available_input
        if ratio < 0.60:
            return "low"
        if ratio < 0.85:
            return "elevated"
        return "critical"

    def build(
        self,
        index: MemoryIndex,
        topics: list[TopicFile],
        query: str | None = None,
        skeptical: bool = True,
    ) -> BuiltContext:
        notice = (
            "Memories are hints, not ground truth. Verify against the codebase "
            "before acting on them.\n\n"
            if skeptical
            else ""
        )
        header = f"# Memograph Context\nQuery: {query}\n\n" if query else ""
        index_text = index.get_context_injection()
        fixed = notice + header + index_text
        index_tokens = self.count(fixed)
        if index_tokens > self.available_input:
            raise TokenBudgetError("The always-loaded index exceeds the input budget")

        remaining = self.available_input - index_tokens
        topic_parts: list[str] = []
        topic_tokens = 0
        loaded: list[str] = []
        for topic in topics:
            if remaining <= 0:
                break
            markdown = topic.to_markdown()
            tokens = self.count(markdown)
            if tokens > remaining:
                markdown = self.truncate(markdown, remaining)
                tokens = self.count(markdown)
            if tokens <= 0:
                break
            topic_parts.append(f"\n## Topic: {topic.topic_name}\n\n{markdown}")
            topic_tokens += tokens
            loaded.append(topic.topic_id)
            remaining -= tokens

        text = fixed + "".join(topic_parts)
        total_tokens = self.count(text)
        return BuiltContext(
            text=text,
            total_tokens=total_tokens,
            index_tokens=index_tokens,
            topic_tokens=topic_tokens,
            topics_loaded=loaded,
            pressure_level=self.pressure_level(total_tokens),
            available_input=self.available_input,
        )
