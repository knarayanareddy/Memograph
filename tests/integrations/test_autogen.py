from __future__ import annotations

import pytest

pytest.importorskip("autogen_agentchat")

from autogen_agentchat.messages import MultiModalMessage, TextMessage  # noqa: E402

from memograph.integrations import AutoGenMemory  # noqa: E402


@pytest.mark.integration
async def test_autogen_memory_roundtrip(tmp_path):
    memory = AutoGenMemory.from_path(tmp_path / "store")
    async with memory:
        first = await memory.remember_message(
            TextMessage(content="Uses FastAPI and SQLite", source="user")
        )
        assert first.startswith("fact_")
        more = await memory.remember_messages(
            [
                TextMessage(content="SQLite is canonical", source="assistant"),
                MultiModalMessage(content=["Architecture diagram"], source="tool"),
            ]
        )
        assert len(more) == 2
        context = await memory.context_for("What framework do we use?")
        assert "FastAPI" in context.text
