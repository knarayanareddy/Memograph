"""CrewAI storage-backend and task-output integrations."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from crewai import TaskOutput
    from crewai.memory import MemoryRecord, ScopeInfo
except ImportError as exc:  # pragma: no cover - depends on optional extra
    raise RuntimeError(
        "Install the 'memograph[integrations]' extra to use CrewAIMemoryBackend."
    ) from exc

from .. import LLMProvider, MemoGraph, MemoGraphConfig
from ..db import DatabaseManager
from ..validation import stable_id
from ..vector_store import SQLiteVectorStore, VectorEntry
from .common import AsyncBridge, clip_text

_BACKEND = "crewai"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS integration_records (
    backend TEXT NOT NULL,
    record_id TEXT NOT NULL,
    scope TEXT NOT NULL,
    categories_json TEXT NOT NULL,
    record_json TEXT NOT NULL,
    PRIMARY KEY (backend, record_id)
)
"""


class CrewAIMemoryBackend:
    """CrewAI ``StorageBackend`` protocol implemented over Memograph.

    Records are stored in a dedicated SQLite table, mirrored into Memograph
    topic views, and optionally indexed in the safe JSON vector store when an
    embedding is supplied. All SDK-facing methods are synchronous; ``asave``,
    ``asearch``, and ``adelete`` provide the async variants.
    """

    def __init__(
        self,
        base_path: str | Path = ".memograph",
        *,
        agent_id: str = "default",
        source: str = "crewai",
        manager: MemoGraph | None = None,
    ) -> None:
        self._bridge = AsyncBridge()
        self._manager = manager or MemoGraph(
            config=MemoGraphConfig(
                base_path=Path(base_path),
                agent_id=agent_id,
                llm_provider=LLMProvider.NONE,
                auto_consolidate=False,
            )
        )
        self._source = source
        self._closed = False
        self._bridge.run(self._initialize_async())

    def _db(self) -> DatabaseManager:
        manager = self._manager.manager
        if manager is None:
            raise RuntimeError("Memograph manager is not initialized")
        return manager.db

    async def _initialize_async(self) -> None:
        await self._manager.initialize()
        await self._db().execute(_CREATE_TABLE)

    @staticmethod
    def _topic_id(record_id: str) -> str:
        return stable_id(f"crewai:{record_id}", prefix="crewai", length=12)

    @staticmethod
    def _record_from_row(row: dict[str, Any]) -> MemoryRecord:
        return MemoryRecord.model_validate_json(str(row["record_json"]))

    async def _all_records_async(self) -> list[MemoryRecord]:
        rows = await self._db().fetchall(
            "SELECT record_json FROM integration_records WHERE backend = ? ORDER BY rowid",
            (_BACKEND,),
        )
        return [self._record_from_row(row) for row in rows]

    async def _get_record_async(self, record_id: str) -> MemoryRecord | None:
        row = await self._db().fetchone(
            "SELECT record_json FROM integration_records WHERE backend = ? AND record_id = ?",
            (_BACKEND, record_id),
        )
        return self._record_from_row(row) if row else None

    async def _upsert_record_async(self, record: MemoryRecord) -> None:
        record_id = str(record.id)
        payload = record.model_dump_json()
        categories = json.dumps(record.categories, ensure_ascii=False, separators=(",", ":"))
        db = self._db()
        store = SQLiteVectorStore(db)
        async with db.transaction():
            await db.execute(
                """
                INSERT INTO integration_records(
                    backend, record_id, scope, categories_json, record_json
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(backend, record_id) DO UPDATE SET
                    scope = excluded.scope,
                    categories_json = excluded.categories_json,
                    record_json = excluded.record_json
                """,
                (_BACKEND, record_id, record.scope, categories, payload),
            )
            if record.embedding:
                await store.upsert(
                    VectorEntry(
                        id=record_id,
                        vector=record.embedding,
                        metadata={
                            "backend": _BACKEND,
                            "record_id": record_id,
                            "scope": record.scope,
                            "categories": record.categories,
                        },
                    )
                )
            else:
                await store.delete(record_id)
        await self._manager.remember(
            self._topic_id(record_id),
            clip_text(record.content, 500),
            f"{self._source}:{record.scope}",
        )

    async def _save_async(self, records: Sequence[MemoryRecord]) -> None:
        for record in records:
            await self._upsert_record_async(record)

    @staticmethod
    def _matches(
        record: MemoryRecord,
        *,
        scope_prefix: str | None,
        categories: list[str] | None,
        metadata_filter: dict[str, Any] | None,
    ) -> bool:
        if scope_prefix and not record.scope.startswith(scope_prefix):
            return False
        if categories and not any(item in record.categories for item in categories):
            return False
        if metadata_filter and any(
            record.metadata.get(key) != value for key, value in metadata_filter.items()
        ):
            return False
        return True

    async def _search_async(
        self,
        query_embedding: list[float],
        scope_prefix: str | None = None,
        categories: list[str] | None = None,
        metadata_filter: dict[str, Any] | None = None,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[tuple[MemoryRecord, float]]:
        if not query_embedding or limit <= 0:
            return []
        store = SQLiteVectorStore(self._db())
        matches = await store.search(
            query_embedding,
            top_k=max(limit * 3, limit),
            min_score=min_score,
            filter_meta={"backend": _BACKEND},
        )
        results: list[tuple[MemoryRecord, float]] = []
        for match in matches:
            record_id = str(match.entry.metadata.get("record_id") or "")
            record = await self._get_record_async(record_id)
            if record is None:
                continue
            if not self._matches(
                record,
                scope_prefix=scope_prefix,
                categories=categories,
                metadata_filter=metadata_filter,
            ):
                continue
            results.append((record, match.score))
            if len(results) >= limit:
                break
        return results

    async def _delete_async(
        self,
        scope_prefix: str | None = None,
        categories: list[str] | None = None,
        record_ids: list[str] | None = None,
        older_than: datetime | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> int:
        records = await self._all_records_async()
        wanted = {str(item) for item in record_ids} if record_ids is not None else None
        selected: list[MemoryRecord] = []
        for record in records:
            if wanted is not None and str(record.id) not in wanted:
                continue
            if older_than is not None and record.created_at.isoformat() >= older_than.isoformat():
                continue
            if not self._matches(
                record,
                scope_prefix=scope_prefix,
                categories=categories,
                metadata_filter=metadata_filter,
            ):
                continue
            selected.append(record)
        db = self._db()
        store = SQLiteVectorStore(db)
        async with db.transaction():
            for record in selected:
                record_id = str(record.id)
                await db.execute(
                    "DELETE FROM integration_records WHERE backend = ? AND record_id = ?",
                    (_BACKEND, record_id),
                )
                await store.delete(record_id)
        for record in selected:
            await self._manager.forget(self._topic_id(str(record.id)))
        return len(selected)

    def save(self, records: Sequence[MemoryRecord]) -> None:
        self._bridge.run(self._save_async(records))

    async def asave(self, records: Sequence[MemoryRecord]) -> None:
        await asyncio.to_thread(self.save, records)

    def search(
        self,
        query_embedding: list[float],
        scope_prefix: str | None = None,
        categories: list[str] | None = None,
        metadata_filter: dict[str, Any] | None = None,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[tuple[MemoryRecord, float]]:
        return self._bridge.run(
            self._search_async(
                query_embedding,
                scope_prefix,
                categories,
                metadata_filter,
                limit,
                min_score,
            )
        )

    async def asearch(
        self,
        query_embedding: list[float],
        scope_prefix: str | None = None,
        categories: list[str] | None = None,
        metadata_filter: dict[str, Any] | None = None,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[tuple[MemoryRecord, float]]:
        return await asyncio.to_thread(
            self.search,
            query_embedding,
            scope_prefix,
            categories,
            metadata_filter,
            limit,
            min_score,
        )

    def get_record(self, record_id: str) -> MemoryRecord | None:
        return self._bridge.run(self._get_record_async(record_id))

    def list_records(
        self,
        scope_prefix: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[MemoryRecord]:
        records = self._bridge.run(self._all_records_async())
        if scope_prefix:
            records = [record for record in records if record.scope.startswith(scope_prefix)]
        return records[offset : offset + limit]

    def count(self, scope_prefix: str | None = None) -> int:
        return len(self.list_records(scope_prefix))

    def update(self, record: MemoryRecord) -> None:
        self.save([record])

    def delete(
        self,
        scope_prefix: str | None = None,
        categories: list[str] | None = None,
        record_ids: list[str] | None = None,
        older_than: datetime | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> int:
        return self._bridge.run(
            self._delete_async(
                scope_prefix,
                categories,
                record_ids,
                older_than,
                metadata_filter,
            )
        )

    async def adelete(
        self,
        scope_prefix: str | None = None,
        categories: list[str] | None = None,
        record_ids: list[str] | None = None,
        older_than: datetime | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> int:
        return await asyncio.to_thread(
            self.delete,
            scope_prefix,
            categories,
            record_ids,
            older_than,
            metadata_filter,
        )

    def reset(self, scope_prefix: str | None = None) -> None:
        self._bridge.run(self._delete_async(scope_prefix=scope_prefix))

    def list_categories(self, scope_prefix: str | None = None) -> dict[str, int]:
        counts: dict[str, int] = {}
        for record in self.list_records(scope_prefix):
            for category in record.categories:
                counts[category] = counts.get(category, 0) + 1
        return counts

    def list_scopes(self, parent: str = "/") -> list[str]:
        prefix = parent.rstrip("/")
        return sorted(
            {
                record.scope
                for record in self.list_records()
                if not prefix or record.scope.startswith(prefix)
            }
        )

    def get_scope_info(self, scope: str) -> ScopeInfo:
        records = [record for record in self.list_records() if record.scope == scope]
        categories: set[str] = set()
        oldest: datetime | None = None
        newest: datetime | None = None
        children: set[str] = set()
        prefix = scope.rstrip("/")
        for record in self.list_records():
            if record.scope.startswith(prefix + "/"):
                remainder = record.scope[len(prefix) :].lstrip("/")
                if remainder:
                    children.add(remainder.split("/", 1)[0])
        for record in records:
            categories.update(record.categories)
            if oldest is None or record.created_at < oldest:
                oldest = record.created_at
            if newest is None or record.created_at > newest:
                newest = record.created_at
        return ScopeInfo(
            path=scope,
            record_count=len(records),
            categories=sorted(categories),
            oldest_record=oldest,
            newest_record=newest,
            child_scopes=sorted(children),
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._bridge.run(self._manager.close())
        self._bridge.close()

    def __enter__(self) -> CrewAIMemoryBackend:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class CrewAITaskOutputAdapter:
    """Store ``crewai.TaskOutput`` objects as Memograph facts."""

    def __init__(self, manager: MemoGraph, *, source: str = "crewai") -> None:
        self.manager = manager
        self.source = source

    async def remember_task_output(self, output: TaskOutput, role: str | None = None) -> str:
        actor = role or output.agent or "agent"
        text = clip_text(output.raw or output.summary or output.description or "", 900)
        topic_id = stable_id(f"crewai:task:{actor}:{text}", prefix="crewai", length=12)
        result = await self.manager.remember(topic_id, f"{actor}: {text}", self.source)
        return result.fact.fact_id if result.fact else ""

    async def close(self) -> None:
        await self.manager.close()
