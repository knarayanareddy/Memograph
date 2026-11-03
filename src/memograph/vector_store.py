"""Safe SQLite vector store.

Vectors and metadata are stored as JSON, never ``pickle``.  Metadata filtering
happens in Python, so filter keys are never interpolated into SQL.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .db import DatabaseManager


def _now() -> str:
    return datetime.now(UTC).isoformat()


class VectorEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    vector: list[float] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class VectorMatch:
    entry: VectorEntry
    score: float


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norm_left = math.sqrt(sum(a * a for a in left))
    norm_right = math.sqrt(sum(b * b for b in right))
    if norm_left == 0.0 or norm_right == 0.0:
        return 0.0
    return dot / (norm_left * norm_right)


class SQLiteVectorStore:
    def __init__(self, db: DatabaseManager):
        self.db = db

    async def initialize(self) -> None:
        # The vectors table is part of the canonical schema.
        return None

    async def upsert(self, entry: VectorEntry) -> None:
        await self.db.execute(
            """
            INSERT INTO vectors(
                id, vector_json, dimensions, metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                vector_json = excluded.vector_json,
                dimensions = excluded.dimensions,
                metadata_json = excluded.metadata_json,
                updated_at = excluded.updated_at
            """,
            (
                entry.id,
                json.dumps(entry.vector, separators=(",", ":")),
                len(entry.vector),
                json.dumps(entry.metadata, ensure_ascii=False, separators=(",", ":")),
                _now(),
                _now(),
            ),
        )

    async def get(self, entry_id: str) -> VectorEntry | None:
        row = await self.db.fetchone("SELECT * FROM vectors WHERE id = ?", (entry_id,))
        if row is None:
            return None
        return VectorEntry(
            id=row["id"],
            vector=json.loads(row["vector_json"]),
            metadata=json.loads(row["metadata_json"]),
        )

    async def delete(self, entry_id: str) -> bool:
        cursor = await self.db.execute("DELETE FROM vectors WHERE id = ?", (entry_id,))
        return cursor.rowcount > 0

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        min_score: float = 0.0,
        filter_meta: dict[str, Any] | None = None,
    ) -> list[VectorMatch]:
        if top_k <= 0:
            return []
        rows = await self.db.fetchall("SELECT * FROM vectors")
        matches: list[VectorMatch] = []
        for row in rows:
            metadata = json.loads(row["metadata_json"])
            if filter_meta and any(
                metadata.get(key) != value for key, value in filter_meta.items()
            ):
                continue
            vector = json.loads(row["vector_json"])
            score = _cosine(query_vector, vector)
            if score < min_score:
                continue
            matches.append(
                VectorMatch(
                    entry=VectorEntry(id=row["id"], vector=vector, metadata=metadata),
                    score=score,
                )
            )
        matches.sort(key=lambda match: (-match.score, match.entry.id))
        return matches[:top_k]

    async def __aenter__(self) -> SQLiteVectorStore:
        await self.initialize()
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None
