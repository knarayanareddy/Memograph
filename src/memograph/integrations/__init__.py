"""Optional, real framework SDK integrations."""

from __future__ import annotations

from typing import Any

__all__ = ["AutoGenMemory", "CrewAIMemoryBackend", "CrewAITaskOutputAdapter", "LangChainMemory"]


def __getattr__(name: str) -> Any:
    if name in {
        "AutoGenMemory",
        "CrewAIMemoryBackend",
        "CrewAITaskOutputAdapter",
        "LangChainMemory",
    }:
        from . import autogen, crewai, langchain

        return {
            "AutoGenMemory": autogen.AutoGenMemory,
            "CrewAIMemoryBackend": crewai.CrewAIMemoryBackend,
            "CrewAITaskOutputAdapter": crewai.CrewAITaskOutputAdapter,
            "LangChainMemory": langchain.LangChainMemory,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
