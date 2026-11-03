"""AutoGen AgentChat message integration."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, TypeAlias

try:
    from autogen_agentchat.messages import BaseMessage as AutoGenBaseMessage
    from autogen_agentchat.messages import MultiModalMessage, TextMessage
except ImportError as exc:  # pragma: no cover - depends on optional extra
    raise RuntimeError("Install the 'memograph[integrations]' extra to use AutoGenMemory.") from exc

from .. import LLMProvider, MemoGraph, MemoGraphConfig
from ..injection import BuiltContext
from ..validation import stable_id
from .common import clip_text

AutoGenMessage: TypeAlias = AutoGenBaseMessage | TextMessage | MultiModalMessage | str


def _message_parts(message: AutoGenMessage) -> tuple[str, str, str]:
    if isinstance(message, str):
        return "", "unknown", message
    message_id = str(getattr(message, "id", "") or "")
    sender = str(getattr(message, "source", "unknown") or "unknown")
    content = getattr(message, "content", "")
    if isinstance(content, list):
        content = " ".join(str(item) for item in content)
    return message_id, sender, clip_text(str(content), 900)


class AutoGenMemory:
    """Async AutoGen memory adapter using Memograph as canonical storage."""

    def __init__(self, manager: MemoGraph, *, source: str = "autogen") -> None:
        self.manager = manager
        self.source = source

    @classmethod
    def from_path(
        cls,
        base_path: str | Path = ".memograph",
        *,
        agent_id: str = "default",
        source: str = "autogen",
    ) -> AutoGenMemory:
        manager = MemoGraph(
            config=MemoGraphConfig(
                base_path=Path(base_path),
                agent_id=agent_id,
                llm_provider=LLMProvider.NONE,
                auto_consolidate=False,
            )
        )
        return cls(manager, source=source)

    async def initialize(self) -> None:
        await self.manager.initialize()

    async def close(self) -> None:
        await self.manager.close()

    async def remember_message(self, message: AutoGenMessage) -> str:
        """Store one AutoGen message and return its generated fact ID."""
        message_id, sender, content = _message_parts(message)
        topic_id = stable_id(
            f"autogen:{message_id}:{sender}:{content}", prefix="autogen", length=12
        )
        result = await self.manager.remember(topic_id, f"{sender}: {content}", self.source)
        return result.fact.fact_id if result.fact else ""

    async def remember_messages(self, messages: Sequence[AutoGenMessage]) -> list[str]:
        """Store a sequence of AutoGen messages."""
        return [await self.remember_message(message) for message in messages]

    async def context_for(
        self,
        query: str,
        max_topics: int = 3,
        token_budget: int | None = None,
    ) -> BuiltContext:
        """Build a bandwidth-aware context window from stored memories."""
        return await self.manager.build_context(query, max_topics, token_budget)

    async def __aenter__(self) -> AutoGenMemory:
        await self.initialize()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
