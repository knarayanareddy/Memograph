# Roadmap status

The archived spec described a 10-phase plan. This table is the honest status of
the current repository. Checkmarks in the historical spec are not reused.

| Phase | Original scope | Status | Notes |
| --- | --- | --- | --- |
| 1 | Foundation: schema, models, config, LLM client, CRUD | Implemented | Canonical `src/memograph/`, SQLite schema, config, providers, `MemoryManager`, CLI |
| 2 | Memory layer: index engine, topic manager, caching | Implemented | Index/topic logic consolidated into `MemoryManager`; hard limits enforced in `models.py` |
| 3 | AutoDream: gates, lock, four-phase engine, daemon | Partially implemented | Gates, atomic lock, schema-validated engine, and `dream_now()` exist; no long-running daemon |
| 4 | Context injection: token budgeting, formatter | Partially implemented | Conservative `TokenBudgetManager` and skeptical framing; no streaming updater or multiple formatting strategies |
| 5 | Relevance: semantic search and embeddings | Partially implemented | Keyword recall plus a safe SQLite vector store; no FAISS, embedding providers, clustering, or cross-session semantic search |
| 6 | Verification: staleness, skeptical memory | Partially implemented | Local `VerificationEngine` marks missing hints stale; no LLM verifier, scheduler, audit log, or decay model |
| 7 | Adapters: LangChain, CrewAI, AutoGen, raw API | Partially implemented | Thin wrappers in `adapters.py` with stable IDs; no optional framework integrations |
| 8 | CLI: status dashboard, interactive recall | Implemented | `memograph` entry point and `python -m memograph`; non-interactive JSON output |
| 9 | REST API: FastAPI, WebSocket, API keys | Deferred | Not implemented; plan an authenticated API only after the core stabilizes |
| 10 | SDK/docs: publish package, TypeScript port, full docs | Deferred | Packaging, CI, and canonical docs exist; no release automation or TypeScript port |

## Immediate next work

1. Add a long-running consolidation daemon with graceful shutdown.
2. Add embedding providers and hybrid ranking behind explicit optional extras.
3. Add LLM-backed verification with an immutable audit log.
4. Add a REST API only with authentication, rate limits, and CORS defaults.
5. Publish releases and generate API documentation from docstrings.
