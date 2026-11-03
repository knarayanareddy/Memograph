from __future__ import annotations

import pytest

from memograph.config import LLMProvider, MemoGraphConfig
from memograph.db import DatabaseManager
from memograph.llm import LLMResponse
from memograph.memory_manager import MemoryManager


class FakeLLM:
    """Deterministic LLM used by consolidation tests."""

    provider_name = "fake"

    def __init__(self, responses: list[str] | None = None):
        self.responses = list(responses or [])
        self.calls: list[object] = []

    async def complete(self, request: object) -> LLMResponse:
        self.calls.append(request)
        content = self.responses.pop(0) if self.responses else '{"operations": []}'
        return LLMResponse(
            content=content,
            model="fake-model",
            provider="fake",
            prompt_tokens=10,
            completion_tokens=5,
            latency_ms=1,
        )

    async def health_check(self) -> bool:
        return True

    async def close(self) -> None:
        return None


@pytest.fixture
def config(tmp_path):
    return MemoGraphConfig(
        base_path=str(tmp_path / "store"),
        llm_provider=LLMProvider.NONE,
        auto_consolidate=False,
    )


@pytest.fixture
def fake_llm():
    return FakeLLM()


@pytest.fixture
async def manager(config):
    instance = MemoryManager(config=config)
    await instance.initialize()
    yield instance
    await instance.close()


@pytest.fixture
async def manager_with_fake_llm(config, fake_llm):
    instance = MemoryManager(config=config, llm=fake_llm)
    await instance.initialize()
    yield instance
    await instance.close()


@pytest.fixture
async def db(config):
    database = DatabaseManager(config.resolved_db_path)
    await database.connect()
    yield database
    await database.close()
