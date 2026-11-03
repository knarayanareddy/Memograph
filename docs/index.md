# Memograph

Memograph is a self-healing, bandwidth-aware memory system for AI agents.
SQLite is the canonical store; `MEMORY.md` and topic files are generated views.

## Start here

- [Quickstart and project overview](https://github.com/knarayanareddy/Memograph#quickstart)
- [Architecture](ARCHITECTURE.md)
- [REST API](REST_API.md)
- [Framework integrations](INTEGRATIONS.md)
- [TypeScript SDK](TYPESCRIPT.md)
- [Python API reference](api.md)

## Status

Core storage, consolidation, CLI, REST/WebSocket API, real framework SDK
integrations, TypeScript SDK, published docs, release automation, tests, CI,
and a reproducible `uv.lock` are implemented. See [Roadmap](ROADMAP.md) and
[Spec status](SPEC_STATUS.md) for details and the remaining production
hardening backlog.

## Design principles

- One canonical architecture; the historical 27,000-line draft is archived.
- Atomic writes and startup reconciliation from SQLite.
- Strict validation of IDs, paths, and LLM output.
- SHA-256 stable IDs and no `pickle` deserialization.
- Secure-by-default API: required API key, deny-by-default CORS, rate limits.
