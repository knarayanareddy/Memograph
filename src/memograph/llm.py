"""Model-agnostic LLM providers.

All providers use ``httpx`` directly.  There are no undeclared SDK extras and
no provider-specific optional dependency names in error messages.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field

from .config import LLMProvider, MemoGraphConfig, ProviderConfig, get_config
from .errors import ProviderError


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant"]
    content: str


class LLMRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[Message] = Field(default_factory=list)
    model: str | None = None
    max_tokens: int = 2048
    temperature: float = 0.1
    system_prompt: str | None = None
    purpose: str = "general"

    def effective_messages(self) -> list[Message]:
        messages = list(self.messages)
        if self.system_prompt:
            messages.insert(0, Message(role="system", content=self.system_prompt))
        return messages


class LLMResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class BaseLLMProvider(ABC):
    provider_name: ClassVar[str] = "base"

    def __init__(
        self,
        config: ProviderConfig,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.config = config
        self._client = httpx.AsyncClient(
            timeout=config.timeout,
            transport=transport,
        )

    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Return a completion for ``request``."""

    async def health_check(self) -> bool:
        return True

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> BaseLLMProvider:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()


class NullProvider(BaseLLMProvider):
    """Offline provider used for tests and local-only operation."""

    provider_name: ClassVar[str] = LLMProvider.NONE.value

    def __init__(self, config: ProviderConfig | None = None):
        self.config = config or ProviderConfig(provider=LLMProvider.NONE, model="none")
        self._client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200))
        )

    async def complete(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            content='{"operations": []}',
            model=self.config.model or "none",
            provider=self.provider_name,
        )

    async def health_check(self) -> bool:
        return True


class OllamaProvider(BaseLLMProvider):
    provider_name: ClassVar[str] = LLMProvider.OLLAMA.value

    async def complete(self, request: LLMRequest) -> LLMResponse:
        model = request.model or self.config.model
        if not model:
            raise ProviderError("An Ollama model is required")
        url = f"{self.config.base_url.rstrip('/')}/api/chat"
        payload = {
            "model": model,
            "stream": False,
            "messages": [
                {"role": m.role, "content": m.content} for m in request.effective_messages()
            ],
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }
        started = time.monotonic()
        response = await self._client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        content = data.get("message", {}).get("content", "")
        if not isinstance(content, str):
            raise ProviderError("Ollama returned a non-text message")
        return LLMResponse(
            content=content,
            model=model,
            provider=self.provider_name,
            prompt_tokens=int(data.get("prompt_eval_count", 0) or 0),
            completion_tokens=int(data.get("eval_count", 0) or 0),
            latency_ms=int((time.monotonic() - started) * 1000),
        )

    async def health_check(self) -> bool:
        try:
            response = await self._client.get(f"{self.config.base_url.rstrip('/')}/api/tags")
            return response.status_code < 400
        except httpx.HTTPError:
            return False


class OpenAICompatibleProvider(BaseLLMProvider):
    """OpenAI, Groq, LM Studio, vLLM, and other chat-completions endpoints."""

    provider_name: ClassVar[str] = "openai-compatible"

    async def complete(self, request: LLMRequest) -> LLMResponse:
        if not self.config.base_url:
            raise ProviderError("A chat-completions base_url is required")
        model = request.model or self.config.model
        if not model:
            raise ProviderError("A model is required")
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {self.config.api_key}"} if self.config.api_key else {}
        payload = {
            "model": model,
            "messages": [
                {"role": m.role, "content": m.content} for m in request.effective_messages()
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        started = time.monotonic()
        response = await self._client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("Malformed chat-completions response") from exc
        usage = data.get("usage") or {}
        return LLMResponse(
            content=str(content),
            model=model,
            provider=self.config.provider.value,
            prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
            completion_tokens=int(usage.get("completion_tokens", 0) or 0),
            latency_ms=int((time.monotonic() - started) * 1000),
        )

    async def health_check(self) -> bool:
        try:
            response = await self._client.get(
                f"{self.config.base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {self.config.api_key}"}
                if self.config.api_key
                else {},
            )
            return response.status_code < 500
        except httpx.HTTPError:
            return False


class AnthropicProvider(BaseLLMProvider):
    provider_name: ClassVar[str] = LLMProvider.ANTHROPIC.value

    async def complete(self, request: LLMRequest) -> LLMResponse:
        if not self.config.api_key:
            raise ProviderError("ANTHROPIC_API_KEY is required for the Anthropic provider")
        model = request.model or self.config.model
        system_parts: list[str] = []
        messages: list[dict[str, str]] = []
        for message in request.effective_messages():
            if message.role == "system":
                system_parts.append(message.content)
            else:
                messages.append({"role": message.role, "content": message.content})
        url = f"{self.config.base_url.rstrip('/')}/v1/messages"
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "system": "\n\n".join(system_parts),
            "messages": messages,
        }
        started = time.monotonic()
        response = await self._client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        blocks = data.get("content") or []
        content = "".join(block.get("text", "") for block in blocks if isinstance(block, dict))
        usage = data.get("usage") or {}
        return LLMResponse(
            content=content,
            model=model,
            provider=self.provider_name,
            prompt_tokens=int(usage.get("input_tokens", 0) or 0),
            completion_tokens=int(usage.get("output_tokens", 0) or 0),
            latency_ms=int((time.monotonic() - started) * 1000),
        )

    async def health_check(self) -> bool:
        return bool(self.config.api_key)


class GeminiProvider(BaseLLMProvider):
    provider_name: ClassVar[str] = LLMProvider.GEMINI.value

    async def complete(self, request: LLMRequest) -> LLMResponse:
        if not self.config.api_key:
            raise ProviderError("GOOGLE_API_KEY is required for the Gemini provider")
        model = request.model or self.config.model
        url = f"{self.config.base_url.rstrip('/')}/models/{model}:generateContent"
        headers = {
            "x-goog-api-key": self.config.api_key,
            "content-type": "application/json",
        }
        contents: list[dict[str, Any]] = []
        for message in request.effective_messages():
            role = "model" if message.role == "assistant" else "user"
            prefix = "[SYSTEM]\n" if message.role == "system" else ""
            contents.append({"role": role, "parts": [{"text": prefix + message.content}]})
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            },
        }
        started = time.monotonic()
        response = await self._client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
            content = "".join(part.get("text", "") for part in parts)
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("Malformed Gemini response") from exc
        usage = data.get("usageMetadata") or {}
        return LLMResponse(
            content=content,
            model=model,
            provider=self.provider_name,
            prompt_tokens=int(usage.get("promptTokenCount", 0) or 0),
            completion_tokens=int(usage.get("candidatesTokenCount", 0) or 0),
            latency_ms=int((time.monotonic() - started) * 1000),
        )

    async def health_check(self) -> bool:
        return bool(self.config.api_key)


def create_provider(
    provider: LLMProvider | str | None = None,
    model: str | None = None,
    config: MemoGraphConfig | None = None,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> BaseLLMProvider:
    """Create a provider from config and explicit overrides."""
    cfg = config or get_config()
    resolved: LLMProvider | str | None = provider
    if isinstance(provider, str) and ":" in provider:
        head, _, tail = provider.partition(":")
        if head in {item.value for item in LLMProvider}:
            resolved = LLMProvider(head)
            model = model or tail
    resolved_provider = LLMProvider(resolved) if resolved else cfg.llm_provider
    provider_config = cfg.get_active_provider_config(
        resolved_provider, model=model, api_key=api_key, base_url=base_url
    )
    if resolved_provider in {
        LLMProvider.OPENAI,
        LLMProvider.GROQ,
        LLMProvider.CUSTOM,
    }:
        return OpenAICompatibleProvider(provider_config, transport=transport)
    if resolved_provider == LLMProvider.OLLAMA:
        return OllamaProvider(provider_config, transport=transport)
    if resolved_provider == LLMProvider.ANTHROPIC:
        return AnthropicProvider(provider_config, transport=transport)
    if resolved_provider == LLMProvider.GEMINI:
        return GeminiProvider(provider_config, transport=transport)
    if resolved_provider == LLMProvider.NONE:
        return NullProvider(provider_config)
    raise ProviderError(f"Unknown provider: {resolved_provider}")  # pragma: no cover


async def probe_providers(config: MemoGraphConfig | None = None) -> dict[str, bool]:
    """Report which configured providers appear reachable."""
    cfg = config or get_config()
    results: dict[str, bool] = {}
    for item in LLMProvider:
        provider = create_provider(item, config=cfg)
        try:
            results[item.value] = await provider.health_check()
        except Exception:
            results[item.value] = False
        finally:
            await provider.close()
    return results
