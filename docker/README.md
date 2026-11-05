# docker/

Container build files for each service. Local orchestration is the root
`docker-compose.yml`, which references these via each service's `build.dockerfile`.

- `backend.Dockerfile`  — FastAPI API (build context: `../backend`)
- `frontend.Dockerfile` — Next.js app (build context: `../frontend`)
