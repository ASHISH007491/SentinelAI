# Frontend Architecture

The web client is a Next.js 15 App Router application using a feature-based layout.
Route groups separate the unauthenticated `(auth)` surface from the authenticated
`(app)` shell (collapsible sidebar, sticky navbar, footer, mobile sheet nav).

Cross-cutting concerns live in `providers/` (theme, React Query, toasts), `lib/`
(api-client with bearer auth + `/api` proxy, query client, validators, utils), and
`services/` (typed API calls). Presentation primitives are hand-written shadcn/ui
components over Radix. Charts use Recharts and read theme CSS variables.

See `frontend/README.md` for the full directory map and run instructions.
