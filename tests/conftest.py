from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from memograph import MemoGraph
from memograph.api.app import create_app
from memograph.api.settings import APISettings
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
def config_factory(tmp_path: Path):
    """Return isolated configs for persistence/state tests."""

    def make(**overrides: Any) -> MemoGraphConfig:
        params: dict[str, Any] = {
            "base_path": str(tmp_path / overrides.pop("name", "store")),
            "llm_provider": LLMProvider.NONE,
            "auto_consolidate": False,
        }
        params.update(overrides)
        return MemoGraphConfig(**params)

    return make


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


@pytest.fixture
async def graph(config: MemoGraphConfig) -> MemoGraph:
    instance = MemoGraph(config=config)
    await instance.initialize()
    yield instance
    await instance.close()


@pytest.fixture
def tmp_base(tmp_path: Path) -> Path:
    return tmp_path / ".memograph"


@pytest.fixture
def api_key() -> str:
    return "test-key-0123456789abcdef"


@pytest.fixture
def api_settings(tmp_base: Path, api_key: str) -> APISettings:
    return APISettings(
        api_key=api_key,
        base_path=tmp_base,
        llm_provider="none",
        max_request_bytes=8192,
        max_websocket_connections=2,
        dream_rate_limit_per_minute=2,
        max_llm_tokens=256,
    )


@pytest.fixture
def app(api_settings: APISettings):
    return create_app(api_settings)


@pytest.fixture
def client(app) -> Iterator[Any]:
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client
