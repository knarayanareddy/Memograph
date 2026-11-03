from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError as PydanticValidationError

from memograph.vector_store import SQLiteVectorStore, VectorEntry, VectorMatch


async def test_vector_store_json_and_safe_filters(db):
    store = SQLiteVectorStore(db)
    await store.initialize()
    await store.upsert(VectorEntry(id="a", vector=[1.0, 0.0], metadata={"kind": "a"}))
    await store.upsert(VectorEntry(id="b", vector=[0.0, 1.0], metadata={"kind": "b"}))
    await store.upsert(VectorEntry(id="c", vector=[0.9, 0.1], metadata={"kind": "a"}))

    loaded = await store.get("a")
    assert loaded is not None
    assert loaded.vector == [1.0, 0.0]

    matches = await store.search([1.0, 0.0], top_k=3, filter_meta={"kind": "a"})
    assert all(isinstance(match, VectorMatch) for match in matches)
    assert matches[0].entry.id == "a"
    assert all(match.entry.metadata["kind"] == "a" for match in matches)

    # A SQL-injection-shaped metadata key is just a dict key, never SQL text.
    injected = await store.search([1.0, 0.0], top_k=3, filter_meta={"x' OR 1=1 --": "a"})
    assert injected == []

    row = await db.fetchone("SELECT * FROM vectors WHERE id = ?", ("a",))
    assert json.loads(row["vector_json"]) == [1.0, 0.0]
    assert await store.delete("b") is True
    assert await store.get("b") is None


async def test_vector_entry_validation():
    with pytest.raises(PydanticValidationError):
        VectorEntry(id="empty", vector=[], metadata={})


def test_no_pickle_in_vector_store():
    source = Path("src/memograph/vector_store.py").read_text(encoding="utf-8")
    assert "import pickle" not in source
    assert "pickle.load" not in source
    assert "pickle.dump" not in source
    assert "json_extract" not in source
