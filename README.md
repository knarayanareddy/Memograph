# Memograph

A self-healing, bandwidth-aware memory system for AI agents.

Memograph keeps a small `MEMORY.md` index permanently available, stores facts in
on-demand topic files, archives raw transcripts separately, and consolidates
memories under an exclusive lock. SQLite is the source of truth; Markdown and
JSON topic files are generated views that are rebuilt at startup.

> **Status: early alpha.** Core storage, index limits, safe writes, providers,
> consolidation, a CLI, tests, and CI are implemented. Phases 7–10 of the
> original 10-phase roadmap (full framework integrations, REST API, TypeScript
> port, published docs) are deferred. See [docs/ROADMAP.md](docs/ROADMAP.md)
> and [docs/SPEC_STATUS.md](docs/SPEC_STATUS.md).

## Quickstart

Python 3.11+ is required.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # optional; see below
pytest
```

Use the offline provider (`none`) for a first run without any network service:

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

- [Architecture](docs/ARCHITECTURE.md) — canonical design and invariants
- [Roadmap](docs/ROADMAP.md) — honest implementation status
- [Decisions](docs/DECISIONS.md) — why the historical spec was changed
- [Spec status](docs/SPEC_STATUS.md) — review findings and their resolution
- [References](docs/REFERENCES.md) — primary sources for APIs used here
- [Examples](examples/README.md) — runnable offline walkthrough
- [docs/archive/memo.md](docs/archive/memo.md) — archived historical design draft

## Security

Never commit `.env`, database files, or generated memory stores. Untrusted
transcript and LLM text is treated as data: topic IDs are validated, paths are
contained, consolidation output is schema-validated, and no `pickle`
deserialization is used. See [SECURITY.md](SECURITY.md).

## License

MIT — see [LICENSE](LICENSE).
