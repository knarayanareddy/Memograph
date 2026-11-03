"""Memograph: a self-healing, bandwidth-aware memory system for AI agents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapters import AutoGenAdapter, CrewAIAdapter, LangChainAdapter, RawAPIAdapter
from .config import (
    ConfidenceLevel,
    LLMProvider,
    MemoGraphConfig,
    MemoryLimits,
    ProviderConfig,
    get_config,
    reset_config,
)
from .consolidation import (
    ConsolidationGates,
    ConsolidationLock,
    ConsolidationPlan,
    DreamEngine,
    DreamResult,
    GateReport,
    GateResult,
    parse_consolidation_plan,
)
from .injection import BuiltContext, ContextWindowSpec, TokenBudgetManager, get_context_spec
from .llm import (
    LLMRequest,
    LLMResponse,
    Message,
    NullProvider,
    create_provider,
    probe_providers,
)
from .memory_manager import MemoryManager, WriteResult
from .models import IndexPointer, MemoryFact, MemoryIndex, TopicFile
from .vector_store import SQLiteVectorStore, VectorEntry, VectorMatch
from .verification import VerificationEngine

__version__ = "0.2.0"

__all__ = [
    "AutoGenAdapter",
    "BuiltContext",
    "ConfidenceLevel",
    "ConsolidationGates",
    "ConsolidationLock",
    "ConsolidationPlan",
    "ContextWindowSpec",
    "CrewAIAdapter",
    "DreamEngine",
    "DreamResult",
    "GateReport",
    "GateResult",
    "IndexPointer",
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "LangChainAdapter",
    "MemoGraph",
    "MemoGraphConfig",
    "MemoryFact",
    "MemoryIndex",
    "MemoryLimits",
    "MemoryManager",
    "Message",
    "NullProvider",
    "ProviderConfig",
    "RawAPIAdapter",
    "SQLiteVectorStore",
    "TokenBudgetManager",
    "TopicFile",
    "VectorEntry",
    "VectorMatch",
    "VerificationEngine",
    "WriteResult",
    "create_provider",
    "get_config",
    "get_context_spec",
    "parse_consolidation_plan",
    "probe_providers",
    "reset_config",
]


class MemoGraph:
    """High-level async facade."""

    def __init__(
        self,
        base_path: str | Path = ".memograph",
        agent_id: str = "default",
        provider: LLMProvider | str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        config: MemoGraphConfig | None = None,
        **kwargs: Any,
    ):
        if config is None:
            overrides: dict[str, Any] = {
                "base_path": str(base_path),
                "agent_id": agent_id,
            }
            if provider is not None:
                head = provider.value if isinstance(provider, LLMProvider) else provider
                if isinstance(head, str) and ":" in head:
                    head = head.partition(":")[0]
                overrides["llm_provider"] = head
            overrides.update(kwargs)
            config = MemoGraphConfig(**overrides)
        self.config = config
        self._manager: MemoryManager | None = None
        self._provider_override = provider
        self._model_override = model
        self._api_key_override = api_key
        self._base_url_override = base_url

    async def _get_manager(self) -> MemoryManager:
        if self._manager is None:
            llm = create_provider(
                provider=self._provider_override,
                model=self._model_override,
                config=self.config,
                api_key=self._api_key_override,
                base_url=self._base_url_override,
            )
            self._manager = MemoryManager(config=self.config, llm=llm)
            await self._manager.initialize()
        return self._manager

    @property
    def manager(self) -> MemoryManager | None:
        return self._manager

    async def initialize(self) -> None:
        await self._get_manager()

    async def close(self) -> None:
        if self._manager is not None:
            await self._manager.close()
            self._manager = None

    async def __aenter__(self) -> MemoGraph:
        await self.initialize()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def remember(
        self,
        topic_id: str,
        content: str,
        source: str = "user",
        **kwargs: Any,
    ) -> WriteResult:
        manager = await self._get_manager()
        return await manager.remember(topic_id, content, source, **kwargs)

    async def recall(self, query: str, top_k: int = 3, verify: bool = False) -> list[TopicFile]:
        manager = await self._get_manager()
        return await manager.recall(query, top_k, verify)

    async def forget(self, topic_id: str, fact_id: str | None = None) -> bool:
        manager = await self._get_manager()
        return await manager.forget(topic_id, fact_id)

    async def update(
        self,
        topic_id: str,
        fact_id: str,
        new_content: str | None = None,
        new_confidence: ConfidenceLevel | str | None = None,
        verification_source: str | None = None,
    ) -> bool:
        manager = await self._get_manager()
        return await manager.update(
            topic_id, fact_id, new_content, new_confidence, verification_source
        )

    async def get_topic(self, topic_id: str) -> TopicFile | None:
        manager = await self._get_manager()
        return await manager.get_topic(topic_id)

    async def save_topic(self, topic: TopicFile) -> None:
        manager = await self._get_manager()
        await manager.save_topic(topic)

    async def get_index(self) -> MemoryIndex:
        manager = await self._get_manager()
        return await manager.get_index()

    async def get_context_injection(self) -> str:
        manager = await self._get_manager()
        return await manager.get_context_injection()

    async def build_context(
        self, query: str, max_topics: int = 3, token_budget: int | None = None
    ) -> BuiltContext:
        manager = await self._get_manager()
        return await manager.build_context(query, max_topics, token_budget)

    async def status(self) -> dict[str, Any]:
        manager = await self._get_manager()
        return await manager.status()

    async def start_session(self, session_id: str | None = None) -> str:
        manager = await self._get_manager()
        return await manager.start_session(session_id)

    async def end_session(self) -> None:
        manager = await self._get_manager()
        await manager.end_session()

    async def archive_turn(
        self, role: str, content: str, tool_calls: list[Any] | None = None
    ) -> None:
        manager = await self._get_manager()
        await manager.archive_turn(role, content, tool_calls)

    async def grep_transcripts(
        self, pattern: str, max_results: int = 20, regex: bool = False
    ) -> list[dict[str, Any]]:
        manager = await self._get_manager()
        return await manager.grep_transcripts(pattern, max_results, regex)

    async def recent_signals(self, limit: int = 20) -> list[str]:
        manager = await self._get_manager()
        return await manager.recent_signals(limit)

    async def prune(self) -> int:
        manager = await self._get_manager()
        return await manager.prune()

    async def reconcile(self) -> None:
        manager = await self._get_manager()
        await manager.reconcile()

    async def dream_now(self, force: bool = False, max_tokens: int | None = None) -> DreamResult:
        manager = await self._get_manager()
        return await manager.dream_now(force, max_tokens)

    async def vector_store(self) -> SQLiteVectorStore:
        manager = await self._get_manager()
        return SQLiteVectorStore(manager.db)
