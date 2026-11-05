.PHONY: db backend frontend test lint evaluate
db:        ## start Postgres
	docker compose up -d db
backend:   ## run API (from backend/)
	cd backend && uv run uvicorn app.main:app --reload
frontend:  ## run dashboard on :3000 (from frontend/)
	cd frontend && npm run dev
test:      ## run backend + agent tests
	cd backend && uv run pytest -q
	cd agents && uv run pytest -q
lint:      ## ruff over python packages
	cd backend && uv run ruff check .
	cd agents && uv run ruff check .
evaluate:  ## run the full experiment matrix (Tracks A/B/C/D, N=5) -> eval/results/<timestamp>/
	uv run --project backend python -m eval.harness.runner --all --repeats 5
