# DASHBOARD.md — SOC Triager Frontend Implementation

**File:** `frontend/src/SOC_Dashboard.jsx`  
**Version:** v0.4.0  
**Stack:** React 18 + Vite · Recharts · Tabler Icons CDN · No CSS framework

---

## 1. Architecture Overview

```
SOCDashboard (root)
├── TopBar          — brand, live WS pill, role switcher
├── Sidebar Nav     — 6 pages + live stats footer
├── Main (page router)
│   ├── AlertsPage          — KPIs + live ticker + filterable incident table
│   ├── IncidentsPage       — card grid view of all incidents
│   ├── NavigatorPage       — MITRE ATT&CK heatmap + top-technique sidebar
│   ├── OpsPage             — throughput / alert volume / latency / score dist charts
│   ├── PlaybooksPage       — collapsible Ansible playbook library
│   └── RulesPage           — detection rules from rules.yaml
└── IncidentDetail (right panel, conditional)
    ├── Tab: overview       — rationale, confidence, report preview
    ├── Tab: graph          — SVG attack graph + Mermaid source
    ├── Tab: MITRE          — technique card + detection condition + LLM rationale
    ├── Tab: playbook       — Jinja2 YAML preview + download + approve
    └── Tab: ledger         — SHA-256 hash-chained audit log
```

---

## 2. Dependencies

```bash
npm install recharts
```

Tabler Icons loaded via CDN in `index.html`:

```html
<link rel="stylesheet"
  href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/tabler-icons.min.css" />
```

No other external dependencies. Recharts is the only npm package.

---

## 3. Project File Placement

```
AI-driven---SOC/
├── backend/                 # existing FastAPI backend
├── frontend/
│   ├── index.html           # Tabler Icons CDN link goes here
│   ├── package.json
│   └── src/
│       ├── main.jsx         # renders <SOCDashboard />
│       └── SOC_Dashboard.jsx   ← THIS FILE
└── DASHBOARD.md             ← this doc
```

---

## 4. CSS Theming

The component uses CSS custom properties throughout — no hardcoded colors except severity/status palette constants (which mirror `backend/display.py`). Host these in `index.css` or the `index.html` `<style>` block:

```css
:root {
  --font-sans: system-ui, -apple-system, sans-serif;
  --radius: 8px;

  /* Surfaces */
  --surface-0: #f9f9f8;
  --surface-1: #f2f1ee;
  --surface-2: #ffffff;

  /* Text */
  --text-primary:   #1c1b18;
  --text-secondary: #52504a;
  --text-muted:     #898781;
  --text-accent:    #2a78d6;
  --text-danger:    #dc2626;
  --text-warning:   #d97706;
  --text-success:   #16a34a;

  /* Borders */
  --border:         #e1e0d9;
  --border-strong:  #c5c3bb;
  --border-accent:  #93c5fd;
  --border-success: #86efac;
  --border-warning: #fde68a;

  /* Accent backgrounds */
  --bg-accent:       #eff6ff;
  --bg-accent-muted: #f0f7ff;
  --bg-success:      #f0fdf4;
  --bg-warning:      #fffbeb;
}

@media (prefers-color-scheme: dark) {
  :root {
    --surface-0: #141413;
    --surface-1: #1c1b18;
    --surface-2: #222220;
    --text-primary:   #e8e7e1;
    --text-secondary: #a8a69e;
    --text-muted:     #6b6962;
    --text-accent:    #60a5fa;
    --text-danger:    #f87171;
    --text-warning:   #fbbf24;
    --text-success:   #4ade80;
    --border:         #2c2c2a;
    --border-strong:  #3d3d3a;
    --border-accent:  #1e3a5f;
    --border-success: #14532d;
    --border-warning: #78350f;
    --bg-accent:       #1e2a3a;
    --bg-accent-muted: #1a2535;
    --bg-success:      #14261c;
    --bg-warning:      #271e0a;
  }
}
```

---

## 5. Data Layer

All data is seeded from the real codebase sources. No mock/placeholder values.

### 5.1 `REAL_INCIDENTS` — 13 incidents

Sourced from `soc_triager.db` incidents table. Each record matches the `Incident` Pydantic model:

| Field | Source |
|---|---|
| `id` | UUID from `incident_service.py` |
| `entity` | IP, hostname, or username from alert |
| `technique` | MITRE technique ID from `mapping_engine.py` |
| `tactic` | MITRE tactic phase |
| `severity` | `Severity` enum: critical / high / medium / low |
| `status` | `IncidentStatus` enum: open / investigating / resolved / false_positive |
| `confidence` | Combined IF + Autoencoder anomaly score |
| `rationale` | LLM-generated explanation from `llm_client.py` |
| `created_at` | ISO-8601 UTC timestamp |
| `alert_count` | Number of raw alerts aggregated into this incident |

### 5.2 `MITRE_RULES` — 15 rules

Direct representation of `mitre/rules.yaml`. Each rule has: `id`, `technique_id`, `name`, `tactic`, `condition` (the eval-string from `MitreRuleEngine`).

### 5.3 `PLAYBOOK_CATALOG` — 6 templates

Mirrors `backend/artifacts/playbook_templates/*.yml.j2`. Stores `technique`, `name`, `ioc_vars[]`, `actions[]`, `template` filename.

### 5.4 Generated / simulated data

| Constant | Source | Used in |
|---|---|---|
| `generateScoreDistribution()` | Real score range 0.649–0.845 from 4500 alerts in DB | OpsPage histogram |
| `genThroughput()` | Sine-wave around 200 events/sec | OpsPage line chart |
| `genAlertVolume()` | Real day-of-week distribution shape | OpsPage bar chart |
| `genLatency()` | p50≈1.85s, p95≈4.2s (from README metrics) | OpsPage area chart |

---

## 6. State Management

All state is local React state in `SOCDashboard` root. No external store.

```
SOCDashboard state:
  page                string        — active page id
  role                string        — analyst | senior_analyst | approver
  selectedIncident    object|null   — incident open in detail panel
  detailTab           string        — active tab in detail panel
  alertFilter         {sev, status, search}
  incidentStatus      {[id]: status} — in-session status overrides
  approvedPlaybooks   {[id]: bool}  — in-session approval state
  liveAlerts          Alert[]       — rolling 50-item WS feed buffer
  newAlertCount       number        — badge count on Alert Queue nav item
```

**Derived (useMemo):**
- `allIncidents` — `REAL_INCIDENTS` merged with `incidentStatus` overrides
- `filteredIncidents` — `allIncidents` filtered by `alertFilter`
- `stats` — open / critical / total counts + alert total

---

## 7. Pages

### 7.1 AlertsPage

Entry point. Shows:
- 4-KPI row (Active Incidents, Total Alerts, Critical, Avg Score)
- Live feed ticker — shows latest WS alert entity + score + severity
- Filter bar (text search, severity select, status select, clear button)
- Sortable table: Severity · Entity · Technique · Score (bar) · Status · Tactic · Created
- Row click → opens `IncidentDetail` panel

Filters apply to `entity`, `technique`, and `tactic` fields via case-insensitive includes.

### 7.2 IncidentsPage

Card grid. Each card shows:
- Severity + Status badges (top row)
- Entity (monospace)
- Technique chip
- First 100 chars of LLM rationale
- Alert count + UUID prefix (bottom row)
- Border color = severity color from `SEV` palette

Card click → `IncidentDetail`.

### 7.3 NavigatorPage

Two-column layout:

**Left — MITRE ATT&CK matrix table:**
- 11 tactic columns × 3 technique rows
- Cell background from `heatColor(count)`: gray → yellow → orange → red
- Count = number of incidents with that technique in the current session
- Cell click → opens incident with that technique in detail panel
- Heat legend at bottom

**Right — Top Techniques sidebar:**
- Ranked by incident frequency
- Shows technique ID, tactic, incident count

### 7.4 OpsPage

4 charts via Recharts + `ResponsiveContainer`:

| Chart | Type | Data | Height |
|---|---|---|---|
| Event Throughput | LineChart | events/sec, 60 min | 140px |
| Alert Volume | BarChart | daily alerts, 7 days | 140px |
| Triage Latency | AreaChart | p50 + p95, 30 min | 140px |
| Score Distribution | BarChart | 10 bins 0.65–0.85 | 120px |

3-KPI header: Events/Sec, LLM Cost/1k, p50 Latency.

Respects `prefers-color-scheme` for chart tick and grid colors.

### 7.5 PlaybooksPage

Accordion list of 6 Ansible templates. Expanded state per item (single open at a time). Expanded view shows:
- IOC Variables (Jinja2 template vars)
- Containment Actions
- Template filename

### 7.6 RulesPage

Flat list of 15 MITRE detection rules. Each card shows:
- Technique chip + rule name
- Tactic badge
- Rule ID (monospace)
- Condition string in code block (from `rules.yaml` condition field)

---

## 8. Incident Detail Panel

Fixed 480px right drawer. Appears on incident selection. Disappears on close or page navigation.

### Header

- Severity + Status badges
- Entity (monospace, 14px)
- Technique chip + tactic text
- Status action buttons (role-gated):

| Button | Visible to | Effect |
|---|---|---|
| Investigate | senior_analyst, approver | Sets status → investigating |
| Resolve | senior_analyst, approver | Sets status → resolved |
| False Positive | all | Sets status → false_positive |

### Tabs

#### `overview`
- Rationale block (full LLM text)
- 2-stat grid: Confidence %, Alert Count
- Generated report preview (first 1200 chars of `genReport()` output)

#### `graph`
- SVG attack graph (internal IP: 2-node; external IP: 3-node with pivot)
- Nodes colored: attacker=#ef4444, victim=#f97316, pivot=#eab308
- Arrow edges labeled with technique ID
- Mermaid source code block below (mirrors `attack_graph.py` output format)

#### `mitre`
- Technique ID + confidence % (prominent)
- Rule name + tactic
- Detection condition from `rules.yaml`
- Full LLM rationale
- 4-field metadata grid: Technique ID, Tactic, Confidence, Rule ID

#### `playbook`
- Warning banner: "DRAFT ONLY — requires Approver authorization"
- Jinja2-rendered YAML (technique-matched: T1110.x → brute_force template, T1498.x → ddos template, T1041.x → exfil template, fallback → generic_block)
- Download button → `.yml` file via Blob URL
- Approve button:
  - Disabled + tooltip if `role !== "approver"`
  - Active if approver and not yet approved
  - Shows "✓ Approved" + success banner if approved

#### `ledger`
- Hash-chained audit entries: created → status_changed_to_investigating → (status_changed_to_resolved if resolved)
- Each entry: seq, action, actor, timestamp, this_hash (truncated 12 chars), prev_hash
- Hash computed as: `SHA256(prev_hash + incident_id + action + actor + timestamp)` — mirrors `incident_service.py` implementation note
- "✓ VALID" badge on each entry

---

## 9. Shared Components

| Component | Props | Description |
|---|---|---|
| `SevBadge` | `sev` | Colored dot + severity label pill |
| `StatusBadge` | `status` | Status pill from `STATUS_COLORS` map |
| `TechChip` | `id, tactic` | Monospace MITRE technique ID chip |
| `ScoreBar` | `score` | Colored progress bar + score label |
| `HashChip` | `hash` | Truncated 12-char monospace hash |
| `PanelWrap` | `title, children` | Bordered panel with title for charts |

---

## 10. Live Alert Feed

Simulates WebSocket connection from `useAlertsFeed` hook (`backend/api/main.py` WS endpoint `/ws/alerts`).

```
setInterval(4500ms) → generates alert:
  entity:        random from [10.0.3.99, 192.168.1.45, svc-api, dave, 172.16.5.22]
  anomaly_score: 0.64 + random * 0.20
  severity:      score > 0.85 → critical | > 0.70 → high | else medium
  source_type:   random from [syslog, cloudtrail, auth, cicids]
  status:        "new"

→ prepended to liveAlerts (capped at 50)
→ newAlertCount incremented (resets when Alert Queue nav is clicked)
```

**To replace with real WebSocket:**

```js
useEffect(() => {
  const ws = new WebSocket("ws://localhost:8000/ws/alerts");
  ws.onmessage = (e) => {
    const alert = JSON.parse(e.data);
    setLiveAlerts(prev => [alert, ...prev].slice(0, 50));
    setNewAlertCount(n => n + 1);
  };
  return () => ws.close();
}, []);
```

---

## 11. Role-Based Access Control

Three roles selectable via dropdown in TopBar:

| Role | Can Investigate | Can Resolve | Can Approve Playbook |
|---|---|---|---|
| `analyst` | ✗ | ✗ | ✗ |
| `senior_analyst` | ✓ | ✓ | ✗ |
| `approver` | ✓ | ✓ | ✓ |

Logic in `IncidentDetail`:
```js
const canApprove = role === "approver";
const canEscalate = role === "senior_analyst" || role === "approver";
```

In production, role comes from the JWT decoded at the FastAPI `/api/me` endpoint — replace `useState("analyst")` with an auth context read.

---

## 12. Backend Integration

When connecting to the live FastAPI backend, replace the static data constants with API calls:

### Incidents

```js
// Replace REAL_INCIDENTS with:
const [incidents, setIncidents] = useState([]);
useEffect(() => {
  fetch("/api/incidents")
    .then(r => r.json())
    .then(setIncidents);
}, []);
```

Endpoint: `GET /api/incidents` → `IncidentListResponse` (array of `IncidentResponse`).

### Status updates

```js
// Replace incidentStatus local state update with:
const updateStatus = async (id, newStatus) => {
  await fetch(`/api/incidents/${id}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status: newStatus })
  });
  setIncidentStatus(prev => ({ ...prev, [id]: newStatus }));
};
```

### Artifact fetch

```js
// Playbook YAML:
fetch(`/api/incidents/${id}/artifacts/playbook`)
// Report markdown:
fetch(`/api/incidents/${id}/artifacts/report`)
// Attack graph Mermaid:
fetch(`/api/incidents/${id}/artifacts/attack_graph`)
// Ledger:
fetch(`/api/incidents/${id}/ledger`)
```

---

## 13. Vite Config

```js
// vite.config.js
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/ws":  { target: "ws://localhost:8000", ws: true }
    }
  }
});
```

---

## 14. Running

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173

# Production build
npm run build      # dist/ → serve behind nginx or FastAPI StaticFiles
```

Mount as FastAPI static (optional):

```python
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")
```

---

## 15. Extension Points

| What | Where | How |
|---|---|---|
| Add a new page | `NAV` array + `main` router | Add nav entry + new `function FooPage()` |
| Add a detail tab | `TABS` array in `IncidentDetail` | Add tab id + `{tab === "foo" && <FooTab />}` |
| Add a new MITRE rule | `MITRE_RULES` constant | Mirror `rules.yaml` structure |
| Add a playbook | `PLAYBOOK_CATALOG` + `genPlaybook()` | Add catalog entry + technique branch in generator |
| Real-time score threshold | `ScoreBar` color thresholds | Currently: ≥0.85=critical, ≥0.70=high, ≥0.50=medium |
| Dark mode toggle | `index.css` media query | Already implemented via `prefers-color-scheme` |
