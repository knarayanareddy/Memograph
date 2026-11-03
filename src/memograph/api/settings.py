"""Settings for the optional REST/WebSocket service."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..config import LLMProvider, MemoGraphConfig


class APISettings(BaseSettings):
    """Environment-driven API settings; secure by default.

    An API key is required. CORS is disabled unless origins are explicitly
    configured, and the in-process rate limiter applies to every protected
    HTTP and WebSocket request.
    """

    model_config = SettingsConfigDict(
        env_prefix="MEMOGRAPH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias="MEMOGRAPH_API_KEY",
        description="Shared secret for X-API-Key or Authorization: Bearer.",
    )
    cors_origins: list[str] = Field(
        default_factory=list,
        validation_alias="MEMOGRAPH_API_CORS_ORIGINS",
        description="Comma-separated or JSON list of allowed browser origins.",
    )
    rate_limit_per_minute: int = Field(
        default=60,
        ge=1,
        le=10_000,
        validation_alias="MEMOGRAPH_API_RATE_LIMIT_PER_MINUTE",
    )
    base_path: Path = Field(default=Path(".memograph"), validation_alias="MEMOGRAPH_BASE_PATH")
    agent_id: str = Field(default="default", validation_alias="MEMOGRAPH_AGENT_ID")
    llm_provider: str = Field(default="none", validation_alias="MEMOGRAPH_LLM_PROVIDER")
    host: str = Field(default="0.0.0.0", validation_alias="MEMOGRAPH_API_HOST")
    port: int = Field(default=8000, ge=1, le=65_535, validation_alias="MEMOGRAPH_API_PORT")
    log_level: str = Field(default="info", validation_alias="MEMOGRAPH_API_LOG_LEVEL")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    def to_memograph_config(self) -> MemoGraphConfig:
        return MemoGraphConfig(
            base_path=self.base_path,
            agent_id=self.agent_id,
            llm_provider=LLMProvider(self.llm_provider),
            auto_consolidate=False,
        )
