# SentinelAI

A multi-agent cybersecurity copilot for vulnerability analysis, phishing
investigation, and security decision support — plus a single-agent baseline for
a fair architectural comparison. Mono-repo for the dissertation build.

## Layout
| Path | Purpose |
|------|---------|
| `backend/`  | FastAPI API: auth, uploads, run records, orchestration entrypoint (Python, uv, ruff, pytest) |
| `agents/`   | LangGraph orchestrator + five MVP agents, shared toolkit, single-agent baseline, typed contracts |
| `frontend/` | Next.js 15 + React + TypeScript + Tailwind dashboard |
| `eval/`     | Evaluation harness, datasets, analysis notebooks, results |
| `docs/`     | Architecture, evaluation protocol, ADRs |
| `infrastructure/` | Deployment / provisioning helpers |
| `scripts/`  | Dev helpers (`dev.sh`) |

## Quickstart
```bash
cp .env.example .env
docker compose up -d db                 # Postgres on :5432

cd backend && uv sync --extra dev
uv run alembic upgrade head             # create the schema (Alembic owns it)
uv run python -m app.seed               # demo account + sample data (optional)
uv run uvicorn app.main:app --reload    # API on :8000  (/docs, /health)

cd ../frontend && npm install && npm run dev   # dashboard on :3000
```
The dashboard pings the backend `/health` endpoint, proving the React → FastAPI → DB
wire-up.

**LLM is optional.** With no `LLM_API_KEY` set, every agent falls back to a
deterministic rule-based path, so the app, the tests and the evaluation harness
all run offline. Set `LLM_API_KEY` (Anthropic) and `LLM_MODEL` in `.env` to use a
real model. No Ollama or local model is required.

## Reproducing the evaluation
```bash
make evaluate      # Tracks A/B/C (multi-agent vs single-LLM baseline) + Track D
                   # (guardrail on/off), N=5 repeats, into eval/results/<timestamp>/

# figures need matplotlib/pandas — the `viz` extra:
cd backend && uv sync --extra dev --extra viz && cd ..
uv run --project backend python eval/notebooks/generate_figures.py   # PNGs from the CSVs
```
Each run writes `summary.csv` (mean ± std per metric, including the efficiency
columns `agents_invoked` / `llm_calls` / `total_tokens` / `latency_s`),
`significance.csv` (paired Wilcoxon, multi-agent vs baseline) and per-run traces.
`eval/results/` is git-ignored — it is regenerated, not version-controlled.

Runs offline on the rule-based fallback (deterministic, so `std = 0`); set
`LLM_API_KEY` in `.env` for real-model numbers with genuine variance. Single
tracks: `... python -m eval.harness.runner --track {A,B,C,D} --repeats N`.

## Conventions
- Python: `uv`, `ruff` (lint+format), `pytest`. Pre-commit hooks via `.pre-commit-config.yaml`.
- CI: lint + tests for `backend/` and `agents/`, lint for `frontend/`, and a
  Postgres-backed end-to-end job. `.gitlab-ci.yml` runs on git.cs.bham.ac.uk;
  `.github/workflows/ci.yml` mirrors it for a GitHub mirror.
- One command stack: `./scripts/dev.sh` or `make db backend frontend`.

See `docs/` for architecture and the evaluation protocol; see `CODE_DELIVERY_PHASES.md`
for the phased delivery plan and per-phase supervisor tests.

## Status
Phases 1–7 delivered and tagged (`phase1`…`phase7`): running skeleton, data/auth/
datasets, orchestrator, the prioritisation / phishing / code-review agents, the
guardrail wired into the live request path, the single-agent baseline, and the
evaluation harness (Tracks A–D with efficiency metrics). Phase 8 — full experiment
matrix, reproducibility docs and the tagged release — is in progress.
