# Security policy

## Supported versions

The current `main` branch and the active Arena branch receive fixes. This is a
beta project; the REST service is **explicitly single-user** and is not a
multi-tenant authorization boundary.

## Reporting

Please report suspected vulnerabilities privately through GitHub's security
advisory flow for this repository. Include a minimal reproduction, the affected
path, and the impact. Do not include real API keys, npm tokens, or private
memory files.

## Threat model and mitigations

- **Single-user API** uses one high-entropy shared `MEMOGRAPH_API_KEY` for all
  routes and WebSocket handshakes. Per-client keys, scopes, tenants, and
  automatic rotation are intentionally not implemented; `create_app()` refuses
  to start when `MEMOGRAPH_API_SINGLE_USER_MODE` is false. Keys are compared
  with `secrets.compare_digest`.
- **Network defaults** bind to `127.0.0.1`, disable Swagger UI and ReDoc, and
  keep CORS off unless origins are explicitly configured. Operators must
  terminate TLS at a reverse proxy; the TypeScript client requires HTTPS/WSS
  for non-loopback remote endpoints.
- **Resource limits** cap HTTP body bytes, WebSocket subscribers, request rate,
  consolidation rate, LLM output tokens, grep pattern length, and regex match
  time. An in-process sliding-window limiter protects HTTP and WebSocket
  handshakes; replace it with a distributed limiter for multiple workers.
- **Untrusted transcripts and LLM output** are treated as data. Consolidation
  output is parsed into a strict discriminated union; prompt text uses explicit
  untrusted-data delimiters and escapes delimiter characters in stored memory
  and signals.
- **Path traversal** is prevented by `validate_topic_id()` and
  `safe_relative_path()` with `Path.resolve().is_relative_to()`. The TypeScript
  local store uses the same topic ID grammar, `realpath`-based containment, and
  length limits.
- **Prompt injection into writes** is limited because model-produced operations
  cannot supply arbitrary keyword arguments, absolute paths, or unverified
  `VERIFIED` confidence.
- **Concurrent consolidation** uses atomic POSIX `flock`, not PID/mtime files.
- **Partial writes** use temporary files plus `os.replace`/`fsync`; SQLite is
  canonical and generated views are reconciled at startup.
- **Unsafe deserialization** is avoided: vectors and metadata use JSON, never
  `pickle`.
- **SQL injection** is avoided: `update_dream_run()` whitelists column names and
  vector metadata filters are evaluated in Python. Prepared statements are used
  throughout the TypeScript store.
- **Secrets** stay in environment variables or `.env`, which is ignored by Git.
  `.env.example` contains only empty values. Gemini keys are sent in the
  `x-goog-api-key` header, not URL query parameters. PyPI uses OIDC trusted
  publishing; npm publishing requires an `NPM_TOKEN` repository secret.
- **Supply chain** uses SHA-pinned GitHub Actions, `persist-credentials: false`,
  Dependabot, a frozen `uv.lock`/`npm ci`, Bandit, Ruff security rules,
  `npm audit`, and isolated `pip-audit` in CI and pre-commit.
- **Audit logging** emits structured JSON records for authentication failures,
  rate limits, WebSocket lifecycle events, and memory/consolidation writes. No
  request bodies or secrets are logged. Operators should route
  `memograph.audit` logs to their own alerting system.
- **Exceptional conditions** no longer rely on production `assert` statements;
  configuration and lock failures raise explicit exceptions.

## Known dependency exceptions

`chromadb 1.5.9` is the latest release and is pulled in transitively by the
`integrations` extra through CrewAI. It has no patched release for these
advisories:

- `GHSA-f4j7-r4q5-qw2c` / `CVE-2026-45829`
- `GHSA-36p7-vc44-83pf` / `CVE-2026-45833`
- `GHSA-xph7-9rjv-w5fr` / `CVE-2026-45831`
- `GHSA-2wm9-hf6c-p5cr` / `CVE-2026-45830`

Memograph does not run a ChromaDB server, but importing CrewAI loads ChromaDB
modules. Core CI jobs use narrow extras (`dev`, `api`, `docs`); only the real
SDK integration job installs `--all-extras`. The `pip-audit` CI step documents
the four exceptions and must be tightened as soon as patched releases exist.
Do not deploy the `integrations` extra to an untrusted multi-tenant service.

## Operator responsibilities

- Protect the `.memograph/` directory and `memograph.db` with filesystem
  permissions; they contain agent memories and transcripts.
- Use a high-entropy `MEMOGRAPH_API_KEY` of at least 16 characters, rotate it if
  exposed, and terminate TLS at the reverse proxy. Anyone holding the key has
  full access to the configured agent's memory store.
- Configure `MEMOGRAPH_API_CORS_ORIGINS` narrowly; never use `*` with
  credentials.
- Use a provider API key with least privilege and rotate it if exposed.
- Use a distributed rate limiter and event broker when running multiple API
  workers; the built-in limiter and WebSocket broker are process-local.
- Configure PyPI trusted publishing and the `NPM_TOKEN` secret before tagging a
  release.
