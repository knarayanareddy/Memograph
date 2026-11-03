"""LangChain chat-history integration backed by Memograph."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

try:
    from langchain_core.chat_history import BaseChatMessageHistory
    from langchain_core.messages import BaseMessage, message_to_dict, messages_from_dict
except ImportError as exc:  # pragma: no cover - depends on optional extra
    raise RuntimeError(
        "Install the 'memograph[integrations]' extra to use LangChainMemory."
    ) from exc

from .. import LLMProvider, MemoGraph, MemoGraphConfig
from ..validation import stable_id
from .common import AsyncBridge, clip_text


def _compact_payload(payload: dict[str, Any]) -> str:
    data = dict(payload.get("data") or {})
    for key in (
        "additional_kwargs",
        "response_metadata",
        "usage_metadata",
        "tool_calls",
        "invalid_tool_calls",
    ):
        data.pop(key, None)
    if "content" in data:
        data["content"] = clip_text(str(data["content"]), 600)
    compact = {"type": str(payload.get("type") or "human"), "data": data}
    return json.dumps(compact, ensure_ascii=False, separators=(",", ":"))[:1000]


class LangChainMemory(BaseChatMessageHistory):
    """A ``BaseChatMessageHistory`` that persists messages as Memograph facts.

    Each session is one topic. Messages are serialized with LangChain's own
    ``message_to_dict`` format and reconstructed with ``messages_from_dict``.
    """

    def __init__(
        self,
        base_path: str | Path = ".memograph",
        *,
        agent_id: str = "default",
        session_id: str = "default",
        source: str = "langchain",
        manager: MemoGraph | None = None,
    ) -> None:
        self._bridge = AsyncBridge()
        self._manager = manager or MemoGraph(
            config=MemoGraphConfig(
                base_path=Path(base_path),
                agent_id=agent_id,
                llm_provider=LLMProvider.NONE,
                auto_consolidate=False,
            )
        )
        self._bridge.run(self._manager.initialize())
        self._topic_id = stable_id(
            f"langchain:{agent_id}:{session_id}", prefix="langchain", length=12
        )
        self._source = source
        self._closed = False

    @property
    def messages(self) -> list[BaseMessage]:
        """All stored LangChain messages for this session."""
        return self._bridge.run(self._aget_messages())

    @messages.setter
    def messages(self, value: list[BaseMessage]) -> None:
        self.clear()
        self.add_messages(value)

    async def _aget_messages(self) -> list[BaseMessage]:
        topic = await self._manager.get_topic(self._topic_id)
        if topic is None:
            return []
        payloads: list[dict[str, Any]] = []
        for fact in topic.facts:
            try:
                payloads.append(json.loads(fact.content))
            except json.JSONDecodeError:  # pragma: no cover - corrupt legacy row
                continue
        return messages_from_dict(payloads)

    def add_messages(self, messages: Sequence[BaseMessage]) -> None:
        """Persist a batch of LangChain messages."""
        self._bridge.run(self._aadd_messages(messages))

    async def _aadd_messages(self, messages: Sequence[BaseMessage]) -> None:
        for message in messages:
            payload = _compact_payload(message_to_dict(message))
            await self._manager.remember(self._topic_id, payload, self._source)

    def clear(self) -> None:
        """Remove every stored message for this session."""
        self._bridge.run(self._manager.forget(self._topic_id))

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._bridge.run(self._manager.close())
        self._bridge.close()

    def __enter__(self) -> LangChainMemory:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
