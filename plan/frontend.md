# SOC Triager — Frontend Implementation Guide

> **Owner:** Engineer B
> **Stack:** React 18 + TypeScript + Vite + shadcn/ui + Recharts + TanStack Query/Table + Zustand + Playwright
> **Deployment:** Vercel — auto-preview per PR, production on `main` merge

---

## 1. Project Setup

### 1.1 Scaffold

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
```

### 1.2 Core Dependencies

```bash
# UI components
npx shadcn@latest init
npx shadcn@latest add button badge card dialog drawer sheet tabs tooltip

# Data fetching & state
npm install @tanstack/react-query @tanstack/react-table
npm install zustand

# Routing
npm install react-router-dom

# Charts
npm install recharts

# Markdown rendering
npm install react-markdown remark-gfm rehype-sanitize

# Mermaid (attack graph)
npm install mermaid

# Syntax highlighting (for playbooks)
npm install shiki

# Code quality
npm install -D typescript @types/react @types/react-dom eslint prettier
npm install -D vitest @testing-library/react @testing-library/user-event @testing-library/jest-dom jsdom
npm install -D @playwright/test
```

### 1.3 `vite.config.ts`

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') }
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test-setup.ts'
  }
})
```

### 1.4 `vercel.json`

```json
{
  "framework": "vite",
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "rewrites": [
    { "source": "/api/(.*)", "destination": "/api/$1" },
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

---

## 2. Directory Structure

```
frontend/src/
├── pages/
│   ├── AlertQueue.tsx
│   ├── IncidentDetail.tsx
│   ├── Navigator.tsx
│   ├── OpsMetrics.tsx
│   ├── PlaybookLibrary.tsx
│   └── Settings.tsx
├── components/
│   ├── layout/
│   │   ├── AppShell.tsx         ← sidebar + top bar wrapper
│   │   ├── Sidebar.tsx
│   │   └── TopBar.tsx
│   ├── ui/                      ← shadcn/ui generated components
│   ├── SeverityBadge.tsx
│   ├── TechniqueChip.tsx
│   ├── LiveConnectionPill.tsx
│   ├── AttackGraph.tsx
│   ├── MarkdownReport.tsx
│   ├── LedgerEntry.tsx
│   ├── RoleGate.tsx
│   ├── MetricCard.tsx
│   ├── AlertTable.tsx
│   └── SparklineScore.tsx
├── hooks/
│   ├── useAlertsFeed.ts
│   ├── useAuth.ts
│   ├── useIncidents.ts
│   ├── useIncidentDetail.ts
│   ├── useMitreLayer.ts
│   └── useMetrics.ts
├── stores/
│   ├── alertStore.ts
│   ├── authStore.ts
│   └── uiStore.ts
├── lib/
│   ├── apiClient.ts
│   ├── wsClient.ts
│   └── authUtils.ts
├── types/
│   └── index.ts                 ← all shared TypeScript interfaces
├── styles/
│   ├── globals.css
│   └── variables.css            ← CSS custom properties (dark/light mode)
├── App.tsx
├── main.tsx
└── test-setup.ts
```

---

## 3. TypeScript Interfaces

`src/types/index.ts` — shared across all components and API clients:

```typescript
export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info'
export type AlertStatus = 'new' | 'ack' | 'escalated' | 'closed'
export type Role = 'analyst' | 'senior_analyst' | 'approver'

export interface Entity {
  role: 'attacker' | 'victim' | 'pivot'
  ip?: string
  host?: string
  user?: string
  geo_country?: string
}

export interface Alert {
  id: string
  incident_id: string
  severity: Severity
  timestamp: string
  entity: { host?: string; user?: string; source_ip?: string }
  technique_id: string
  technique_name: string
  tactic: string
  anomaly_score: number
  score_history: number[]
  status: AlertStatus
  assignee: string | null
  created_at: string
}

export interface Incident {
  id: string
  title: string
  severity: Severity
  status: AlertStatus
  technique_id: string
  technique_name: string
  tactic: string
  confidence: number
  llm_rationale: string
  recommended_action: string
  entities: Entity[]
  alerts: string[]
  report_md?: string
  graph_mmd?: string
  playbook_draft?: string
  playbook_approved: boolean
  playbook_approved_by?: string
  created_at: string
  updated_at: string
}

export interface LedgerEntry {
  seq: number
  hash: string
  prev_hash: string
  timestamp: string
  action: string
  actor: string
  payload: Record<string, unknown>
}

export interface AuthState {
  token: string | null
  role: Role | null
  email: string | null
}
```

---

## 4. State Management

### 4.1 Zustand Stores

**`src/stores/authStore.ts`**
```typescript
import { create } from 'zustand'
import type { AuthState, Role } from '@/types'

interface AuthStore extends AuthState {
  setAuth: (token: string, role: Role, email: string) => void
  clearAuth: () => void
  hasRole: (...roles: Role[]) => boolean
}

export const useAuthStore = create<AuthStore>((set, get) => ({
  token: null,
  role: null,
  email: null,
  setAuth: (token, role, email) => set({ token, role, email }),
  clearAuth: () => set({ token: null, role: null, email: null }),
  hasRole: (...roles) => roles.includes(get().role as Role)
}))
```

**`src/stores/alertStore.ts`**
```typescript
import { create } from 'zustand'
import type { Alert } from '@/types'

interface AlertStore {
  alerts: Alert[]
  wsStatus: 'connected' | 'reconnecting' | 'disconnected'
  newAlertCount: number
  prependAlert: (alert: Alert) => void
  setAlerts: (alerts: Alert[]) => void
  setWsStatus: (status: AlertStore['wsStatus']) => void
  resetNewAlertCount: () => void
}

export const useAlertStore = create<AlertStore>((set) => ({
  alerts: [],
  wsStatus: 'disconnected',
  newAlertCount: 0,
  prependAlert: (alert) => set((s) => ({
    alerts: [alert, ...s.alerts],
    newAlertCount: s.newAlertCount + 1
  })),
  setAlerts: (alerts) => set({ alerts }),
  setWsStatus: (wsStatus) => set({ wsStatus }),
  resetNewAlertCount: () => set({ newAlertCount: 0 })
}))
```

**`src/stores/uiStore.ts`**
```typescript
import { create } from 'zustand'

interface Toast { id: string; message: string; type: 'info' | 'success' | 'warning' | 'error' }

interface UIStore {
  sidebarCollapsed: boolean
  darkMode: boolean
  toasts: Toast[]
  toggleSidebar: () => void
  toggleDarkMode: () => void
  addToast: (toast: Omit<Toast, 'id'>) => void
  removeToast: (id: string) => void
}

export const useUIStore = create<UIStore>((set) => ({
  sidebarCollapsed: false,
  darkMode: false,
  toasts: [],
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  toggleDarkMode: () => set((s) => ({ darkMode: !s.darkMode })),
  addToast: (toast) => set((s) => ({
    toasts: [...s.toasts, { ...toast, id: crypto.randomUUID() }]
  })),
  removeToast: (id) => set((s) => ({ toasts: s.toasts.filter(t => t.id !== id) }))
}))
```

### 4.2 TanStack Query Configuration

```typescript
// src/main.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,        // 10 s — alerts page refreshes frequently via WS anyway
      retry: 2,
      refetchOnWindowFocus: false
    }
  }
})
```

---

## 5. API Client

```typescript
// src/lib/apiClient.ts
import { useAuthStore } from '@/stores/authStore'

const BASE = '/api'  // Vercel BFF routes

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = useAuthStore.getState().token
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers
    }
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({}))
    throw new Error(error.error?.message ?? `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  getAlerts: (params: URLSearchParams) =>
    apiFetch<AlertsResponse>(`/alerts?${params}`),
  getIncident: (id: string) =>
    apiFetch<Incident>(`/incidents/${id}`),
  updateStatus: (id: string, status: string, note?: string) =>
    apiFetch<Incident>(`/incidents/${id}/status`, {
      method: 'POST',
      body: JSON.stringify({ status, note })
    }),
  approvePlaybook: (id: string, note: string) =>
    apiFetch<{ approved: boolean }>(`/incidents/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ note })
    }),
  getMetrics: () => apiFetch<MetricsResponse>('/metrics'),
  getNavigatorLayer: () => apiFetch<object>('/navigator/layer.json')
}
```

---

## 6. WebSocket Client

```typescript
// src/lib/wsClient.ts
import { useAlertStore } from '@/stores/alertStore'
import { useUIStore } from '@/stores/uiStore'

const MAX_RETRIES = 10
const BASE_DELAY = 1000

export function createAlertsFeed(token: string) {
  let ws: WebSocket | null = null
  let retries = 0
  let heartbeatTimer: ReturnType<typeof setTimeout>

  function connect() {
    useAlertStore.getState().setWsStatus('reconnecting')
    ws = new WebSocket(`${location.origin.replace('https','wss')}/api/ws/alerts?token=${token}`)

    ws.onopen = () => {
      retries = 0
      useAlertStore.getState().setWsStatus('connected')
      scheduleHeartbeatCheck()
    }

    ws.onmessage = (event) => {
      clearTimeout(heartbeatTimer)
      scheduleHeartbeatCheck()
      const msg = JSON.parse(event.data)
      if (msg.type === 'new_alert') {
        useAlertStore.getState().prependAlert(msg.alert)
        if (msg.alert.severity === 'critical') {
          useUIStore.getState().addToast({ type: 'error', message: `Critical alert: ${msg.alert.entity.host}` })
        }
      }
    }

    ws.onclose = () => {
      clearTimeout(heartbeatTimer)
      if (retries < MAX_RETRIES) {
        const delay = Math.min(BASE_DELAY * 2 ** retries, 30_000)
        retries++
        useAlertStore.getState().setWsStatus('reconnecting')
        setTimeout(connect, delay)
      } else {
        useAlertStore.getState().setWsStatus('disconnected')
      }
    }
  }

  function scheduleHeartbeatCheck() {
    heartbeatTimer = setTimeout(() => {
      ws?.close()  // triggers reconnect
    }, 40_000)  // server heartbeat every 30 s + 10 s grace
  }

  connect()
  return { disconnect: () => { retries = MAX_RETRIES; ws?.close() } }
}
```

---

## 7. Key Components — Implementation Notes

### 7.1 `RoleGate`

```typescript
// src/components/RoleGate.tsx
import { useAuthStore } from '@/stores/authStore'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import type { Role } from '@/types'

interface RoleGateProps {
  requiredRole: Role
  children: React.ReactNode
  fallbackTooltip?: string
}

export function RoleGate({ requiredRole, children, fallbackTooltip }: RoleGateProps) {
  const hasRole = useAuthStore(s => s.hasRole)

  if (hasRole(requiredRole, 'approver')) return <>{children}</>

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="cursor-not-allowed">
          <span className="pointer-events-none opacity-40">{children}</span>
        </span>
      </TooltipTrigger>
      <TooltipContent>
        {fallbackTooltip ?? `Requires ${requiredRole.replace('_', ' ')} role`}
      </TooltipContent>
    </Tooltip>
  )
}
```

### 7.2 `AttackGraph`

```typescript
// src/components/AttackGraph.tsx
import { useEffect, useRef } from 'react'
import mermaid from 'mermaid'

mermaid.initialize({ startOnLoad: false, theme: 'default', securityLevel: 'loose' })

export function AttackGraph({ mermaidSource }: { mermaidSource: string }) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current || !mermaidSource) return
    const id = `graph-${Math.random().toString(36).slice(2)}`
    mermaid.render(id, mermaidSource).then(({ svg }) => {
      if (containerRef.current) containerRef.current.innerHTML = svg
    })
  }, [mermaidSource])

  return (
    <div
      ref={containerRef}
      className="overflow-auto rounded-lg border bg-muted/20 p-4 min-h-[300px]"
      aria-label="Attack graph visualization"
    />
  )
}
```

### 7.3 `SeverityBadge`

```typescript
// src/components/SeverityBadge.tsx
import { Badge } from '@/components/ui/badge'
import type { Severity } from '@/types'

const SEVERITY_CONFIG: Record<Severity, { label: string; className: string }> = {
  critical: { label: 'Critical', className: 'bg-red-600 text-white' },
  high:     { label: 'High',     className: 'bg-orange-500 text-white' },
  medium:   { label: 'Medium',   className: 'bg-yellow-500 text-black' },
  low:      { label: 'Low',      className: 'bg-blue-500 text-white' },
  info:     { label: 'Info',     className: 'bg-gray-400 text-white' }
}

export function SeverityBadge({ level }: { level: Severity }) {
  const { label, className } = SEVERITY_CONFIG[level]
  return (
    <Badge className={className} aria-label={`Severity: ${label}`}>
      {label}
    </Badge>
  )
}
```

---

## 8. Vercel BFF — Serverless Function Pattern

All BFF functions follow the same pattern:

```typescript
// frontend/api/incidents/[id]/approve.ts
import type { VercelRequest, VercelResponse } from '@vercel/node'
import { verifyJWT, requireRole } from '../../_lib/auth'

export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (req.method !== 'POST') return res.status(405).end()

  const claims = verifyJWT(req.headers.authorization)
  if (!claims) return res.status(401).json({ error: { code: 'UNAUTHORIZED' } })

  if (!requireRole(claims, 'approver'))
    return res.status(403).json({ error: { code: 'FORBIDDEN', message: 'Approver role required' } })

  const backendRes = await fetch(
    `${process.env.BACKEND_API_URL}/api/incidents/${req.query.id}/approve`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Internal-Auth': process.env.INTERNAL_SERVICE_TOKEN!
      },
      body: JSON.stringify(req.body)
    }
  )

  const data = await backendRes.json()
  return res.status(backendRes.status).json(data)
}
```

`X-Internal-Auth` is a shared secret between the BFF and FastAPI for service-to-service auth (not user JWT). Stored in `INTERNAL_SERVICE_TOKEN` env var.

---

## 9. Testing

### 9.1 Vitest + React Testing Library

```typescript
// frontend/tests/RoleGate.test.tsx
import { render, screen } from '@testing-library/react'
import { describe, it, expect, beforeEach } from 'vitest'
import { RoleGate } from '@/components/RoleGate'
import { useAuthStore } from '@/stores/authStore'

describe('RoleGate', () => {
  it('renders children for users with the required role', () => {
    useAuthStore.setState({ role: 'approver', token: 'mock', email: 'a@b.com' })
    render(<RoleGate requiredRole="approver"><button>Approve</button></RoleGate>)
    expect(screen.getByRole('button')).not.toBeDisabled()
  })

  it('disables children for users without the required role', () => {
    useAuthStore.setState({ role: 'analyst', token: 'mock', email: 'a@b.com' })
    render(<RoleGate requiredRole="approver"><button>Approve</button></RoleGate>)
    expect(screen.getByRole('button').closest('span')).toHaveClass('pointer-events-none')
  })
})
```

### 9.2 Playwright E2E

```typescript
// frontend/e2e/rbac.spec.ts
import { test, expect } from '@playwright/test'

test('analyst cannot approve a playbook', async ({ page }) => {
  await page.goto('/')
  await page.getByText('Sign in as Analyst').click()
  await page.getByRole('link', { name: 'Incidents' }).click()
  await page.getByRole('row').first().click()
  await page.getByRole('tab', { name: 'Containment Playbook' }).click()
  const approveBtn = page.getByRole('button', { name: 'Approve for Ops' })
  await expect(approveBtn.locator('..')).toHaveClass(/pointer-events-none/)
})

test('approver can approve a playbook', async ({ page }) => {
  await page.goto('/')
  await page.getByText('Sign in as Approver').click()
  await page.getByRole('link', { name: 'Incidents' }).click()
  await page.getByRole('row').first().click()
  await page.getByRole('tab', { name: 'Containment Playbook' }).click()
  await page.getByRole('button', { name: 'Approve for Ops' }).click()
  await expect(page.getByText('Playbook approved')).toBeVisible()
})
```

```typescript
// playwright.config.ts
import { defineConfig } from '@playwright/test'
export default defineConfig({
  use: { baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5173' },
  webServer: process.env.PLAYWRIGHT_BASE_URL ? undefined : {
    command: 'npm run dev',
    url: 'http://localhost:5173'
  }
})
```

`PLAYWRIGHT_BASE_URL` is set in CI to the Vercel Preview URL, so tests run against the real deployed environment.

---

## 10. Performance Optimization

- **Code splitting:** React Router's `lazy()` + `Suspense` for all page components — only the current page's JS is loaded
- **TanStack Query caching:** alert list cached for 10 s; incident detail cached for 30 s; MITRE technique data cached for 1 h (static)
- **Mermaid lazy load:** `mermaid` package imported dynamically only when the Attack Graph tab is first opened
- **Recharts tree shaking:** import individual chart components, not the full `recharts` bundle
- **Bundle analysis:** `npm run build -- --report` generates a `dist/stats.html` treemap; review before every major feature addition
- **Image optimization:** Vercel's built-in image optimization used for any static assets; SVGs used for icons
- **Vercel Speed Insights:** `@vercel/speed-insights` injected in `main.tsx` — real user performance data available in the Vercel dashboard from day one
