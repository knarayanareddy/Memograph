# Architecture

This document is the canonical architecture. The historical 27,000-line design
export is archived at [archive/memo.md](archive/memo.md) and is **not** a source
of implementation truth.

## Layers

1. **Index** — `MEMORY.md` is generated from `index_pointers` in SQLite. It is
   always available to the agent and is capped at 200 lines, 25,600 UTF-8
   bytes, and 150 characters per pointer line.
2. **Topic files** — `topics/<topic_id>.json` is the machine-readable view and
   `topics/<topic_id>.md` is the human/LLM-readable view. They are loaded only
   when their pointer is relevant.
3. **Transcripts** — `transcripts/<session_id>.jsonl` stores raw turns. The
   context builder never injects a whole transcript; `grep_transcripts()` and
   `recent_signals()` return bounded snippets.

SQLite (`memograph.db`) is the single source of truth. At startup,
`MemoryManager.reconcile()` regenerates all derived JSON/Markdown files from the
database and removes orphaned topic files. This makes a crash during file
replacement recoverable.

## Write discipline

`MemoryManager._save_topic_unlocked()` enforces the core axiom:

1. Build the new `TopicFile` and `MemoryIndex` in memory.
2. Validate index line/byte limits.
3. Atomically write topic JSON, then topic Markdown, then `MEMORY.md`.
4. Commit topic rows, fact rows, and the index pointer in one
   `BEGIN IMMEDIATE` transaction.
5. If any file write or DB commit fails, rebuild the derived views from SQLite.

No `memory_index.json` exists: the earlier spec alternated between JSON and
SQLite as the index store, which was a contradiction.

## Concurrency and consolidation

`ConsolidationLock` uses POSIX `flock` on an open file descriptor. It does not
use PID files, mtimes, or a check-then-write race. The lock file has no semantic
timestamp; `dream_state.last_consolidated_at` in SQLite is the only gate
timestamp. A failed dream run marks `dream_runs.status = 'failed'` and
deliberately does **not** advance `dream_state`.

Consolidation gates are cheapest-first: scan interval, elapsed time, session
count, then lock availability. The final `acquire()` is atomic regardless of the
earlier advisory check.

LLM consolidation output is untrusted. `parse_consolidation_plan()` accepts only
a strict discriminated union of `merge`, `resolve_contradiction`, `promote`, and
`create`. It rejects unknown fields, invalid topic IDs, unknown actions, and
`verified` promotions without a `verification_source`. The engine never passes
`**params` from a model into application code.

## Validation and path safety

`validation.validate_topic_id()` permits only `^[a-z][a-z0-9_]{0,49}$`.
`safe_relative_path()` resolves a candidate under a base directory and rejects
absolute paths, `..`, and symlink escapes. All topic, transcript, and index
paths go through these helpers.

Persistent IDs use SHA-256 (`stable_id()`), never Python's per-process
`hash()`.

## Context injection

`TokenBudgetManager` uses a conservative 8,192-token default and a 2,048-token
output reservation, or an explicit caller override. It does not guess a large
context window from a hard-coded model registry. The index is always included;
topic files are added and truncated to fit. When `skeptical_mode` is enabled,
the generated context begins with a notice that memories are hints to verify,
not ground truth.

## Providers

`create_provider()` builds an `httpx`-based provider from one flat
`MemoGraphConfig`. Ollama, OpenAI-compatible endpoints, Anthropic, Gemini, and
an offline `none` provider are supported. Provider error messages never point at
undefined optional-dependency extras.

## Vector store

`SQLiteVectorStore` stores vectors and metadata as JSON. Metadata filters are
applied in Python, never interpolated into SQL. There is no `pickle` and no
`faiss` dependency.

## Tests and CI

`tests/` covers validation, models, atomic writes, the database, the manager,
the lock, gates, consolidation parsing/execution, providers, context injection,
the vector store, adapters, packaging, docs, and the CLI.
`.github/workflows/ci.yml` runs Ruff, mypy, pytest with coverage, and a package
build on Python 3.11–3.13.
