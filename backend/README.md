# SentinelAI Backend

FastAPI service: auth, uploads, run records, orchestration entrypoint.

## Quickstart
```bash
uv sync --extra dev          # or: pip install -e ".[dev]"
cp ../.env.example .env
docker compose -f ../docker-compose.yml up -d db   # Postgres on :5432
uv run alembic upgrade head  # create the schema — Alembic owns it, the app does not
uv run python -m app.seed    # demo account + sample data (optional)
uv run uvicorn app.main:app --reload
```
Open http://localhost:8000/docs. Health: http://localhost:8000/health

`LLM_API_KEY` is optional: unset, agents use a deterministic rule-based path and
all tests still pass. Set it (Anthropic) plus `LLM_MODEL` to use a real model.

## Test & lint
```bash
uv run pytest
uv run ruff check .
```
