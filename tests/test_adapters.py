from __future__ import annotations

from pathlib import Path

from memograph.adapters import (
    AutoGenAdapter,
    CrewAIAdapter,
    LangChainAdapter,
    RawAPIAdapter,
)


async def test_adapters_use_stable_ids(manager):
    raw = RawAPIAdapter(manager)
    first = await raw.remember_interaction("What framework?", "FastAPI")
    second = await raw.remember_interaction("What framework?", "Still FastAPI")
    assert first.success and second.success
    assert first.topic.topic_id == second.topic.topic_id

    chain = await LangChainAdapter(manager).remember_chain_output({"answer": "ok"})
    crew = await CrewAIAdapter(manager).remember_agent_output("researcher", "done")
    autogen = await AutoGenAdapter(manager).remember_message("agent", "hello")
    assert chain.success and crew.success and autogen.success


def test_no_builtin_hash_in_adapters():
    source = Path("src/memograph/adapters.py").read_text(encoding="utf-8")
    assert "hash(" not in source
    assert "stable_id(" in source
