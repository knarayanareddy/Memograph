from __future__ import annotations

import pytest
from pydantic import SecretStr

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from memograph.api import (  # noqa: E402
    APIKeyAuth,
    APISettings,
    EventBroker,
    RateLimiter,
    make_event,
)
from memograph.api.app import create_app  # noqa: E402
from memograph.api.cli import main as api_main  # noqa: E402

HEADERS = {"X-API-Key": "test-key"}


@pytest.fixture
def settings(tmp_path):
    return APISettings(
        api_key=SecretStr("test-key"),
        base_path=tmp_path / "store",
        llm_provider="none",
        rate_limit_per_minute=100,
        cors_origins=[],
    )


def test_health_openapi_and_auth(settings):
    with TestClient(create_app(settings)) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        spec = client.get("/openapi.json")
        assert spec.status_code == 200
        assert "/remember" in spec.json()["paths"]
        assert client.get("/status").status_code == 401
        assert client.get("/status", headers=HEADERS).status_code == 200
        bearer = {"Authorization": "Bearer test-key"}
        assert client.get("/status", headers=bearer).status_code == 200


def test_memory_flow(settings):
    with TestClient(create_app(settings)) as client:
        remember = client.post(
            "/remember",
            headers=HEADERS,
            json={
                "topic_id": "project_stack",
                "content": "Uses FastAPI and SQLite",
                "source": "api-test",
            },
        )
        assert remember.status_code == 200
        payload = remember.json()
        assert payload["success"] is True
        assert payload["fact_id"].startswith("fact_")

        recall = client.get("/recall", headers=HEADERS, params={"query": "FastAPI", "top_k": 3})
        assert recall.status_code == 200
        assert any(topic["topic_id"] == "project_stack" for topic in recall.json())

        context = client.post("/context", headers=HEADERS, json={"query": "What framework?"})
        assert context.status_code == 200
        assert "FastAPI" in context.json()["text"]

        assert client.get("/index", headers=HEADERS).json()["index"]
        assert (
            client.post("/dream", headers=HEADERS, json={"force": True}).json()["status"]
            == "completed"
        )
        assert client.post("/prune", headers=HEADERS).status_code == 200
        assert client.post("/grep", headers=HEADERS, json={"pattern": "FastAPI"}).status_code == 200

        forgotten = client.post("/forget", headers=HEADERS, json={"topic_id": "project_stack"})
        assert forgotten.json() == {"forgotten": True}


def test_update_endpoint(settings):
    with TestClient(create_app(settings)) as client:
        created = client.post(
            "/remember",
            headers=HEADERS,
            json={
                "topic_id": "project_stack",
                "content": "Uses FastAPI",
                "source": "api-test",
            },
        ).json()
        updated = client.post(
            "/update",
            headers=HEADERS,
            json={
                "topic_id": "project_stack",
                "fact_id": created["fact_id"],
                "new_content": "Uses FastAPI and SQLite",
            },
        )
        assert updated.json() == {"updated": True}


def test_websocket_events(settings):
    with TestClient(create_app(settings)) as client:
        with client.websocket_connect("/events", headers=HEADERS) as websocket:
            client.post(
                "/remember",
                headers=HEADERS,
                json={
                    "topic_id": "project_stack",
                    "content": "Uses FastAPI",
                    "source": "api-test",
                },
            )
            event = websocket.receive_json()
            assert event["type"] == "memory.remembered"
            assert event["payload"]["topic_id"] == "project_stack"


def test_rate_limit(settings):
    settings.rate_limit_per_minute = 1
    with TestClient(create_app(settings)) as client:
        assert client.get("/status", headers=HEADERS).status_code == 200
        limited = client.get("/status", headers=HEADERS)
        assert limited.status_code == 429
        assert limited.headers["Retry-After"] == "60"


def test_cors_preflight(settings):
    settings.cors_origins = ["https://example.com"]
    with TestClient(create_app(settings)) as client:
        response = client.options(
            "/status",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-API-Key",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "https://example.com"


def test_auth_helpers():
    auth = APIKeyAuth("secret")
    assert auth.verify("secret", None) == auth.fingerprint
    assert auth.verify(None, "Bearer secret") == auth.fingerprint
    assert auth.verify("wrong", None) is None
    assert auth.verify(None, "Basic secret") is None
    assert len(auth.fingerprint) == 16
    assert callable(api_main)


async def test_rate_limiter_sliding_window():
    limiter = RateLimiter(2)
    assert await limiter.acquire("a") is True
    assert await limiter.acquire("a") is True
    assert await limiter.acquire("a") is False
    await limiter.reset("a")
    assert await limiter.acquire("a") is True


async def test_event_broker_bounded_delivery():
    broker = EventBroker(max_queue_size=1)
    async with broker.subscription() as queue:
        assert broker.subscriber_count == 1
        assert broker.publish(make_event("one", value=1)) == 1
        assert broker.publish(make_event("two", value=2)) == 1
        assert (await queue.get())["payload"]["value"] == 2
    assert broker.subscriber_count == 0
