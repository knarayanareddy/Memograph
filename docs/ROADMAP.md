# Roadmap status

The archived spec described a 10-phase plan. This table is the honest status of
the current repository. Checkmarks in the historical spec are not reused.

| Phase | Original scope | Status | Notes |
| --- | --- | --- | --- |
| 1 | Foundation: schema, models, config, LLM client, CRUD | Implemented | Canonical `src/memograph/`, SQLite schema, config, providers, `MemoryManager`, CLI |
| 2 | Memory layer: index engine, topic manager, caching | Implemented | Index/topic logic consolidated into `MemoryManager`; hard limits enforced in `models.py` |
| 3 | AutoDream: gates, lock, four-phase engine, daemon | Partially implemented | Gates, atomic lock, schema-validated engine, and `dream_now()` exist; no long-running daemon |
| 4 | Context injection: token budgeting, formatter | Partially implemented | Conservative `TokenBudgetManager` and skeptical framing; no streaming updater |
| 5 | Relevance: semantic search and embeddings | Partially implemented | Keyword recall plus a safe SQLite vector store; no FAISS or embedding providers |
| 6 | Verification: staleness, skeptical memory | Partially implemented | Local `VerificationEngine` marks missing hints stale; no LLM verifier or decay model |
| 7 | Adapters: LangChain, CrewAI, AutoGen, raw API | Implemented | Thin stable-ID adapters plus real optional SDK integrations in `memograph.integrations` |
| 8 | CLI: status dashboard, interactive recall | Implemented | `memograph`, `python -m memograph`, JSON CLI output, and the authenticated `memograph-api` service |
| 9 | REST API: FastAPI, WebSocket, API keys | Implemented | FastAPI app factory, API-key auth, rate limiting, deny-by-default CORS, OpenAPI, `/events` WebSocket |
| 10 | SDK/docs: publish package, TypeScript port, full docs | Implemented | `uv.lock`, `memograph-sdk`, MkDocs/Pages, API reference from docstrings, PyPI/npm/GitHub release workflows |

## Production hardening still ahead

These are follow-up hardening items, not unimplemented phases of the original
10-phase plan:

1. Add a long-running consolidation daemon with graceful shutdown.
2. Add embedding providers and hybrid ranking behind explicit optional extras.
3. Add LLM-backed verification with an immutable audit log.
4. Add streaming context updates and multiple formatting strategies.
5. Add distributed rate limiting and centralized audit logging for the REST API.
