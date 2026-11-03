# Architecture decisions

## ADR 1 — SQLite is canonical; generated files are views

The historical spec defined both `memory_index.json` and a SQLite index, with
four incompatible `MemoryManager` implementations. We keep SQLite as the only
source of truth and regenerate `MEMORY.md` and topic files on startup. This
gives us transactions, foreign keys, WAL, and crash recovery.

## ADR 2 — Replace the mtime/PID lock with `flock`

The old lock checked availability and then opened the lock file for writing:
two daemons could both proceed. It also treated the file mtime as
`lastConsolidatedAt`, used `os.kill(pid, 0)`, and restored an old mtime while
leaving the current PID in the file. We use an atomic advisory `flock`, and
store `last_consolidated_at` in `dream_state`.

## ADR 3 — A failed dream is a failed dream

The old engine caught phase errors, returned normally from inside the lock
context manager, and thereby updated the lock mtime to “now” while leaving the
DB state unchanged. The new engine marks the run failed, re-raises, and only
upserts `dream_state` after successful completion.

## ADR 4 — Validate all model output

Consolidation output is parsed into a strict Pydantic discriminated union. No
arbitrary keyword dictionaries are forwarded to `remember()`. Transcripts and
index content are delimited as untrusted data in prompts. Topic IDs and paths
are validated at every boundary.

## ADR 5 — Atomic writes and startup reconciliation

All derived files use a temporary file plus `os.replace` and `fsync`. Multi-table
DB writes use `BEGIN IMMEDIATE`. If either side fails, `reconcile()` rebuilds
views from the canonical DB. This replaces sequential truncating writes with no
rollback.

## ADR 6 — No `pickle`, no dynamic SQL

Vector metadata is JSON. Metadata filtering happens in Python. This removes the
`.meta.pkl` code-execution risk and the `json_extract(metadata, '$.{key}')`
string-interpolation risk.

## ADR 7 — One HTTP client, no phantom extras

All providers use `httpx`, which is a declared core dependency. The old
`pyproject.toml` omitted `pydantic-settings`, `aiosqlite`, and `httpx`, while
provider errors referenced extras such as `memograph[anthropic]` that did not
exist.

## ADR 8 — Conservative token budgeting

Unknown models get a conservative 8,192-token default, not the largest value
from a hard-coded registry. Callers can override the size explicitly. This
avoids silent context overflow as model catalogs change.

## ADR 9 — Stable identifiers

`stable_id()` uses SHA-256. Python's `hash()` is randomized per process and was
used for persistent topic IDs in the historical adapters.

## ADR 10 — Reviewable docs and honest provenance

The 507-page PDF duplicated the un-fenced `memo.md` almost exactly. It is
removed; the historical markdown is archived and clearly marked superseded.
Canonical docs are short, fenced, and diffable. Claims based on unverifiable third-party material are replaced with an
independent design description and links to primary API documentation in
[REFERENCES.md](REFERENCES.md).
