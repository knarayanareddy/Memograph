.PHONY: install test example lint format typecheck build clean

install:
	python -m pip install -e ".[dev]"

test:
	pytest --cov=memograph --cov-report=term-missing

example:
	python examples/quickstart.py

lint:
	ruff check .
	ruff format --check .

format:
	ruff format .
	ruff check --fix .

typecheck:
	mypy

build:
	python -m build

clean:
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
