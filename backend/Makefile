.PHONY: dev start test lint fmt typecheck checkall

# Port for the API server (override: make dev BACKEND_PORT=8100)
BACKEND_PORT ?= 8000

dev:
	uv run uvicorn app.main:app --reload --reload-dir app --host 0.0.0.0 --port $(BACKEND_PORT)

start:
	uv run uvicorn app.main:app --host 0.0.0.0 --port $(BACKEND_PORT)

test:
	uv run pytest

lint:
	uv run ruff check .

fmt:
	uv run ruff format .

typecheck:
	uv run pyright .

checkall: fmt lint typecheck test
