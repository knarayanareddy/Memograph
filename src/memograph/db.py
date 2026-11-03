"""SQLite persistence layer.

SQLite is the single source of truth.  Generated JSON/Markdown files are
rebuilt from this database at startup, so a crash during file replacement is
recoverable.  All writes use an explicit immediate transaction.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite

from .errors import ValidationError
from .models import IndexPointer, MemoryFact, TopicFile

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS topics (
    agent_id TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    topic_name TEXT NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]',
    file_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_modified TEXT NOT NULL,
    PRIMARY KEY (agent_id, topic_id),
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS facts (
    agent_id TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    fact_id TEXT NOT NULL,
    content TEXT NOT NULL,
    confidence_level TEXT NOT NULL,
    source TEXT NOT NULL,
    verification_hint TEXT,
    created_at TEXT NOT NULL,
    last_verified TEXT,
    contradicts_json TEXT NOT NULL DEFAULT '[]',
    meta_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (agent_id, topic_id, fact_id),
    FOREIGN KEY (agent_id, topic_id)
        REFERENCES topics(agent_id, topic_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS index_pointers (
    agent_id TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    topic_file_path TEXT NOT NULL,
    summary TEXT NOT NULL,
    confidence REAL NOT NULL,
    pointer_line TEXT NOT NULL,
    last_updated TEXT NOT NULL,
    last_accessed TEXT,
    access_count INTEGER NOT NULL DEFAULT 0,
    is_stale INTEGER NOT NULL DEFAULT 0,
    verification_source TEXT,
    PRIMARY KEY (agent_id, topic_id),
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sessions (
    agent_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    turn_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (agent_id, session_id),
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS dream_runs (
    agent_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    trigger TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    duration_ms INTEGER,
    operations_applied INTEGER NOT NULL DEFAULT 0,
    facts_created INTEGER NOT NULL DEFAULT 0,
    facts_merged INTEGER NOT NULL DEFAULT 0,
    facts_pruned INTEGER NOT NULL DEFAULT 0,
    contradictions_resolved INTEGER NOT NULL DEFAULT 0,
    confidence_promoted INTEGER NOT NULL DEFAULT 0,
    pointers_pruned INTEGER NOT NULL DEFAULT 0,
    llm_provider TEXT,
    llm_model TEXT,
    llm_prompt_tokens INTEGER NOT NULL DEFAULT 0,
    llm_completion_tokens INTEGER NOT NULL DEFAULT 0,
    llm_latency_ms INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    error_phase TEXT,
    PRIMARY KEY (agent_id, run_id),
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS dream_state (
    agent_id TEXT PRIMARY KEY,
    last_run_id TEXT,
    last_consolidated_at TEXT,
    sessions_since_last INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS llm_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    session_id TEXT,
    call_id TEXT,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    purpose TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vectors (
    id TEXT PRIMARY KEY,
    vector_json TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

DREAM_RUN_FIELDS = frozenset(
    {
        "status",
        "ended_at",
        "duration_ms",
        "operations_applied",
        "facts_created",
        "facts_merged",
        "facts_pruned",
        "contradictions_resolved",
        "confidence_promoted",
        "pointers_pruned",
        "llm_provider",
        "llm_model",
        "llm_prompt_tokens",
        "llm_completion_tokens",
        "llm_latency_ms",
        "error_message",
        "error_phase",
    }
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    return json.loads(value)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


class DatabaseManager:
    """Async SQLite manager with a single connection and explicit transactions."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._conn: aiosqlite.Connection | None = None
        self._in_transaction = False

    async def connect(self) -> None:
        if self._conn is not None:
            return
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(str(self.db_path), isolation_level=None)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode = WAL")
        await self._conn.execute("PRAGMA foreign_keys = ON")
        await self._conn.execute("PRAGMA synchronous = NORMAL")
        await self._conn.executescript(SCHEMA)
        await self._conn.execute(
            "INSERT OR IGNORE INTO schema_version(version, description, applied_at) "
            "VALUES (?, ?, ?)",
            (1, "Canonical Memograph schema", _now()),
        )

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    @property
    def connection(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("DatabaseManager is not connected")
        return self._conn

    async def execute(self, sql: str, params: tuple[Any, ...] = ()) -> aiosqlite.Cursor:
        cursor = await self.connection.execute(sql, params)
        if not self._in_transaction:
            await self.connection.commit()
        return cursor

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[DatabaseManager]:
        """Hold a ``BEGIN IMMEDIATE`` transaction for a multi-table write."""
        if self._in_transaction:
            raise RuntimeError("Nested transactions are not supported")
        await self.connection.execute("BEGIN IMMEDIATE")
        self._in_transaction = True
        try:
            yield self
            await self.connection.commit()
        except BaseException:
            await self.connection.rollback()
            raise
        finally:
            self._in_transaction = False

    async def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        async with self.connection.execute(sql, params) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row is not None else None

    async def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        async with self.connection.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def fetchval(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        row = await self.fetchone(sql, params)
        return next(iter(row.values())) if row else None

    async def __aenter__(self) -> DatabaseManager:
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    # ── Agents ───────────────────────────────────────────────────────────────

    async def ensure_agent(self, agent_id: str, display_name: str = "") -> None:
        await self.execute(
            "INSERT OR IGNORE INTO agents(id, display_name, created_at) VALUES (?, ?, ?)",
            (agent_id, display_name, _now()),
        )

    # ── Topics and facts ─────────────────────────────────────────────────────

    async def upsert_topic(self, agent_id: str, topic: TopicFile, file_path: str) -> None:
        await self.execute(
            """
            INSERT INTO topics(
                agent_id, topic_id, topic_name, tags_json, file_path,
                created_at, last_modified
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_id, topic_id) DO UPDATE SET
                topic_name = excluded.topic_name,
                tags_json = excluded.tags_json,
                file_path = excluded.file_path,
                last_modified = excluded.last_modified
            """,
            (
                agent_id,
                topic.topic_id,
                topic.topic_name,
                _dumps(topic.tags),
                file_path,
                topic.created_at.isoformat(),
                topic.last_modified.isoformat(),
            ),
        )

    async def replace_topic_facts(self, agent_id: str, topic: TopicFile) -> None:
        await self.execute(
            "DELETE FROM facts WHERE agent_id = ? AND topic_id = ?",
            (agent_id, topic.topic_id),
        )
        for fact in topic.facts:
            await self._insert_fact(agent_id, topic.topic_id, fact)

    async def _insert_fact(self, agent_id: str, topic_id: str, fact: MemoryFact) -> None:
        await self.execute(
            """
            INSERT INTO facts(
                agent_id, topic_id, fact_id, content, confidence_level, source,
                verification_hint, created_at, last_verified,
                contradicts_json, meta_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_id, topic_id, fact_id) DO UPDATE SET
                content = excluded.content,
                confidence_level = excluded.confidence_level,
                source = excluded.source,
                verification_hint = excluded.verification_hint,
                last_verified = excluded.last_verified,
                contradicts_json = excluded.contradicts_json,
                meta_json = excluded.meta_json
            """,
            (
                agent_id,
                topic_id,
                fact.fact_id,
                fact.content,
                fact.confidence.value,
                fact.source,
                fact.verification_hint,
                fact.created_at.isoformat(),
                fact.last_verified.isoformat() if fact.last_verified else None,
                _dumps(fact.contradicts_ids),
                _dumps(fact.meta),
            ),
        )

    async def insert_fact(self, agent_id: str, topic_id: str, fact: MemoryFact) -> None:
        await self._insert_fact(agent_id, topic_id, fact)

    async def get_facts(self, agent_id: str, topic_id: str) -> list[dict[str, Any]]:
        rows = await self.fetchall(
            "SELECT * FROM facts WHERE agent_id = ? AND topic_id = ? ORDER BY created_at",
            (agent_id, topic_id),
        )
        for row in rows:
            row["contradicts_ids"] = _loads(row.pop("contradicts_json"), [])
            row["meta"] = _loads(row.pop("meta_json"), {})
        return rows

    async def delete_fact(self, agent_id: str, topic_id: str, fact_id: str) -> bool:
        cursor = await self.execute(
            "DELETE FROM facts WHERE agent_id = ? AND topic_id = ? AND fact_id = ?",
            (agent_id, topic_id, fact_id),
        )
        return cursor.rowcount > 0

    async def update_fact_confidence(
        self,
        agent_id: str,
        topic_id: str,
        fact_id: str,
        confidence: str,
        verification_hint: str | None = None,
    ) -> bool:
        cursor = await self.execute(
            """
            UPDATE facts
               SET confidence_level = ?,
                   last_verified = ?,
                   verification_hint = COALESCE(?, verification_hint)
             WHERE agent_id = ? AND topic_id = ? AND fact_id = ?
            """,
            (confidence, _now(), verification_hint, agent_id, topic_id, fact_id),
        )
        return cursor.rowcount > 0

    def _row_to_fact(self, row: dict[str, Any]) -> MemoryFact:
        return MemoryFact(
            fact_id=row["fact_id"],
            content=row["content"],
            confidence=row["confidence_level"],
            source=row["source"],
            verification_hint=row.get("verification_hint"),
            created_at=_parse_dt(row["created_at"]) or datetime.now(UTC),
            last_verified=_parse_dt(row.get("last_verified")),
            contradicts_ids=_loads(row.get("contradicts_json"), []),
            meta=_loads(row.get("meta_json"), {}),
        )

    async def get_topic(self, agent_id: str, topic_id: str) -> TopicFile | None:
        row = await self.fetchone(
            "SELECT * FROM topics WHERE agent_id = ? AND topic_id = ?",
            (agent_id, topic_id),
        )
        if row is None:
            return None
        fact_rows = await self.fetchall(
            "SELECT * FROM facts WHERE agent_id = ? AND topic_id = ? ORDER BY created_at",
            (agent_id, topic_id),
        )
        return TopicFile(
            topic_id=row["topic_id"],
            topic_name=row["topic_name"],
            agent_id=agent_id,
            facts=[self._row_to_fact(r) for r in fact_rows],
            tags=_loads(row.get("tags_json"), []),
            file_path=row["file_path"],
            created_at=_parse_dt(row["created_at"]) or datetime.now(UTC),
            last_modified=_parse_dt(row["last_modified"]) or datetime.now(UTC),
        )

    async def get_all_topics(self, agent_id: str) -> list[TopicFile]:
        rows = await self.fetchall(
            "SELECT topic_id FROM topics WHERE agent_id = ? ORDER BY topic_id",
            (agent_id,),
        )
        topics: list[TopicFile] = []
        for row in rows:
            topic = await self.get_topic(agent_id, row["topic_id"])
            if topic is not None:
                topics.append(topic)
        return topics

    async def delete_topic(self, agent_id: str, topic_id: str) -> None:
        await self.execute(
            "DELETE FROM topics WHERE agent_id = ? AND topic_id = ?",
            (agent_id, topic_id),
        )
        await self.execute(
            "DELETE FROM index_pointers WHERE agent_id = ? AND topic_id = ?",
            (agent_id, topic_id),
        )

    # ── Index pointers ───────────────────────────────────────────────────────

    async def upsert_index_pointer(self, agent_id: str, pointer: IndexPointer) -> None:
        await self.execute(
            """
            INSERT INTO index_pointers(
                agent_id, topic_id, topic_file_path, summary, confidence,
                pointer_line, last_updated, last_accessed, access_count,
                is_stale, verification_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_id, topic_id) DO UPDATE SET
                topic_file_path = excluded.topic_file_path,
                summary = excluded.summary,
                confidence = excluded.confidence,
                pointer_line = excluded.pointer_line,
                last_updated = excluded.last_updated,
                last_accessed = excluded.last_accessed,
                access_count = excluded.access_count,
                is_stale = excluded.is_stale,
                verification_source = excluded.verification_source
            """,
            (
                agent_id,
                pointer.topic_id,
                pointer.topic_file_path,
                pointer.summary,
                pointer.confidence,
                pointer.pointer_line,
                pointer.last_updated.isoformat(),
                pointer.last_accessed.isoformat() if pointer.last_accessed else None,
                pointer.access_count,
                int(pointer.is_stale),
                pointer.verification_source,
            ),
        )

    async def get_index_pointers(self, agent_id: str) -> list[dict[str, Any]]:
        rows = await self.fetchall(
            "SELECT * FROM index_pointers WHERE agent_id = ? ORDER BY topic_id",
            (agent_id,),
        )
        for row in rows:
            row["is_stale"] = bool(row["is_stale"])
        return rows

    async def delete_index_pointer(self, agent_id: str, topic_id: str) -> None:
        await self.execute(
            "DELETE FROM index_pointers WHERE agent_id = ? AND topic_id = ?",
            (agent_id, topic_id),
        )

    # ── Sessions ─────────────────────────────────────────────────────────────

    async def create_session(self, agent_id: str, session_id: str, started_at: str) -> None:
        await self.execute(
            """
            INSERT OR IGNORE INTO sessions(agent_id, session_id, started_at)
            VALUES (?, ?, ?)
            """,
            (agent_id, session_id, started_at),
        )

    async def end_session(self, agent_id: str, session_id: str, turn_count: int) -> None:
        await self.execute(
            """
            UPDATE sessions
               SET ended_at = ?, turn_count = ?
             WHERE agent_id = ? AND session_id = ?
            """,
            (_now(), turn_count, agent_id, session_id),
        )

    async def count_sessions_since(self, agent_id: str, since_iso: str) -> int:
        value = await self.fetchval(
            """
            SELECT COUNT(*) FROM sessions
             WHERE agent_id = ? AND COALESCE(ended_at, started_at) >= ?
            """,
            (agent_id, since_iso),
        )
        return int(value or 0)

    # ── Dream runs ───────────────────────────────────────────────────────────

    async def create_dream_run(
        self, agent_id: str, run_id: str, trigger: str, started_at: str
    ) -> None:
        await self.execute(
            """
            INSERT INTO dream_runs(agent_id, run_id, trigger, status, started_at)
            VALUES (?, ?, ?, 'running', ?)
            """,
            (agent_id, run_id, trigger, started_at),
        )

    async def update_dream_run(self, agent_id: str, run_id: str, **fields: Any) -> None:
        unknown = set(fields) - DREAM_RUN_FIELDS
        if unknown:
            raise ValidationError(f"Unknown dream_run fields: {sorted(unknown)}")
        updates = [(key, value) for key, value in fields.items() if value is not None]
        if not updates:
            return
        # Column names come exclusively from the whitelist above; values are bound.
        set_clause = ", ".join(f"{key} = ?" for key, _ in updates)
        values = [value for _, value in updates] + [agent_id, run_id]
        await self.execute(
            f"UPDATE dream_runs SET {set_clause} WHERE agent_id = ? AND run_id = ?",
            tuple(values),
        )

    async def get_dream_runs(self, agent_id: str, limit: int = 10) -> list[dict[str, Any]]:
        return await self.fetchall(
            """
            SELECT * FROM dream_runs
             WHERE agent_id = ?
             ORDER BY started_at DESC
             LIMIT ?
            """,
            (agent_id, limit),
        )

    async def get_dream_state(self, agent_id: str) -> dict[str, Any] | None:
        return await self.fetchone("SELECT * FROM dream_state WHERE agent_id = ?", (agent_id,))

    async def upsert_dream_state(
        self,
        agent_id: str,
        last_run_id: str,
        last_consolidated_at: str,
        sessions_since_last: int = 0,
    ) -> None:
        await self.execute(
            """
            INSERT INTO dream_state(
                agent_id, last_run_id, last_consolidated_at, sessions_since_last
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(agent_id) DO UPDATE SET
                last_run_id = excluded.last_run_id,
                last_consolidated_at = excluded.last_consolidated_at,
                sessions_since_last = excluded.sessions_since_last
            """,
            (agent_id, last_run_id, last_consolidated_at, sessions_since_last),
        )

    # ── Usage ────────────────────────────────────────────────────────────────

    async def log_llm_call(
        self,
        agent_id: str,
        provider: str,
        model: str,
        purpose: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        session_id: str | None = None,
        call_id: str | None = None,
    ) -> None:
        await self.execute(
            """
            INSERT INTO llm_calls(
                agent_id, session_id, call_id, provider, model, purpose,
                prompt_tokens, completion_tokens, total_tokens, latency_ms, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                session_id,
                call_id,
                provider,
                model,
                purpose,
                prompt_tokens,
                completion_tokens,
                prompt_tokens + completion_tokens,
                latency_ms,
                _now(),
            ),
        )

    async def get_usage_stats(self, agent_id: str) -> dict[str, Any]:
        row = await self.fetchone(
            """
            SELECT COUNT(*) AS total_calls,
                   COALESCE(SUM(total_tokens), 0) AS total_tokens,
                   COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                   COALESCE(SUM(completion_tokens), 0) AS completion_tokens
              FROM llm_calls
             WHERE agent_id = ?
            """,
            (agent_id,),
        )
        return row or {
            "total_calls": 0,
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
        }
