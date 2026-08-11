---
name: soc-triager-dashboard-design
description: Use this skill whenever the user asks what a SOC Triager dashboard page should look like or how it should behave — the app shell/navigation layout, the Alert Queue table and filters, the Incident Detail page and its 5 tabs (Overview, Attack Graph, MITRE Technique, Containment Playbook, Audit Trail), the MITRE Navigator page, Ops Metrics panels, the Playbook Library, the shared component inventory, or accessibility/performance targets. Trigger this for any UX, layout, page-spec, or "what should this component show" question about the React SOC dashboard. Use `soc-triager-frontend` alongside this for the actual React/TypeScript implementation of what this skill specifies.
---

# SOC Triager — Dashboard Design & Specification

> Audience: Engineer B (primary builder), Engineer A (consumer/reviewer for analyst UX copy). This is a single-page React app deployed to Vercel that talks only to the BFF (`/api/...`), never directly to FastAPI.

## Personas & RBAC-visible capabilities

| Role | Capabilities |
|---|---|
| **Analyst** | View all alerts/incidents; acknowledge and assign alerts; view all tabs including containment playbooks (read-only) |
| **Senior Analyst** | All Analyst + escalate incidents + close incidents + annotate audit trail |
| **Approver** | All Senior Analyst + approve containment playbooks for ops execution |

RBAC is enforced **twice**: client-side via `RoleGate` (UX only — prevents accidental clicks) and server-side via BFF + FastAPI (the real security control — see `soc-triager-security`).

## App shell & navigation

```
┌──────────────────────────────────────────────────────────┐
│ TOP BAR: [logo]  [Search]  [WS Pill]  [Role]  [dark mode] │
├──────────┬───────────────────────────────────────────────┤
│ SIDEBAR  │  PAGE CONTENT                                  │
│ Alert Queue │                                             │
│ Incidents   │                                             │
│ Navigator   │                                             │
│ Ops         │                                             │
│ Playbooks   │                                             │
│ Settings    │                                             │
└──────────┴───────────────────────────────────────────────┘
```

**Top bar:** logo (links `/alerts`); global entity search (IP/hostname/username/technique ID, e.g. `T1110`, dropdown results with severity chips); `LiveConnectionPill` (🟢 Connected / 🟡 Reconnecting… + retry count / 🔴 Disconnected + Manual Refresh button); role badge/switcher (dev/demo only — production uses a real identity provider); dark/light toggle persisted to `localStorage`.

**Sidebar** (collapsible to icon-only, state in Zustand): 🚨 Alert Queue `/alerts` · 📋 Incidents `/incidents` · 🗺️ MITRE Navigator `/navigator` · 📊 Ops Metrics `/ops` · 📚 Playbook Library `/playbooks` · ⚙️ Settings `/settings`. All routes are open to all roles.

**Global toast system** — Zustand-driven queue, top-right: critical alert → red, auto-dismiss 8 s, click navigates to incident; WS reconnection → amber; containment approved → green.

## Page: Alert Queue (`/alerts`)

Primary operational view — analysts spend ~80% of their time here. New alerts stream via WebSocket; the table updates without a reload.

**Data:** WebSocket (`/ws/alerts` via BFF) for live rows; REST `GET /api/alerts` for initial load and after filter changes.

**Table columns:** Severity (`SeverityBadge`, sortable, multi-select filter) · Timestamp (relative time + ISO tooltip, sortable desc default, date-range filter) · Entity (host/user/IP, free-text filter) · MITRE Technique (`TechniqueChip`, multi-select filter) · Anomaly Score (`SparklineScore`, 24h history, range-slider filter) · Status (`StatusPill`, sortable, multi-select filter) · Assignee (select from user list).

**Filter bar** (persistent, not a modal): severity chips, status chips, technique searchable multi-select, date range (1h/6h/24h/7d/custom), entity free text, "clear all". Filter state reflected in the URL query string (shareable links).

**Real-time row insertion:** on WebSocket `new_alert` — (1) prepend if it passes current filters, (2) 1.5 s yellow-highlight fade animation, (3) increment the `LiveConnectionPill` new-alert counter, (4) if `severity === 'critical'`, also fire a global toast.

**Bulk actions** (appear when ≥1 row selected): "Acknowledge selected" → `POST /api/alerts/bulk-ack`; "Assign to me" → `POST /api/alerts/bulk-assign`; selection count badge.

**Row click** opens the Incident Detail drawer (slides from right, 640px), preserves table scroll position, deep-links to `/incidents/:id` so Back closes the drawer.

## Page: Incident Detail (`/incidents/:id`)

**Header:** auto-generated title (e.g. "Brute-Force Credential Access — prod-db-03"), severity badge, status dropdown, assignee, created/updated timestamps.

Status dropdown is role-gated:
| Action | Analyst | Senior Analyst | Approver |
|---|---|---|---|
| Acknowledge | ✅ | ✅ | ✅ |
| Escalate | ❌ (disabled + tooltip) | ✅ | ✅ |
| Close | ❌ | ✅ | ✅ |

### Tab: Overview
Renders the LLM-generated Markdown report via `react-markdown` + `remark-gfm`: timeline table, entities with links to filtered Alert Queue, up to 5 evidence excerpts (code-block formatted), recommended immediate action.

### Tab: Attack Graph
Renders the Mermaid `graph LR` source via the `mermaid` npm package. Node colors: 🔴 red = confirmed attacker IP, 🟠 orange = victim host, 🟡 yellow = pivot/lateral-movement target, 🔵 blue = benign co-located host (context). Controls: zoom in/out, pan, reset view, download as PNG.

### Tab: MITRE Technique
Card: technique ID + confidence %, name, tactic, official ATT&CK description (loaded from `/api/mitre/technique/:id`), LLM rationale quote, links to the official ATT&CK page and "View in Navigator".

### Tab: Containment Playbook
```
⚠️ DRAFT ONLY — requires Approver authorization
[Syntax-highlighted Ansible YAML / firewall rule snippet]
[Download]  [Approve for Ops ← disabled for non-Approver, tooltip: "Only Approvers can authorize containment runs"]
```
- **Download** — always available, `GET /api/incidents/:id/playbook` → blob download.
- **Approve for Ops** — `RoleGate`-wrapped; Approver-only enabled → `POST /api/incidents/:id/approve` → green confirmation + ledger entry. API independently returns `403` for non-Approver regardless of UI state.

### Tab: Audit Trail
Append-only ledger visualization — each entry shows sequential ID, its own SHA-256 hash, previous-hash link (tooltip confirms chain intact), timestamp, action, actor:
```
Entry #7  [Hash: a3f9d2...] [Prev: 8bc014...]  2026-08-10T09:20:11Z
  Action: PLAYBOOK_APPROVED  Actor: approver@example.com
```

## Page: MITRE Navigator (`/navigator`)

Embeds the official MITRE ATT&CK Navigator web component; auto-loads `layer.json` from `GET /api/navigator/layer.json`. Colors techniques by weekly frequency (grey → yellow → orange → red). Right sidebar: "Top Techniques This Week" — ID + name + count, each links to `/alerts?technique=T####`.

## Page: Ops Metrics (`/ops`)

All Recharts panels, data from `GET /api/metrics`:
| Panel | Chart | Data |
|---|---|---|
| Event Throughput | LineChart (events/sec, 1-min res, last 1h) | `events_ingested_total` |
| Alert Volume Trend | AreaChart (alerts/hr, last 7d) | `alerts_generated_total` |
| Anomaly Score Distribution | Histogram (bins 0.0–1.0) | `anomaly_score_histogram` |
| LLM Cost | BarChart ($/1,000 flagged, daily, last 7d) | token-cost log |
| Pipeline Latency | LineChart (p50/p95, last 1h) | `pipeline_latency_seconds` |

Each panel wraps in a `MetricCard`: title, current value badge, trend arrow vs. previous period, `?` info tooltip.

## Page: Playbook Library (`/playbooks`)

Read-only catalog of `containment_templates`: Brute Force IP Block (T1110.x, `source_ip`), Lateral Movement Segmentation (T1021.x, `pivot_host`/`target_subnet`), DDoS Mitigation (T1498.x, `source_cidrs[]`), Priv-Esc Account Suspend (T1548.x, `user_id`/`host`), Data Exfil Egress Block (T1041.x, `destination_ip`/`port`). Row click → drawer with full Jinja2 template source, syntax-highlighted.

## Shared component inventory

| Component | Props | Notes |
|---|---|---|
| `SeverityBadge` | `level` | Color-coded, ARIA-labeled |
| `TechniqueChip` | `id, name, tactic` | Tooltip shows full tactic |
| `LiveConnectionPill` | `status, newAlerts` | Top-bar WS status |
| `AttackGraph` | `mermaidSource` | Zoom/pan handling |
| `MarkdownReport` | `markdown` | react-markdown + remark-gfm + highlighting |
| `LedgerEntry` | `entry` | Hash + prev-hash with chain-validity indicator |
| `RoleGate` | `requiredRole, children` | Disabled+tooltip if role insufficient |
| `MetricCard` | `title, value, trend, children` | Ops panel wrapper |
| `AlertTable` | `alerts, onRowClick, filters` | Full TanStack Table |
| `SparklineScore` | `scores, current` | Micro line chart, 24h |
| `StatusPill` | `status` | New/Ack/Escalated/Closed colors |

**Hooks:** `useAlertsFeed` (manages WS, pushes into Zustand), `useAuth` (JWT/role, `logout()`, `hasRole()`), `useIncidents`/`useIncidentDetail` (TanStack Query wrappers), `useMitreLayer`, `useMetrics`.

## Performance targets

| Metric | Target |
|---|---|
| Lighthouse Performance (Production) | ≥ 85 |
| Largest Contentful Paint | < 2.5 s on 4G |
| Alert Queue initial load (200 rows) | < 1 s |
| WebSocket message → row visible | < 200 ms |
| Mermaid graph render | < 1 s for ≤50 nodes |
| Bundle size (gzipped JS) | < 400 KB |

## Accessibility & UX standards

All interactive elements have ARIA labels; keyboard-navigable (Tab/Shift-Tab through rows, Enter to open drawer); color is never the sole differentiator (severity always paired with text + icon); error states always show an actionable message (never bare "Error 500"); loading states use skeleton screens, not spinners alone; dark mode applies to every component including Mermaid graphs via CSS variable injection.
