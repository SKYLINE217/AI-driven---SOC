---
name: soc-triager-frontend
description: Use this skill whenever the user is implementing or asking about the SOC Triager React frontend — project scaffolding, dependencies, directory structure, TypeScript interfaces, Zustand state stores, TanStack Query config, the API client, the WebSocket client, key components (RoleGate, AttackGraph, SeverityBadge), the Vercel BFF serverless function pattern, Vitest/Playwright tests, or frontend performance optimization. Trigger this for anything under `frontend/src`, `.tsx`, Vite config, shadcn/ui, Zustand, TanStack, or Vercel BFF functions. Pairs with `soc-triager-dashboard-design` (UX/page spec) — use that skill for what a page should look like and this one for how to build it.
---

# SOC Triager — Frontend Implementation Guide

> Owner: Engineer B. Stack: React 18 + TypeScript + Vite + shadcn/ui + Recharts + TanStack Query/Table + Zustand + Playwright. Deployment: Vercel — auto-preview per PR, production on `main` merge.

## Project setup

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend && npm install

# UI components
npx shadcn@latest init
npx shadcn@latest add button badge card dialog drawer sheet tabs tooltip

# Data fetching & state
npm install @tanstack/react-query @tanstack/react-table zustand

# Routing, charts, markdown, diagrams, syntax highlighting
npm install react-router-dom recharts react-markdown remark-gfm rehype-sanitize mermaid shiki

# Code quality / testing
npm install -D typescript @types/react @types/react-dom eslint prettier
npm install -D vitest @testing-library/react @testing-library/user-event @testing-library/jest-dom jsdom
npm install -D @playwright/test
```

`vite.config.ts` — alias `@` to `./src`; test config `environment: 'jsdom'`, `setupFiles: './src/test-setup.ts'`.

`vercel.json`:
```json
{
  "framework": "vite", "buildCommand": "npm run build", "outputDirectory": "dist",
  "rewrites": [
    { "source": "/api/(.*)", "destination": "/api/$1" },
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

## Directory structure

```
frontend/src/
├── pages/          AlertQueue.tsx, IncidentDetail.tsx, Navigator.tsx, OpsMetrics.tsx, PlaybookLibrary.tsx, Settings.tsx
├── components/
│   ├── layout/     AppShell.tsx, Sidebar.tsx, TopBar.tsx
│   ├── ui/         shadcn/ui generated
│   └── SeverityBadge.tsx, TechniqueChip.tsx, LiveConnectionPill.tsx, AttackGraph.tsx,
│       MarkdownReport.tsx, LedgerEntry.tsx, RoleGate.tsx, MetricCard.tsx, AlertTable.tsx, SparklineScore.tsx
├── hooks/          useAlertsFeed, useAuth, useIncidents, useIncidentDetail, useMitreLayer, useMetrics
├── stores/         alertStore.ts, authStore.ts, uiStore.ts
├── lib/            apiClient.ts, wsClient.ts, authUtils.ts
├── types/index.ts  all shared TypeScript interfaces
├── styles/         globals.css, variables.css (dark/light CSS custom properties)
├── App.tsx  main.tsx  test-setup.ts
```

## TypeScript interfaces (`src/types/index.ts`)

```typescript
export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info'
export type AlertStatus = 'new' | 'ack' | 'escalated' | 'closed'
export type Role = 'analyst' | 'senior_analyst' | 'approver'

export interface Entity { role: 'attacker' | 'victim' | 'pivot'; ip?: string; host?: string; user?: string; geo_country?: string }

export interface Alert {
  id: string; incident_id: string; severity: Severity; timestamp: string
  entity: { host?: string; user?: string; source_ip?: string }
  technique_id: string; technique_name: string; tactic: string
  anomaly_score: number; score_history: number[]
  status: AlertStatus; assignee: string | null; created_at: string
}

export interface Incident {
  id: string; title: string; severity: Severity; status: AlertStatus
  technique_id: string; technique_name: string; tactic: string; confidence: number
  llm_rationale: string; recommended_action: string
  entities: Entity[]; alerts: string[]
  report_md?: string; graph_mmd?: string; playbook_draft?: string
  playbook_approved: boolean; playbook_approved_by?: string
  created_at: string; updated_at: string
}

export interface LedgerEntry { seq: number; hash: string; prev_hash: string; timestamp: string; action: string; actor: string; payload: Record<string, unknown> }
export interface AuthState { token: string | null; role: Role | null; email: string | null }
```

## State management

**Zustand stores:**
- `authStore` — `{ token, role, email, setAuth(), clearAuth(), hasRole(...roles) }`
- `alertStore` — `{ alerts, wsStatus: 'connected'|'reconnecting'|'disconnected', newAlertCount, prependAlert(), setAlerts(), setWsStatus(), resetNewAlertCount() }`. `prependAlert` puts the newest alert first and increments the counter.
- `uiStore` — `{ sidebarCollapsed, darkMode, toasts, toggleSidebar(), toggleDarkMode(), addToast(), removeToast() }`

**TanStack Query** handles all server state (fetch/cache/revalidate/loading/error) for REST endpoints; Zustand handles client-side and real-time WebSocket state. Cache TTLs: alert list 10 s, incident detail 30 s, MITRE technique data 1 h (static).

## API client & WebSocket client

`src/lib/apiClient.ts` wraps `fetch` against the BFF (`/api/...`), typed per endpoint (`approvePlaybook(id, note)`, `getMetrics()`, `getNavigatorLayer()`, etc.) — never calls FastAPI directly from the browser.

`src/lib/wsClient.ts` — `createAlertsFeed(token)`:
- Connects to `wss://.../api/ws/alerts?token=<jwt>`.
- On `new_alert` message → `prependAlert()`; if `severity === 'critical'` also fire a toast.
- **Reconnect:** exponential backoff, `BASE_DELAY = 1000ms`, doubling up to 30 s max, `MAX_RETRIES = 10`. After max retries, status becomes `disconnected`.
- **Heartbeat watchdog:** resets a 40 s timer (`server heartbeat 30s + 10s grace`) on every message; if it fires, the socket is force-closed to trigger reconnect.

## Key components — implementation notes

**`RoleGate`** — wraps children; if `hasRole(requiredRole, 'approver')` renders them normally, else wraps in a disabled, `pointer-events-none opacity-40` span with a tooltip explaining the required role. **This is UX only** — the real enforcement is server-side (see `soc-triager-security`).

**`AttackGraph`** — lazy-renders Mermaid source into a `<div>` via `mermaid.render()` in a `useEffect`; `mermaid.initialize({ startOnLoad: false, securityLevel: 'loose' })`.

**`SeverityBadge`** — maps `Severity` to a color/label config (`critical`=red-600, `high`=orange-500, `medium`=yellow-500, `low`=blue-500, `info`=gray-400) and renders an accessible `<Badge>` with `aria-label`.

## Vercel BFF — serverless function pattern

Every BFF function under `frontend/api/` follows this shape:
```typescript
// frontend/api/incidents/[id]/approve.ts
export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (req.method !== 'POST') return res.status(405).end()
  const claims = verifyJWT(req.headers.authorization)
  if (!claims) return res.status(401).json({ error: { code: 'UNAUTHORIZED' } })
  if (!requireRole(claims, 'approver'))
    return res.status(403).json({ error: { code: 'FORBIDDEN', message: 'Approver role required' } })
  const backendRes = await fetch(`${process.env.BACKEND_API_URL}/api/incidents/${req.query.id}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Internal-Auth': process.env.INTERNAL_SERVICE_TOKEN! },
    body: JSON.stringify(req.body)
  })
  return res.status(backendRes.status).json(await backendRes.json())
}
```
`X-Internal-Auth` is a shared secret between BFF and FastAPI for service-to-service auth (never the user's JWT).

## Testing

**Vitest + RTL** — component tests, e.g. `RoleGate.test.tsx` asserts children are enabled for a matching role and disabled (`pointer-events-none` class) for a non-matching one.

**Playwright E2E** — full-flow specs run against a real deployed URL:
```typescript
test('analyst cannot approve a playbook', async ({ page }) => {
  await page.goto('/'); await page.getByText('Sign in as Analyst').click()
  await page.getByRole('link', { name: 'Incidents' }).click()
  await page.getByRole('row').first().click()
  await page.getByRole('tab', { name: 'Containment Playbook' }).click()
  await expect(page.getByRole('button', { name: 'Approve for Ops' }).locator('..')).toHaveClass(/pointer-events-none/)
})
```
`playwright.config.ts` reads `PLAYWRIGHT_BASE_URL` (set in CI to the Vercel Preview URL) so tests exercise the real deployed environment, not just localhost.

## Performance optimization

- **Code splitting** — React Router `lazy()` + `Suspense` per page.
- **Mermaid lazy-loaded** — only imported when the Attack Graph tab first opens.
- **Recharts tree-shaken** — import individual chart components, not the whole bundle.
- **Bundle analysis** — `npm run build -- --report` → `dist/stats.html` treemap; review before every major feature.
- **Vercel Speed Insights** — `@vercel/speed-insights` injected in `main.tsx` for real-user performance data from day one.
- Targets (see `soc-triager-dashboard-design` for the full table): Lighthouse ≥ 85, gzipped JS < 400 KB.
