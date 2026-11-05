# SentinelAI — Web (Frontend)

Enterprise dashboard for the SentinelAI Multi-Agent AI Cybersecurity Copilot.

## Stack
Next.js 15 (App Router) · React 19 · TypeScript (strict) · Tailwind CSS · shadcn/ui
(Radix primitives) · Framer Motion · TanStack Query · TanStack Table · React Hook Form ·
Zod · Recharts · Lucide · Sonner · next-themes.

## Getting started
```bash
npm install
cp .env.example .env.local      # set NEXT_PUBLIC_API_BASE_URL if backend isn't on :8000
npm run dev                     # http://localhost:3000
```
`/api/*` is proxied to the FastAPI backend (default `http://localhost:8000`) via
`next.config.mjs` rewrites. Dark mode is the default; a toggle is in the navbar.

## Scripts
| Script | Purpose |
|--------|---------|
| `npm run dev` | Start the dev server |
| `npm run build` / `start` | Production build / serve |
| `npm run typecheck` | `tsc --noEmit` (strict) |
| `npm run lint` | Next.js ESLint |

## Architecture (feature-based)
```
src/
  app/
    (auth)/            Auth layout + login & register
    (app)/             Authenticated shell (sidebar + navbar + footer)
      dashboard/ vulnerability-analysis/ phishing-analysis/ code-review/
      threat-intelligence/ security-advisor/ reports/ projects/ settings/ profile/
      layout.tsx  loading.tsx  error.tsx
    layout.tsx  page.tsx  not-found.tsx  globals.css
  components/
    ui/                shadcn/ui primitives (button, card, table, dialog, sheet…)
    layout/            sidebar, navbar, mobile-nav, footer, brand
    dashboard/         metric-card, charts, security-score, agent-card, tables…
    shared/            page-header, breadcrumbs, states, upload, badges, search
  providers/           theme, react-query, composed AppProviders
  hooks/               use-mounted, use-media-query, use-sidebar
  lib/                 utils, api-client, query-client, validators, mock-data
  services/            typed API surface (auth, runs)
  constants/ config/ types/    navigation, severity, site config, domain types
```

## Design system
HSL design tokens in `globals.css` drive both themes and a security severity palette
(`critical/high/medium/low/info`). Glassmorphism via the `.glass` utility; ambient
gradient via `.app-aurora`. Charts and components read CSS variables so they re-theme
automatically.

## Data
Pages currently render from `lib/mock-data.ts` for presentation. Swap these for
TanStack Query calls against `services/*` as backend endpoints come online — the
`api-client` already handles bearer auth and the `/api` proxy.

## Notes
- Strict TypeScript, no inline styles (except dynamic chart/gauge geometry), reusable
  components, accessible (labels, roles, focus-visible rings, keyboard-friendly upload).
