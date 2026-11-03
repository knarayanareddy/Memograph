"""Integration tests for the optional REST/WebSocket API."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from pydantic import ValidationError as PydanticValidationError
from starlette.websockets import WebSocketDisconnect

from memograph.api.app import create_app
from memograph.api.settings import APISettings
from memograph.config import LLMProvider

HEADERS = {"X-API-Key": "test-key-0123456789abcdef"}


def test_create_app_requires_key(tmp_base: Path) -> None:
    settings = APISettings(
        api_key=SecretStr(""),
        base_path=tmp_base,
        llm_provider=LLMProvider.NONE,
    )
    with pytest.raises(RuntimeError, match="MEMOGRAPH_API_KEY"):
        create_app(settings)


def test_create_app_rejects_short_key(tmp_base: Path) -> None:
    with pytest.raises(PydanticValidationError, match="at least 16"):
        APISettings(
            api_key="short",
            base_path=tmp_base,
            llm_provider=LLMProvider.NONE,
        )


def test_create_app_rejects_multi_user_mode(tmp_base: Path, api_key: str) -> None:
    settings = APISettings(
        api_key=api_key,
        base_path=tmp_base,
        llm_provider=LLMProvider.NONE,
        single_user_mode=False,
    )
    with pytest.raises(RuntimeError, match="Single-user"):
        create_app(settings)


def test_health_and_openapi_are_public(client: TestClient) -> None:
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["auth_model"] == "single-user-shared-key"
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert health.headers.get("X-Request-ID")


def test_auth_required(client: TestClient) -> None:
    assert client.get("/status").status_code == 401
    assert client.get("/status", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/status", headers=HEADERS).status_code == 200
    bearer = {"Authorization": f"Bearer {HEADERS['X-API-Key']}"}
    assert client.get("/status", headers=bearer).status_code == 200


def test_request_body_limit(client: TestClient) -> None:
    oversized = "x" * 9000
    response = client.post(
        "/remember",
        headers=HEADERS,
        json={"topic_id": "project_stack", "content": oversized},
    )
    assert response.status_code == 413
    assert response.json() == {"detail": "Request body too large"}


def test_memory_flow(client: TestClient) -> None:
    remembered = client.post(
        "/remember",
        headers=HEADERS,
        json={
            "topic_id": "project_stack",
            "content": "The backend uses FastAPI.",
            "source": "conversation",
            "tags": ["backend"],
        },
    )
    assert remembered.status_code == 200
    assert remembered.json()["success"] is True

    recall = client.get("/recall", headers=HEADERS, params={"query": "FastAPI", "top_k": 3})
    assert recall.status_code == 200
    assert recall.json()[0]["topic_id"] == "project_stack"

    context = client.post("/context", headers=HEADERS, json={"query": "What framework?"})
    assert context.status_code == 200
    assert "FastAPI" in context.json()["text"]
    assert client.get("/index", headers=HEADERS).json()["index"]
    assert client.post("/dream", headers=HEADERS, json={"force": True}).json()["status"] in {
        "completed",
        "skipped",
    }
    assert client.post("/prune", headers=HEADERS).status_code == 200
    assert client.post("/grep", headers=HEADERS, json={"pattern": "FastAPI"}).status_code == 200

    forgotten = client.post("/forget", headers=HEADERS, json={"topic_id": "project_stack"})
    assert forgotten.status_code == 200
    assert forgotten.json()["forgotten"] is True


def test_update_requires_verification_source(client: TestClient) -> None:
    created = client.post(
        "/remember",
        headers=HEADERS,
        json={"topic_id": "project_stack", "content": "The backend uses FastAPI."},
    )
    fact_id = created.json()["fact_id"]
    response = client.post(
        "/update",
        headers=HEADERS,
        json={
            "topic_id": "project_stack",
            "fact_id": fact_id,
            "new_confidence": "verified",
        },
    )
    assert response.status_code == 400
    assert "verification_source" in response.json()["detail"]


def test_websocket_event(client: TestClient) -> None:
    with client.websocket_connect("/events", headers=HEADERS) as websocket:
        response = client.post(
            "/remember",
            headers=HEADERS,
            json={"topic_id": "project_stack", "content": "WebSockets are enabled."},
        )
        assert response.status_code == 200
        event = websocket.receive_json()
        assert event["type"] == "memory.remembered"
        assert event["payload"]["topic_id"] == "project_stack"


def test_websocket_connection_cap(app, api_key: str) -> None:
    headers = {"X-API-Key": api_key}
    with TestClient(app) as ws_client:
        first = ws_client.websocket_connect("/events", headers=headers)
        second = ws_client.websocket_connect("/events", headers=headers)
        first.__enter__()
        second.__enter__()
        try:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with ws_client.websocket_connect("/events", headers=headers):
                    pass
            assert exc_info.value.code == 1013
        finally:
            second.__exit__(None, None, None)
            first.__exit__(None, None, None)


def test_rate_limiter_applied(tmp_base: Path, api_key: str) -> None:
    settings = APISettings(
        api_key=api_key,
        base_path=tmp_base,
        llm_provider=LLMProvider.NONE,
        rate_limit_per_minute=1,
    )
    with TestClient(create_app(settings)) as limited_client:
        assert limited_client.get("/status", headers=HEADERS).status_code == 200
        limited = limited_client.get("/status", headers=HEADERS)
        assert limited.status_code == 429
        assert limited.headers["Retry-After"] == "60"


def test_dream_rate_limiter_applied(tmp_base: Path, api_key: str) -> None:
    settings = APISettings(
        api_key=api_key,
        base_path=tmp_base,
        llm_provider=LLMProvider.NONE,
        dream_rate_limit_per_minute=1,
    )
    with TestClient(create_app(settings)) as limited_client:
        first = limited_client.post("/dream", headers=HEADERS, json={"force": True})
        assert first.status_code == 200
        second = limited_client.post("/dream", headers=HEADERS, json={"force": True})
        assert second.status_code == 429


def test_audit_logging_omits_secrets(client: TestClient, caplog) -> None:
    with caplog.at_level(logging.INFO, logger="memograph.audit"):
        response = client.get("/status", headers={"X-API-Key": "wrong"})
        assert response.status_code == 401
        success = client.post(
            "/remember",
            headers=HEADERS,
            json={"topic_id": "project_stack", "content": "Uses FastAPI."},
        )
        assert success.status_code == 200
    messages = [record.getMessage() for record in caplog.records]
    assert any("auth.failure" in message for message in messages)
    assert any("memory.remembered" in message for message in messages)
    assert all(HEADERS["X-API-Key"] not in message for message in messages)
    assert all("Uses FastAPI." not in message for message in messages)


def test_cors_disabled_by_default(client: TestClient) -> None:
    response = client.get("/health", headers={"Origin": "https://example.com"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
