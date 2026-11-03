from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError as PydanticValidationError

from memograph.config import (
    LLMProvider,
    MemoGraphConfig,
    MemoryLimits,
    ProviderConfig,
    get_config,
    reset_config,
)


def test_defaults():
    cfg = MemoGraphConfig()
    assert cfg.llm_provider == LLMProvider.OLLAMA
    assert cfg.agent_id == "default"
    assert cfg.auto_consolidate is False
    assert cfg.skeptical_mode is True
    assert cfg.resolved_db_path == Path(".memograph/memograph.db")
    assert cfg.limits.max_grep_pattern_chars == 200
    assert cfg.limits.grep_timeout_seconds == 0.05


def test_standard_provider_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-test")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test")
    monkeypatch.setenv("CUSTOM_API_KEY", "custom-test")
    cfg = MemoGraphConfig()
    assert cfg.anthropic_api_key == "anthropic-test"
    assert cfg.openai_api_key == "openai-test"
    assert cfg.custom_api_key == "custom-test"


def test_env_file(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "MEMOGRAPH_LLM_PROVIDER=none\nOPENAI_API_KEY=dotenv-key\n",
        encoding="utf-8",
    )
    cfg = MemoGraphConfig()
    assert cfg.llm_provider == LLMProvider.NONE
    assert cfg.openai_api_key == "dotenv-key"


def test_provider_overrides():
    cfg = MemoGraphConfig(llm_provider=LLMProvider.OPENAI, openai_api_key="base")
    active = cfg.get_active_provider_config(
        model="override-model", api_key="override-key", base_url="http://local/v1"
    )
    assert active.provider == LLMProvider.OPENAI
    assert active.model == "override-model"
    assert active.api_key == "override-key"
    assert active.base_url == "http://local/v1"


def test_provider_base_url_is_validated():
    with pytest.raises(PydanticValidationError):
        ProviderConfig(provider=LLMProvider.CUSTOM, base_url="file:///etc/passwd")
    with pytest.raises(PydanticValidationError):
        ProviderConfig(
            provider=LLMProvider.CUSTOM,
            base_url="https://user:secret@example.test/v1",
        )
    with pytest.raises(PydanticValidationError):
        MemoGraphConfig().get_active_provider_config(base_url="ftp://example.test")


def test_memory_limits_reject_non_positive_values():
    with pytest.raises(PydanticValidationError):
        MemoryLimits(grep_timeout_seconds=0)


def test_singleton():
    reset_config()
    first = get_config()
    assert get_config() is first
    overridden = get_config(base_path="other")
    assert overridden is not first
    assert str(overridden.base_path) == "other"
    reset_config()


def test_invalid_agent_id():
    with pytest.raises(PydanticValidationError):
        MemoGraphConfig(agent_id="../escape")
