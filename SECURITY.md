# Security policy

## Supported versions

The current `main` branch and the active Arena branch receive fixes. This is a
beta project; do not use it as an authorization boundary.

## Reporting

Please report suspected vulnerabilities privately through GitHub's security
advisory flow for this repository. Include a minimal reproduction, the affected
path, and the impact. Do not include real API keys, npm tokens, or private
memory files.

## Threat model and mitigations

- **Untrusted transcripts and LLM output** are treated as data. Consolidation
  output is parsed into a strict discriminated union; prompt text uses explicit
  untrusted-data delimiters.
- **Path traversal** is prevented by `validate_topic_id()` and
  `safe_relative_path()` with `Path.resolve().is_relative_to()`. The TypeScript
  local store uses the same topic ID grammar and a contained-path helper.
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
- **REST API** requires `MEMOGRAPH_API_KEY`; keys are compared with
  `secrets.compare_digest`. CORS is disabled unless origins are explicitly
  configured, and an in-process sliding-window limiter protects HTTP and
  WebSocket handshakes. Swagger UI and ReDoc are disabled.
- **WebSocket events** use the same API key as HTTP, sent in handshake headers
  rather than the URL. The TypeScript client does not put the key in query
  parameters.
- **Secrets** stay in environment variables or `.env`, which is ignored by Git.
  `.env.example` contains only empty values. PyPI uses OIDC trusted publishing;
  npm publishing requires an `NPM_TOKEN` repository secret.

## Operator responsibilities

- Protect the `.memograph/` directory and `memograph.db` with filesystem
  permissions; they contain agent memories and transcripts.
- Use a high-entropy `MEMOGRAPH_API_KEY`, rotate it if exposed, and terminate
  TLS at the reverse proxy.
- Configure `MEMOGRAPH_API_CORS_ORIGINS` narrowly; never use `*` with
  credentials.
- Use a provider API key with least privilege and rotate it if exposed.
- Replace the in-process rate limiter with a distributed limiter when running
  multiple API workers.
- Configure PyPI trusted publishing and the `NPM_TOKEN` secret before tagging a
  release.
