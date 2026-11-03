# REST API

The optional API extra installs FastAPI, uvicorn, and websockets:

```bash
pip install -e ".[api]"
export MEMOGRAPH_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
memograph-api --host 127.0.0.1 --port 8000
```

`python -m memograph.api` is equivalent to `memograph-api`.

## Single-user authentication

This service is **explicitly single-user**. One shared, high-entropy API key
grants full access to the configured agent's memory store; there are no
per-client scopes, tenants, or automatic rotation. Per-client authorization is
not implemented, and `create_app()` refuses to start when
`MEMOGRAPH_API_SINGLE_USER_MODE` is false. Do not expose one instance to
multiple mutually untrusted clients.

Every memory route and the `/events` WebSocket require the configured secret in
either header:

```text
X-API-Key: <secret>
Authorization: Bearer <secret>
```

Comparison uses `secrets.compare_digest`. `create_app()` refuses to start when
`MEMOGRAPH_API_KEY` is empty; keys shorter than 16 characters are rejected.
Only `GET /health` and `GET /openapi.json` are public. Swagger UI and ReDoc are
disabled; this site is the canonical docs. `GET /health` reports
`"auth_model": "single-user-shared-key"`.

## Defaults and limits

| Setting | Default | Environment variable |
| --- | --- | --- |
| Host | `127.0.0.1` | `MEMOGRAPH_API_HOST` |
| Port | `8000` | `MEMOGRAPH_API_PORT` |
| Base path | `.memograph` | `MEMOGRAPH_BASE_PATH` |
| Agent ID | `default` | `MEMOGRAPH_AGENT_ID` |
| LLM provider | `none` | `MEMOGRAPH_LLM_PROVIDER` |
| Single-user mode | `true` | `MEMOGRAPH_API_SINGLE_USER_MODE` |
| Rate limit | `60`/minute/key | `MEMOGRAPH_API_RATE_LIMIT_PER_MINUTE` |
| Consolidation rate limit | `6`/minute/key | `MEMOGRAPH_API_DREAM_RATE_LIMIT_PER_MINUTE` |
| Max request body | `1048576` bytes | `MEMOGRAPH_API_MAX_REQUEST_BYTES` |
| Max WebSocket connections | `100` | `MEMOGRAPH_API_MAX_WEBSOCKET_CONNECTIONS` |
| Max consolidation LLM tokens | `2048` | `MEMOGRAPH_API_MAX_LLM_TOKENS` |
| CORS origins | none | `MEMOGRAPH_API_CORS_ORIGINS` |
| Log level | `info` | `MEMOGRAPH_API_LOG_LEVEL` |

`MEMOGRAPH_API_CORS_ORIGINS` accepts a comma-separated list or a JSON list.
CORS middleware is not added unless at least one origin is configured. HTTP
responses include an `X-Request-ID` header; structured `memograph.audit` JSON
logs record auth failures, rate limits, WebSocket lifecycle events, and memory
writes without logging request bodies or secrets. The limiter and event broker
are process-local; use a distributed equivalent for multiple workers.

Terminate TLS at a reverse proxy for remote access. The TypeScript client
requires HTTPS/WSS for non-loopback remote endpoints.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness probe and auth model |
| `GET` | `/openapi.json` | OpenAPI schema |
| `GET` | `/status` | Provider, topics, index, consolidation, usage |
| `POST` | `/remember` | Store a fact |
| `GET` | `/recall` | Recall matching topics |
| `POST` | `/forget` | Forget a fact or topic |
| `POST` | `/update` | Update fact content or confidence |
| `POST` | `/context` | Build a bandwidth-aware context window |
| `POST` | `/dream` | Run consolidation |
| `POST` | `/prune` | Remove empty index pointers |
| `GET` | `/index` | Return generated `MEMORY.md` |
| `POST` | `/grep` | Search archived transcript turns |
| `WS` | `/events` | Stream JSON memory events |

Example:

```bash
curl -H "X-API-Key: $MEMOGRAPH_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"topic_id":"project_stack","content":"Uses FastAPI","source":"curl"}' \
  http://localhost:8000/remember
```

## WebSocket events

The WebSocket path is `/events`. Send the API key in the handshake headers.
Messages have the shape:

```json
{
  "type": "memory.remembered",
  "payload": {"topic_id": "project_stack", "fact_id": "fact_..."},
  "timestamp": "2026-11-03T09:00:00+00:00"
}
```

Event types include `memory.remembered`, `memory.forgotten`, `memory.updated`,
`consolidation.completed`, and `memory.pruned`. The TypeScript SDK exposes an
async iterator over this stream. Connections are capped by
`MEMOGRAPH_API_MAX_WEBSOCKET_CONNECTIONS`.

See the [Python API reference](api.md) for `create_app` and `APISettings`.
