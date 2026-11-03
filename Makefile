.PHONY: install install-all lock test test-integration test-all example api lint format typecheck docs-build docs-serve ts-test ts-typecheck build release-check clean

install:
	python -m pip install -e ".[dev]"

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
	memograph-api --host 0.0.0.0 --port 8000

lint:
	ruff check .
	ruff format --check .

format:
	ruff format .
	ruff check --fix .

typecheck:
	mypy

docs-build:
	mkdocs build --strict

docs-serve:
	mkdocs serve

ts-test:
	npm test --prefix sdk/typescript

ts-typecheck:
	npm run typecheck --prefix sdk/typescript

build:
	python -m build

release-check: lint typecheck test test-integration docs-build ts-test build

clean:
	rm -rf build dist site *.egg-info .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov coverage.xml
	rm -rf sdk/typescript/dist sdk/typescript/node_modules
