"""Thin framework adapters with process-independent topic IDs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .validation import stable_id

if TYPE_CHECKING:  # pragma: no cover
    from .memory_manager import MemoryManager, WriteResult


class RawAPIAdapter:
    def __init__(self, manager: MemoryManager):
        self.manager = manager

    async def remember_interaction(
        self, query: str, response: str, source: str = "raw_api"
    ) -> WriteResult:
        topic_id = stable_id(f"raw:{query}", prefix="interaction", length=12)
        content = f"Q: {query}\nA: {response}"[:1000]
        return await self.manager.remember(topic_id, content, source)


class LangChainAdapter:
    def __init__(self, manager: MemoryManager):
        self.manager = manager

    async def remember_chain_output(self, payload: Any, source: str = "langchain") -> WriteResult:
        text = str(payload)[:1000]
        topic_id = stable_id(f"langchain:{text}", prefix="chain", length=12)
        return await self.manager.remember(topic_id, text, source)


class CrewAIAdapter:
    def __init__(self, manager: MemoryManager):
        self.manager = manager

    async def remember_agent_output(
        self, agent_role: str, output: Any, source: str = "crewai"
    ) -> WriteResult:
        text = f"{agent_role}: {output}"[:1000]
        topic_id = stable_id(f"crewai:{text}", prefix="crew", length=12)
        return await self.manager.remember(topic_id, text, source)


class AutoGenAdapter:
    def __init__(self, manager: MemoryManager):
        self.manager = manager

    async def remember_message(
        self, sender: str, content: Any, source: str = "autogen"
    ) -> WriteResult:
        text = f"{sender}: {content}"[:1000]
        topic_id = stable_id(f"autogen:{text}", prefix="autogen", length=12)
        return await self.manager.remember(topic_id, text, source)
