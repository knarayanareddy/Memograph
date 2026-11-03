# Contributing

## Setup

For core development:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

For the locked core CI environment (API and docs, without the vulnerable
ChromaDB transitive dependency):

```bash
uv sync --frozen --extra dev --extra api --extra docs
npm ci --prefix sdk/typescript
```

For the real framework SDK integration job only:

```bash
uv sync --all-extras --frozen
pytest -q -m integration
```

Set a high-entropy `MEMOGRAPH_API_KEY` of at least 16 characters before running
`memograph-api` or the REST API tests explicitly. `.env.example` contains only
empty secret values. The service is single-user; never share one key across
untrusted clients.

## Checks

```bash
make lint
make typecheck
make security
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
bandit -c pyproject.toml -r src/memograph -ll
ruff check src/memograph --select S --ignore S101
uv export --all-extras --frozen --no-emit-project --format requirements-txt > /tmp/requirements.txt
uvx --from 'pip-audit==2.10.1' pip-audit -r /tmp/requirements.txt --vulnerability-service pypi --progress-spinner off --format json --ignore-vuln GHSA-f4j7-r4q5-qw2c --ignore-vuln GHSA-36p7-vc44-83pf --ignore-vuln GHSA-xph7-9rjv-w5fr --ignore-vuln GHSA-2wm9-hf6c-p5cr
npm audit --prefix sdk/typescript --omit=dev
pytest --cov=memograph --cov-report=term-missing -m "not integration"
pytest -q -m integration
mkdocs build --strict
npm test --prefix sdk/typescript -- --run
python -m build
```

All checks run in CI on Python 3.11, 3.12, 3.13 and Node.js 22, 24, 26. The
`integration` marker selects tests that import real LangChain, CrewAI, and
AutoGen packages; only that job installs `--all-extras`. See
[SECURITY.md](SECURITY.md) for the documented ChromaDB advisory exceptions.

## Guidelines

- Keep SQLite as the source of truth; never make a generated Markdown/JSON file
  authoritative.
- Route every path derived from user, transcript, or model input through
  `memograph.validation` or the TypeScript `assertTopicId`/`safePath` helpers.
- Keep LLM output behind a strict Pydantic schema. Never pass arbitrary model
  dictionaries as `**kwargs`.
- Keep the REST API authenticated by default; CORS is opt-in. Do not add
  per-client auth without a full scopes/tenants/rotation design.
- Add a regression test for every bug fix, especially concurrency, path
  containment, index limits, auth, rate limits, resource limits, and
  failure/rollback behavior.
- Add a TypeScript test for SDK or local-store behavior changes.
- Never put secrets in URLs; use headers and keep structured audit logs free of
  request bodies and credentials.
- Do not commit `.env`, databases, generated memory stores, API keys, npm
  tokens, `node_modules/`, `dist/`, or `site/`.
- Update `docs/ROADMAP.md` and `docs/SPEC_STATUS.md` when implementation status
  changes; keep `uv.lock` and `sdk/typescript/package-lock.json` in sync with
  dependency changes.
- Prefer small, descriptive commits. Do not commit generated PDFs or binaries.

## Reporting security issues

See [SECURITY.md](SECURITY.md). Please do not open a public issue for a
suspected vulnerability.
