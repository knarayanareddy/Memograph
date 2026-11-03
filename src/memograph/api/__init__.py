"""Optional authenticated REST/WebSocket service for Memograph."""

from __future__ import annotations

from typing import Any

from .auth import APIKeyAuth
from .events import EventBroker, make_event
from .rate_limit import RateLimiter
from .settings import APISettings

__all__ = [
    "APIKeyAuth",
    "APISettings",
    "EventBroker",
    "RateLimiter",
    "create_app",
    "make_event",
]


def __getattr__(name: str) -> Any:
    if name == "create_app":
        from .app import create_app

        return create_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
