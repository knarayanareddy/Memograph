# Review findings and resolution

| # | Finding | Resolution | Primary paths / tests |
| --- | --- | --- | --- |
| 1 | No runnable package | Added an installable `src/` package, CLI, config, DB, models, providers, manager, REST API, TypeScript SDK, and runnable examples | `pyproject.toml`, `src/memograph/`, `sdk/typescript/`, `examples/`, `tests/test_packaging.py` |
| 2 | Contradictory duplicate specs | One canonical model/manager/lock/gate design; historical spec archived | `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/archive/memo.md` |
| 3 | Non-atomic PID/mtime lock | Atomic `flock`; timestamp moved to SQLite | `src/memograph/consolidation/lock.py`, `tests/test_lock.py` |
| 4 | Failed runs marked successful | Failed runs re-raise and never advance `dream_state` | `src/memograph/consolidation/engine.py`, `tests/test_dream_engine.py` |
| 5 | `topic_id` path traversal | Strict ID grammar and `is_relative_to` containment everywhere | `src/memograph/validation.py`, `src/memograph/memory_manager.py`, `tests/test_validation.py` |
| 6 | Unvalidated LLM operations | Strict discriminated-union plan; no `**params`; verified promotions require evidence | `src/memograph/consolidation/schema.py`, `tests/test_consolidation_schema.py` |
| 7 | Non-atomic strict writes | `os.replace` + `fsync`, DB transaction, startup reconciliation | `src/memograph/atomic.py`, `src/memograph/memory_manager.py`, `tests/test_atomic.py` |
| 8 | Missing/incorrect dependencies and extras | Declared all runtime deps, real optional extras, and a reproducible `uv.lock` | `pyproject.toml`, `uv.lock`, `tests/test_packaging.py` |
| 9 | No executable tests or CI | Real pytest suite, integration marker, TypeScript `node:test` suite, docs build, release workflows, and Python 3.11–3.13 CI | `tests/`, `sdk/typescript/src/*.test.ts`, `.github/workflows/` |
| 10 | Misleading README and ✅ checklists | Honest beta status, quickstart, roadmap, REST/integration/TypeScript docs, and spec status | `README.md`, `docs/ROADMAP.md`, `docs/SPEC_STATUS.md` |
| 11 | Un-fenced 27k-line spec + duplicate PDF | Short canonical docs; archived markdown; PDF removed | `docs/`, `docs/archive/memo.md`, `.gitignore` |
| 12 | No ignore/env/license/contribution hygiene | Added repository scaffolding, API-key template, secret guidance, and release docs | `.gitignore`, `.env.example`, `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md` |
| 13 | Index limits not enforced | Hard line/byte/char limits with computed pointer lines | `src/memograph/models.py`, `sdk/typescript/src/local.ts`, `tests/test_models.py` |
| 14 | `pickle.load` and SQL interpolation | JSON vector storage and Python-side metadata filters | `src/memograph/vector_store.py`, `tests/test_vector_store.py` |
| 15 | Unverifiable provenance claims | Independent design language and primary references | `docs/DECISIONS.md`, `docs/REFERENCES.md`, `tests/test_docs.py` |
| 16 | `hash()` used for persistent IDs | SHA-256-based `stable_id()` in adapters, integrations, runs, and TypeScript | `src/memograph/validation.py`, `src/memograph/adapters.py`, `sdk/typescript/src/validation.ts`, `tests/test_adapters.py` |
| 17 | No dependency lockfile | Added `uv.lock`; CI installs with `uv sync --frozen` | `uv.lock`, `.github/workflows/ci.yml` |
| 18 | Deferred Phases 7–10 | Implemented real SDK integrations, REST/WebSocket API, TypeScript SDK, published docs, and release automation | `src/memograph/api/`, `src/memograph/integrations/`, `sdk/typescript/`, `mkdocs.yml`, `.github/workflows/release.yml` |

## Resolved in 0.2.0

Framework SDK integrations, the authenticated REST API, the TypeScript SDK,
published MkDocs documentation, release automation, and the Python lockfile are
no longer deferred. See [ROADMAP.md](ROADMAP.md) for the remaining production
hardening backlog.
