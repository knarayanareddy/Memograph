.PHONY: install install-core install-all lock test test-integration test-all example api lint format typecheck security docs-build docs-serve ts-test ts-typecheck build release-check clean

install:
	python -m pip install -e ".[dev]"

install-core:
	uv sync --frozen --extra dev --extra api --extra docs

install-all:
	uv sync --all-extras --frozen

lock:
	uv lock

test:
	pytest --cov=memograph --cov-report=term-missing -m "not integration"

test-integration:
	pytest -q -m integration

test-all:
	pytest --cov=memograph --cov-report=term-missing

example:
	python examples/quickstart.py

api:
	@test -n "$(MEMOGRAPH_API_KEY)" || (echo "Set MEMOGRAPH_API_KEY first" && exit 1)
	memograph-api --host 127.0.0.1 --port 8000

lint:
	ruff check .
	ruff format --check .

format:
	ruff format .
	ruff check --fix .

typecheck:
	mypy

security:
	bandit -c pyproject.toml -r src/memograph -ll
	ruff check src/memograph --select S --ignore S101
	uv export --all-extras --frozen --no-emit-project --format requirements-txt > /tmp/memograph-requirements.txt
	uvx --from 'pip-audit==2.10.1' pip-audit -r /tmp/memograph-requirements.txt --vulnerability-service pypi --progress-spinner off --format json --ignore-vuln GHSA-f4j7-r4q5-qw2c --ignore-vuln GHSA-36p7-vc44-83pf --ignore-vuln GHSA-xph7-9rjv-w5fr --ignore-vuln GHSA-2wm9-hf6c-p5cr
	npm audit --prefix sdk/typescript --omit=dev

docs-build:
	mkdocs build --strict

docs-serve:
	mkdocs serve

ts-test:
	npm test --prefix sdk/typescript -- --run

ts-typecheck:
	npm run typecheck --prefix sdk/typescript

build:
	python -m build

release-check: lint typecheck security test test-integration docs-build ts-test build

clean:
	rm -rf build dist site *.egg-info .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov coverage.xml
	rm -rf sdk/typescript/dist sdk/typescript/node_modules
