# Changelog

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
