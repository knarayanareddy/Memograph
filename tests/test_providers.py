from __future__ import annotations

import httpx
import pytest

from memograph.config import LLMProvider, MemoGraphConfig
from memograph.errors import ProviderError
from memograph.llm import LLMRequest, Message, NullProvider, create_provider


def handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/api/chat"):
        return httpx.Response(
            200,
            json={
                "message": {"content": "ollama"},
                "prompt_eval_count": 3,
                "eval_count": 2,
            },
        )
    if path.endswith("/api/tags"):
        return httpx.Response(200, json={"models": []})
    if path.endswith("/chat/completions"):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "openai"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2},
            },
        )
    if path.endswith("/v1/messages"):
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "anthropic"}],
                "usage": {"input_tokens": 7, "output_tokens": 3},
            },
        )
    if "generateContent" in path:
        assert "key" not in request.url.params
        assert request.headers.get("x-goog-api-key") == "test"
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "gemini"}]}}],
                "usageMetadata": {
                    "promptTokenCount": 11,
                    "candidatesTokenCount": 4,
                },
            },
        )
    if path.endswith("/models"):
        return httpx.Response(200, json={"data": []})
    return httpx.Response(404, json={"error": "not found"})


@pytest.fixture
def transport():
    return httpx.MockTransport(handler)


async def request_text() -> LLMRequest:
    return LLMRequest(messages=[Message(role="user", content="hello")])


async def test_ollama_provider(transport):
    config = MemoGraphConfig(ollama_base_url="http://ollama.test")
    provider = create_provider("ollama:llama3.1:8b", config=config, transport=transport)
    response = await provider.complete(await request_text())
    assert response.content == "ollama"
    assert response.model == "llama3.1:8b"
    assert response.prompt_tokens == 3
    assert await provider.health_check() is True
    await provider.close()


async def test_openai_compatible_provider(transport):
    config = MemoGraphConfig(
        llm_provider=LLMProvider.OPENAI,
        openai_api_key="test",
        openai_base_url="http://openai.test/v1",
    )
    provider = create_provider(config=config, transport=transport)
    response = await provider.complete(await request_text())
    assert response.content == "openai"
    assert response.prompt_tokens == 5
    assert await provider.health_check() is True
    await provider.close()


async def test_anthropic_provider(transport):
    config = MemoGraphConfig(
        llm_provider=LLMProvider.ANTHROPIC,
        anthropic_api_key="test",
        anthropic_base_url="http://anthropic.test",
    )
    provider = create_provider(config=config, transport=transport)
    response = await provider.complete(await request_text())
    assert response.content == "anthropic"
    assert response.prompt_tokens == 7
    await provider.close()


async def test_gemini_provider(transport):
    config = MemoGraphConfig(
        llm_provider=LLMProvider.GEMINI,
        google_api_key="test",
        gemini_model="gemini-test",
    )
    provider = create_provider(config=config, transport=transport)
    response = await provider.complete(await request_text())
    assert response.content == "gemini"
    assert response.prompt_tokens == 11
    await provider.close()


async def test_null_provider_and_missing_keys(transport):
    provider = NullProvider()
    response = await provider.complete(await request_text())
    assert response.content == '{"operations": []}'
    await provider.close()

    config = MemoGraphConfig(llm_provider=LLMProvider.ANTHROPIC)
    missing = create_provider(config=config, transport=transport)
    with pytest.raises(ProviderError):
        await missing.complete(await request_text())
    await missing.close()

    with pytest.raises(ValueError):
        create_provider("not-a-provider")
