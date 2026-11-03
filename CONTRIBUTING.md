# Contributing

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

## Checks

```bash
make test
make example
make lint
make typecheck
make build
```

Or run the individual commands:

```bash
ruff check .
ruff format --check .
mypy
pytest --cov=memograph --cov-report=term-missing
python -m build
```

All checks run in CI on Python 3.11, 3.12, and 3.13.

## Guidelines

- Keep SQLite as the source of truth; never make a generated Markdown/JSON file
  authoritative.
- Route every path derived from user, transcript, or model input through
  `memograph.validation`.
- Keep LLM output behind a strict Pydantic schema. Never pass arbitrary model
  dictionaries as `**kwargs`.
- Add a regression test for every bug fix, especially concurrency, path
  containment, index limits, and failure/rollback behavior.
- Do not commit `.env`, databases, generated memory stores, or API keys.
- Update `docs/ROADMAP.md` when implementation status changes.
- Prefer small, descriptive commits. Do not commit generated PDFs or binaries.

## Reporting security issues

See [SECURITY.md](SECURITY.md). Please do not open a public issue for a
suspected vulnerability.
