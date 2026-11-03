from __future__ import annotations

import pytest

pytest.importorskip("crewai")

from crewai import TaskOutput  # noqa: E402
from crewai.memory import MemoryRecord  # noqa: E402
from crewai.memory.storage.backend import StorageBackend  # noqa: E402

from memograph import LLMProvider, MemoGraph, MemoGraphConfig  # noqa: E402
from memograph.integrations import (  # noqa: E402
    CrewAIMemoryBackend,
    CrewAITaskOutputAdapter,
)


@pytest.mark.integration
def test_crewai_backend_implements_storage_protocol():
    required = {
        name
        for name in dir(StorageBackend)
        if not name.startswith("_") and callable(getattr(StorageBackend, name))
    }
    provided = {
        name
        for name in dir(CrewAIMemoryBackend)
        if not name.startswith("_") and callable(getattr(CrewAIMemoryBackend, name))
    }
    assert required <= provided


@pytest.mark.integration
def test_crewai_backend_roundtrip(tmp_path):
    with CrewAIMemoryBackend(base_path=tmp_path / "store") as backend:
        record = MemoryRecord(
            id="r1",
            content="Uses FastAPI and SQLite",
            scope="/project",
            categories=["stack"],
            metadata={"team": "api"},
            importance=0.7,
            source="test",
            embedding=[1.0, 0.0],
        )
        backend.save([record])
        assert backend.count() == 1
        assert backend.get_record("r1").content == "Uses FastAPI and SQLite"
        assert backend.list_records()[0].scope == "/project"
        assert backend.list_categories()["stack"] == 1
        assert backend.list_scopes("/") == ["/project"]
        info = backend.get_scope_info("/project")
        assert info.record_count == 1
        assert "stack" in info.categories

        results = backend.search([1.0, 0.0], limit=5)
        assert results
        assert results[0][0].id == "r1"
        assert results[0][1] > 0.9

        backend.update(
            MemoryRecord(
                id="r1",
                content="Uses FastAPI",
                scope="/project",
                categories=["stack"],
                metadata={"team": "api"},
            )
        )
        assert backend.get_record("r1").content == "Uses FastAPI"
        assert backend.delete(record_ids=["r1"]) == 1
        assert backend.count() == 0


@pytest.mark.integration
async def test_crewai_task_output_adapter(tmp_path):
    manager = MemoGraph(
        config=MemoGraphConfig(
            base_path=tmp_path / "store",
            llm_provider=LLMProvider.NONE,
        )
    )
    adapter = CrewAITaskOutputAdapter(manager)
    output = TaskOutput(
        description="Framework research",
        raw="Uses FastAPI",
        agent="researcher",
    )
    fact_id = await adapter.remember_task_output(output)
    assert fact_id.startswith("fact_")
    await adapter.close()
