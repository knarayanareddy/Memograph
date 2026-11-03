# Contributing

## Setup

For core development:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

For the exact CI environment, including API, real framework SDKs, docs, and the
TypeScript toolchain, use the lockfile:

```bash
uv sync --all-extras --frozen
npm ci --prefix sdk/typescript
```

Set `MEMOGRAPH_API_KEY` before running `memograph-api` or the REST API tests
explicitly. `.env.example` contains only empty secret values.

## Checks

```bash
make lint
make typecheck
make test
make test-integration
make docs-build
make ts-test
make build
```

Or run the all-in-one release check:

```bash
make release-check
```

Individual commands:

```bash
ruff check .
ruff format --check .
mypy
pytest --cov=memograph --cov-report=term-missing -m "not integration"
pytest -q -m integration
mkdocs build --strict
npm test --prefix sdk/typescript
python -m build
```

All checks run in CI on Python 3.11, 3.12, 3.13 and Node.js 22. The
`integration` marker selects tests that import real LangChain, CrewAI, and
AutoGen packages.

## Guidelines

- Keep SQLite as the source of truth; never make a generated Markdown/JSON file
  authoritative.
- Route every path derived from user, transcript, or model input through
  `memograph.validation` or the TypeScript `assertTopicId`/`safePath` helpers.
- Keep LLM output behind a strict Pydantic schema. Never pass arbitrary model
  dictionaries as `**kwargs`.
- Keep the REST API authenticated by default; CORS is opt-in.
- Add a regression test for every bug fix, especially concurrency, path
  containment, index limits, auth, rate limits, and failure/rollback behavior.
- Add a TypeScript test for SDK or local-store behavior changes.
- Do not commit `.env`, databases, generated memory stores, API keys, npm
  tokens, `node_modules/`, `dist/`, or `site/`.
- Update `docs/ROADMAP.md` and `docs/SPEC_STATUS.md` when implementation status
  changes; keep `uv.lock` and `sdk/typescript/package-lock.json` in sync with
  dependency changes.
- Prefer small, descriptive commits. Do not commit generated PDFs or binaries.

## Reporting security issues

See [SECURITY.md](SECURITY.md). Please do not open a public issue for a
suspected vulnerability.
