# tests/

End-to-end (browser) tests with Playwright live in `tests/e2e/`. They drive the
running app (frontend on :3000 + backend on :8000).

Backend unit/integration tests (pytest) live in `backend/tests/`; agent tests in
`agents/tests/` — colocated with the code they cover, by convention.

Run E2E:  `cd frontend && npm run test:e2e`  (with the stack running).
