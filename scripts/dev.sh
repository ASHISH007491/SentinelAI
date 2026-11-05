#!/usr/bin/env bash
# Start the full local stack: db + backend + frontend.
set -euo pipefail
docker compose up -d db
( cd backend && uv run uvicorn app.main:app --reload ) &
( cd frontend && npm run dev ) &
wait
