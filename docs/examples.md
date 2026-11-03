# Examples

## Python offline quickstart

[`examples/quickstart.py`](https://github.com/knarayanareddy/Memograph/blob/main/examples/quickstart.py)
uses the `none` provider and a temporary directory. It creates a fact, recalls
it, builds context, prints status, runs consolidation, and cleans up.

```bash
python examples/quickstart.py
# or
make example
```

## REST API

Start the service, then use `curl`:

```bash
export MEMOGRAPH_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
memograph-api --port 8000

curl -H "X-API-Key: $MEMOGRAPH_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"topic_id":"project_stack","content":"Uses FastAPI","source":"curl"}' \
  http://localhost:8000/remember
```

See [REST API](REST_API.md) for every endpoint and the WebSocket event stream.

## TypeScript

```bash
cd sdk/typescript
npm ci
npm test
```

See [TypeScript SDK](TYPESCRIPT.md) for client and local-store snippets.

## Framework SDKs

See [Integrations](INTEGRATIONS.md) for LangChain, CrewAI, and AutoGen examples
that use the real optional SDK packages.
