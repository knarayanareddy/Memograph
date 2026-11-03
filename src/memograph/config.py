"""Configuration.

One flat ``BaseSettings`` model avoids the contradictory nested-settings
designs in the historical spec.  Standard provider environment variables are
supported directly; ``MEMOGRAPH_*`` variables configure the library itself.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from .errors import ConfigurationError
from .validation import validate_agent_id


class LLMProvider(StrEnum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    GROQ = "groq"
    CUSTOM = "custom"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    NONE = "none"


class ConfidenceLevel(StrEnum):
    VERIFIED = "verified"
    OBSERVED = "observed"
    INFERRED = "inferred"
    STALE = "stale"


class MemoryLimits(BaseModel):
    max_index_lines: int = 200
    max_index_bytes: int = 25_600
    max_pointer_chars: int = 150
    max_summary_chars: int = 80
    max_fact_chars: int = 1000
    min_consolidation_hours: int = 24
    min_consolidation_sessions: int = 5
    min_scan_interval_minutes: int = 10
    max_grep_pattern_chars: int = 200
    grep_timeout_seconds: float = 0.05

    @field_validator("*")
    @classmethod
    def _positive(cls, value: int | float) -> int | float:
        if value <= 0:
            raise ValueError("limits must be positive")
        return value


class ProviderConfig(BaseModel):
    """Resolved connection settings for one LLM provider."""

    model_config = ConfigDict(validate_assignment=True)

    provider: LLMProvider
    api_key: str = ""
    model: str = ""
    base_url: str = ""
    timeout: float = 60.0
    max_tokens: int = 4096

    @field_validator("base_url")
    @classmethod
    def _safe_base_url(cls, value: str) -> str:
        if not value:
            return value
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("provider base_url must be an http(s) URL with a host")
        if parsed.username or parsed.password:
            raise ValueError("provider base_url must not contain credentials")
        return value


class MemoGraphConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MEMOGRAPH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    base_path: Path = Path(".memograph")
    db_path: Path | None = None
    agent_id: str = "default"
    log_level: str = "INFO"
    debug_prompts: bool = False
    skeptical_mode: bool = True
    auto_consolidate: bool = False
    context_window_tokens: int | None = None

    llm_provider: LLMProvider = LLMProvider.OLLAMA
    consolidation_provider: LLMProvider | None = None
    consolidation_model: str | None = None

    limits: MemoryLimits = Field(default_factory=MemoryLimits)

    # Standard BYOK environment variables, with MEMOGRAPH_* aliases.
    anthropic_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("ANTHROPIC_API_KEY", "MEMOGRAPH_ANTHROPIC_API_KEY"),
    )
    anthropic_model: str = "claude-3-5-haiku-latest"
    anthropic_base_url: str = "https://api.anthropic.com"

    openai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("OPENAI_API_KEY", "MEMOGRAPH_OPENAI_API_KEY"),
    )
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"

    groq_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("GROQ_API_KEY", "MEMOGRAPH_GROQ_API_KEY"),
    )
    groq_model: str = "llama-3.1-8b-instant"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    google_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_API_KEY", "MEMOGRAPH_GOOGLE_API_KEY"),
    )
    gemini_model: str = "gemini-1.5-flash"

    custom_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("MEMOGRAPH_CUSTOM_API_KEY", "CUSTOM_API_KEY"),
    )
    custom_model: str = ""
    custom_base_url: str = ""

    ollama_model: str = "llama3.1:8b"
    ollama_base_url: str = "http://localhost:11434"
    ollama_timeout: float = 120.0

    @field_validator("agent_id")
    @classmethod
    def _agent_id(cls, value: str) -> str:
        return validate_agent_id(value)

    @model_validator(mode="after")
    def _resolve_paths(self) -> MemoGraphConfig:
        if self.db_path is None:
            object.__setattr__(self, "db_path", self.base_path / "memograph.db")
        return self

    @property
    def resolved_db_path(self) -> Path:
        if self.db_path is None:
            raise ConfigurationError("Memograph database path is not configured")
        return self.db_path

    def get_active_provider_config(
        self,
        provider: LLMProvider | str | None = None,
        *,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> ProviderConfig:
        """Return a copy of provider settings with explicit overrides applied."""
        resolved = LLMProvider(provider) if provider else self.llm_provider
        common: dict[str, Any] = {"provider": resolved, "max_tokens": 4096}
        if resolved == LLMProvider.OLLAMA:
            cfg = ProviderConfig(
                **common,
                model=self.ollama_model,
                base_url=self.ollama_base_url,
                timeout=self.ollama_timeout,
            )
        elif resolved == LLMProvider.OPENAI:
            cfg = ProviderConfig(
                **common,
                api_key=self.openai_api_key,
                model=self.openai_model,
                base_url=self.openai_base_url,
            )
        elif resolved == LLMProvider.GROQ:
            cfg = ProviderConfig(
                **common,
                api_key=self.groq_api_key,
                model=self.groq_model,
                base_url=self.groq_base_url,
            )
        elif resolved == LLMProvider.CUSTOM:
            cfg = ProviderConfig(
                **common,
                api_key=self.custom_api_key,
                model=self.custom_model or "local-model",
                base_url=self.custom_base_url,
                timeout=120.0,
            )
        elif resolved == LLMProvider.ANTHROPIC:
            cfg = ProviderConfig(
                **common,
                api_key=self.anthropic_api_key,
                model=self.anthropic_model,
                base_url=self.anthropic_base_url,
            )
        elif resolved == LLMProvider.GEMINI:
            cfg = ProviderConfig(
                **common,
                api_key=self.google_api_key,
                model=self.gemini_model,
                base_url="https://generativelanguage.googleapis.com/v1beta",
            )
        elif resolved == LLMProvider.NONE:
            cfg = ProviderConfig(**common, model="none")
        else:  # pragma: no cover - StrEnum exhaustiveness guard
            raise ValueError(f"Unknown provider: {resolved}")

        if model is not None:
            cfg.model = model
        if api_key is not None:
            cfg.api_key = api_key
        if base_url is not None:
            cfg.base_url = base_url
        return cfg

    def get_consolidation_provider(self) -> LLMProvider:
        return self.consolidation_provider or self.llm_provider

    def is_local(self) -> bool:
        return self.llm_provider in {LLMProvider.OLLAMA, LLMProvider.CUSTOM, LLMProvider.NONE}

    def summary(self) -> dict[str, Any]:
        active = self.get_active_provider_config()
        return {
            "provider": self.llm_provider.value,
            "model": active.model,
            "local": self.is_local(),
            "agent_id": self.agent_id,
            "auto_consolidate": self.auto_consolidate,
            "skeptical_mode": self.skeptical_mode,
            "base_path": str(self.base_path),
            "db_path": str(self.resolved_db_path),
        }


_config: MemoGraphConfig | None = None


def get_config(**overrides: Any) -> MemoGraphConfig:
    """Return the process-wide config, replacing it when overrides are given."""
    global _config
    if _config is None or overrides:
        _config = MemoGraphConfig(**overrides)
    return _config


def reset_config() -> None:
    global _config
    _config = None
