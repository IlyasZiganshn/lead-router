.PHONY: install test lint run bench

install:
	uv sync --extra dev

test:
	uv run pytest

lint:
	uv run ruff check .

run:
	uv run uvicorn app.main:app --reload

bench:
	uv run python scripts/bench.py
