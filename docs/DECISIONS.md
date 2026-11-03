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

## ADR 7 — One HTTP client, real optional extras

All providers use `httpx`, which is a declared core dependency. Optional
extras now exist for the REST API, real framework SDKs, docs, development, and
the combined `all` extra. Provider errors never point at undefined extras.

## ADR 8 — Conservative token budgeting

Unknown models get a conservative 8,192-token default, not the largest value
from a hard-coded registry. Callers can override the size explicitly. This
avoids silent context overflow as model catalogs change.

## ADR 9 — Stable identifiers

`stable_id()` uses SHA-256. Python's `hash()` is randomized per process and was
used for persistent topic IDs in the historical adapters. The TypeScript SDK
uses the same SHA-256-based scheme.

## ADR 10 — Reviewable docs and honest provenance

The 507-page PDF duplicated the un-fenced `memo.md` almost exactly. It is
removed; the historical markdown is archived and clearly marked superseded.
Canonical docs are short, fenced, diffable, and generated into a published
MkDocs site. Claims based on unverifiable third-party material are replaced with
an independent design description and links to primary API documentation in
[REFERENCES.md](REFERENCES.md).

## ADR 11 — The REST API is opt-in and authenticated by default

`memograph.api` is not imported by the core package. FastAPI, uvicorn, and
websockets live in the `api` extra. `create_app()` refuses to start without
`MEMOGRAPH_API_KEY`; CORS is disabled unless origins are explicitly configured;
an in-process sliding-window limiter protects HTTP and WebSocket handshakes.
Only `/health` and `/openapi.json` are public. Swagger UI and ReDoc are disabled
because the published MkDocs site is the canonical documentation.

## ADR 12 — Real framework integrations use a dedicated event-loop thread

LangChain and CrewAI expose synchronous memory interfaces, while `aiosqlite`
binds `MemoryManager` to one event loop. `AsyncBridge` owns one background loop
for each adapter instance, so all database operations stay on the loop that
opened the database. AutoGen is async and uses the caller's loop directly. The
real SDK packages are declared in the `integrations` extra and installed in CI.

## ADR 13 — TypeScript parity is split into a client and a local store

`MemographClient` covers the REST API and WebSocket events. `LocalMemograph`
reimplements the core SQLite-backed store, generated views, index limits,
transcripts, and offline consolidation for Node.js 22, 24, and 26 using
`node:sqlite`. This avoids bundling a Python runtime while keeping the same
validation, bounded grep, `realpath` path containment, and stable-ID rules.

## ADR 14 — `uv.lock` is the canonical Python lock

A single `uv.lock` resolves every declared extra. CI uses `uv sync --frozen`
instead of installing floating minimum versions; core jobs select narrow
extras and only the real SDK integration job installs `--all-extras`. This makes
Python 3.11–3.13 runs reproducible without a separate `requirements-dev.txt`.

## ADR 15 — Releases use trusted publishing

PyPI publishing uses OIDC trusted publishing with `id-token: write`; no PyPI
password is stored in the repository. npm publishing uses `NPM_TOKEN` and
`--provenance`. GitHub releases are generated from tags. All three workflows
are tag-triggered, never auto-merged, and never run on pull requests.
