# Changelog

## Unreleased — security hardening

- Documented and enforced the REST service as an explicitly single-user,
  shared-key application; added a startup gate against unimplemented
  per-client authorization and required a 16-character minimum API key.
- Changed the API default bind host to `127.0.0.1`, added structured JSON audit
  logging, request IDs, hard HTTP body limits, WebSocket connection caps,
  separate consolidation quotas, and configurable LLM token limits.
- Replaced Python `re` with timeout-capable `regex` for caller-supplied grep
  patterns, capped pattern length, escaped consolidation prompt delimiters, and
  removed production `assert` statements.
- Moved Gemini API keys from URL query parameters to the `x-goog-api-key`
  header and added validation for provider base URLs.
- Aligned TypeScript validation with Python limits, added `realpath`-based path
  containment, HTTPS/WSS enforcement for remote clients, bounded transcript
  grep patterns/results, and Node 26/TypeScript 7 toolchain updates.
- SHA-pinned GitHub Actions, disabled persisted checkout credentials, enabled
  Dependabot, added Bandit/Ruff-security/npm-audit/isolated pip-audit scans,
  and documented unpatched ChromaDB advisories with explicit audit exceptions.
- Narrowed core CI installs to `dev`/`api`/`docs` extras, isolated `--all-extras`
  to the real SDK integration job, updated Node/Python/action versions, and
  upgraded the locked `pyarrow` to 26.0.1 without disrupting CrewAI.

## 0.2.0 — APIs, SDKs, docs, and reproducible releases

- Added an optional FastAPI REST/WebSocket service with required API-key auth,
  constant-time comparison, rate limiting, deny-by-default CORS, OpenAPI, and
  memory event streaming.
- Added real optional LangChain, CrewAI, and AutoGen integrations in
  `memograph.integrations`, with a dedicated event-loop bridge for synchronous
  SDKs and integration tests marked `integration`.
- Added `memograph-sdk`: a typed REST/WebSocket client and a standalone
  SQLite-backed `LocalMemograph` for Node.js 22.5+ using `node:sqlite`.
- Added `uv.lock` and switched CI to `uv sync --frozen` for reproducible Python
  installs.
- Added MkDocs/Material published docs, generated Python API reference, GitHub
  Pages deployment, and tag-triggered PyPI/npm/GitHub release workflows.
- Added new ADRs, REST/integration/TypeScript/releasing docs, updated roadmap
  and spec status, and expanded packaging/tests/hygiene for all new surfaces.

## 0.1.0 — Canonical implementation

- Added an installable Python package with one canonical architecture.
- Added SQLite persistence, generated `MEMORY.md`, atomic topic/index writes,
  and startup reconciliation.
- Added strict topic-ID/path validation and SHA-256 stable IDs.
- Added `httpx` providers for Ollama, OpenAI-compatible endpoints, Anthropic,
  Gemini, and an offline `none` provider.
- Added exclusive `flock`-based consolidation with cheapest-first gates, strict
  LLM operation schemas, and failure-aware `dream_state` updates.
- Added conservative bandwidth-aware context injection and lightweight
  skeptical verification.
- Added a JSON-based SQLite vector store with no `pickle` or dynamic SQL.
- Added CLI, a runnable offline example, full pytest suite, Ruff/mypy
  configuration, and CI.
- Rewrote the README and added canonical docs, roadmap, ADRs, references,
  license, security policy, contribution guide, and `.gitignore`.
- Archived the historical un-fenced `memo.md` and removed its duplicate PDF.
