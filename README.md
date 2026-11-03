# Memograph

A self-healing, bandwidth-aware memory system for AI agents.

Memograph keeps a small `MEMORY.md` index permanently available, stores facts in
on-demand topic files, archives raw transcripts separately, and consolidates
memories under an exclusive lock. SQLite is the source of truth; Markdown and
JSON topic files are generated views that are rebuilt at startup.

> **Status: beta.** Core storage, index limits, safe writes, providers,
> consolidation, a CLI, an authenticated REST/WebSocket API, real framework SDK
> integrations, a TypeScript SDK, published docs, release automation, tests,
> CI, and a reproducible `uv.lock` are implemented. Phases 7–10 of the original
> 10-phase roadmap are no longer deferred. See [docs/ROADMAP.md](docs/ROADMAP.md)
> and [docs/SPEC_STATUS.md](docs/SPEC_STATUS.md).

## Quickstart

Python 3.11–3.13 is supported. The offline provider (`none`) needs no API key.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # optional; see below
pytest -m "not integration"
```

For a fully locked environment with every optional extra, use
[Astral uv](https://docs.astral.sh/uv/):

```bash
uv sync --all-extras --frozen
uv run --no-sync pytest -m "not integration"
```

Use the CLI without any network service:

```bash
memograph --provider none status
memograph --provider none remember project_stack "Uses FastAPI and SQLite" --source readme
memograph --provider none recall "What framework?"
memograph --provider none index
memograph --provider none dream --force
```

`python -m memograph` is equivalent to the `memograph` entry point.

## Python API

```python
import asyncio
from memograph import MemoGraph, MemoGraphConfig, LLMProvider

async def main():
    config = MemoGraphConfig(
        base_path=".memograph",
        llm_provider=LLMProvider.NONE,  # no network required
    )
    async with MemoGraph(config=config) as mg:
        await mg.remember(
            "project_stack",
            "Uses FastAPI and SQLite",
            source="readme",
        )
        topics = await mg.recall("What framework?")
        context = await mg.build_context("What framework?")
        print(context.text)
        print(await mg.status())

asyncio.run(main())
```

## REST API

Install the API extra and set a shared secret before starting the service:

```bash
pip install -e ".[api]"
export MEMOGRAPH_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
memograph-api --host 0.0.0.0 --port 8000
```

Every memory route and the `/events` WebSocket require `X-API-Key` or
`Authorization: Bearer`. CORS is off by default, and requests are rate-limited.
See [docs/REST_API.md](docs/REST_API.md).

## Framework integrations

Install real SDK integrations with `pip install -e ".[integrations]"`.
`memograph.integrations` provides LangChain chat history, a CrewAI storage
backend and task-output adapter, and an AutoGen message memory. See
[docs/INTEGRATIONS.md](docs/INTEGRATIONS.md).

## TypeScript SDK

`sdk/typescript` contains `MemographClient` for the REST/WebSocket service and
`LocalMemograph`, a standalone SQLite-backed store. Node.js 22.5+ is required.

```bash
cd sdk/typescript
npm ci
npm test
```

See [docs/TYPESCRIPT.md](docs/TYPESCRIPT.md).

## Providers

All providers use `httpx` directly; there are no hidden SDK extras.

| Provider | Environment variable | Notes |
| --- | --- | --- |
| `ollama` | none | Local Ollama at `http://localhost:11434` by default |
| `openai` | `OPENAI_API_KEY` | Chat Completions-compatible |
| `groq` | `GROQ_API_KEY` | Chat Completions-compatible |
| `custom` | `CUSTOM_API_KEY` / `MEMOGRAPH_CUSTOM_API_KEY` | Set `MEMOGRAPH_CUSTOM_BASE_URL` |
| `anthropic` | `ANTHROPIC_API_KEY` | Messages API |
| `gemini` | `GOOGLE_API_KEY` | `generateContent` API |
| `none` | none | Offline; returns an empty consolidation plan |

Library settings use the `MEMOGRAPH_` prefix, for example
`MEMOGRAPH_LLM_PROVIDER=none` or `MEMOGRAPH_BASE_PATH=.memograph`.
See [.env.example](.env.example) for the full template.

## Documentation

The published site is at
<https://knarayanareddy.github.io/Memograph/>.

- [Architecture](docs/ARCHITECTURE.md) — canonical design and invariants
- [Roadmap](docs/ROADMAP.md) — honest implementation status
- [Decisions](docs/DECISIONS.md) — ADRs
- [Spec status](docs/SPEC_STATUS.md) — review findings and resolution
- [REST API](docs/REST_API.md) — authenticated service and WebSocket events
- [Integrations](docs/INTEGRATIONS.md) — LangChain, CrewAI, AutoGen
- [TypeScript SDK](docs/TYPESCRIPT.md) — client and local store
- [Releasing](docs/RELEASING.md) — PyPI/npm/GitHub release process
- [References](docs/REFERENCES.md) — primary sources
- [Examples](examples/README.md) — runnable offline walkthrough
- [docs/archive/memo.md](docs/archive/memo.md) — archived historical design draft

## Security

Never commit `.env`, database files, generated memory stores, API keys, or npm
tokens. The REST API requires a configured key by default; WebSocket handshakes
use the same key; CORS is deny-by-default. Untrusted transcript and LLM text is
treated as data: topic IDs are validated, paths are contained, consolidation
output is schema-validated, and no `pickle` deserialization is used. See
[SECURITY.md](SECURITY.md).

## License

MIT — see [LICENSE](LICENSE).
