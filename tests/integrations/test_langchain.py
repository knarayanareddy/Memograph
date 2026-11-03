from __future__ import annotations

import pytest

pytest.importorskip("langchain_core")

from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402

from memograph.integrations import LangChainMemory  # noqa: E402


@pytest.mark.integration
def test_langchain_memory_roundtrip(tmp_path):
    with LangChainMemory(base_path=tmp_path / "store") as memory:
        memory.add_messages([HumanMessage(content="hello"), AIMessage(content="hi there")])
        messages = memory.messages
        assert [str(message.content) for message in messages] == ["hello", "hi there"]
        assert [message.type for message in messages] == ["human", "ai"]

        memory.clear()
        assert memory.messages == []

        memory.messages = [HumanMessage(content="replaced")]
        assert [str(message.content) for message in memory.messages] == ["replaced"]
