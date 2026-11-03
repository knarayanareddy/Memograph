"""Lightweight skeptical-memory verification.

A fact with a relative ``verification_hint`` is marked stale when that source
no longer exists.  This is deliberately local and deterministic; LLM-based
verification can be layered on later.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from .config import ConfidenceLevel
from .errors import ValidationError
from .validation import safe_relative_path

if TYPE_CHECKING:  # pragma: no cover
    from .models import TopicFile


class VerificationEngine:
    def __init__(self, base_path: str | Path):
        self.base_path = Path(base_path).resolve()

    async def verify_topic(self, topic: TopicFile) -> TopicFile:
        for fact in topic.facts:
            hint = fact.verification_hint
            if not hint:
                continue
            try:
                path = safe_relative_path(self.base_path, hint)
                exists = await asyncio.to_thread(path.exists)
            except ValidationError:
                exists = False
            if not exists:
                fact.confidence = ConfidenceLevel.STALE
                fact.last_verified = None
        return topic
