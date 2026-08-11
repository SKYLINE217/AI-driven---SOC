# SOC Triager — Instructions for Engineer B
## Frontend / Platform / DevOps Lead

> **Your role:** You own the platform — the infrastructure that runs everything, the BFF that secures it, the React dashboard that shows it, and the deployment pipeline that delivers it continuously. You are also the integration point: when Engineer A's backend produces data, your code is what turns it into a usable product.
>
> **Daily rhythm:** 09:00 standup (15 min) · 13:00 integration checkpoint (20 min) · 17:30 end-of-day deploy verification (15 min)
>
> **Golden rule:** The Vercel Production URL must be live and functional at the end of every day — not just locally, not just on a feature branch, but on the real URL. Every day's work ships.

---

## Day 1 — Infrastructure, Vercel Deploy, App Shell

### Morning (09:00–12:00)

**1. Attend the architecture kickoff (shared, 09:00–10:30)**
- Lock the ECS event schema — you need the exact field names to write the Alert Queue's column bindings
- Agree on the Pydantic models for `NormalizedEvent`, `FeatureVector`, `ScoreResponse` with Engineer A — these are the API contracts your BFF will proxy
- Confirm the monorepo structure: `soc-triager/frontend/`, `soc-triager/backend/`, etc.

**2. Set up the GitHub repository**

```bash
# Create repo in GitHub UI: soc-triager (private)
# Add branch protection on main: require PR + status checks + no direct push
git init soc-triager && cd soc-triager
git commit --allow-empty -m "Initial commit"
git remote add origin <repo-url>
git push -u origin main
```

**3. Scaffold the React app**

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npx shadcn@latest init   # choose: TypeScript, CSS variables, default style
npx shadcn@latest add button badge card dialog drawer sheet tabs tooltip

npm install @tanstack/react-query @tanstack/react-table
npm install zustand react-router-dom recharts
npm install react-markdown remark-gfm rehype-sanitize mermaid shiki

npm install -D vitest @testing-library/react @testing-library/user-event
npm install -D @testing-library/jest-dom jsdom @playwright/test
```

**4. Build the app shell**

This is the only thing that goes live on Vercel today — but it must go live today.

Build `src/components/layout/AppShell.tsx`, `Sidebar.tsx`, and `TopBar.tsx` with:
- All 6 sidebar links (`/alerts`, `/incidents`, `/navigator`, `/ops`, `/playbooks`, `/settings`)
- Route stubs: each page renders a `<h1>Alert Queue</h1>` placeholder
- Dark/light mode toggle (working — persisted to Zustand)
- `LiveConnectionPill` stub showing "Disconnected" state (WebSocket not wired yet)

All TypeScript types from `src/types/index.ts` must be written today — both you and Engineer A will reference them.

**5. Create the Vercel project**

```
Vercel Dashboard → New Project → Import from GitHub → soc-triager
  Root directory: frontend
  Framework preset: Vite
  Build command: npm run build
  Output directory: dist
```

Set environment variables in Vercel:
- `BACKEND_API_URL` = `http://localhost:8000` (Preview, will update to real VM URL once provisioned)
- `JWT_SECRET` = generate with `openssl rand -base64 32` (same value on both Preview and Production)

**Push and confirm deploy:**
```bash
cd frontend
git add . && git commit -m "Day 1: app shell, routing stubs"
git push origin main
# Wait for Vercel deploy → confirm Production URL renders the sidebar
```

Open a test PR from a `test/preview-deploy` branch → confirm a Preview deployment URL is auto-generated. This per-PR preview is how you'll demo progress every day.

### Afternoon (13:00–17:30)

**6. Stand up the backend Docker Compose**

On the backend VM (Railway, Fly.io, or EC2-class instance):

```bash
cd soc-triager/backend
docker compose up -d redpanda redis postgres mlflow
```

**Create Redpanda topics:**
```bash
docker compose exec redpanda rpk topic create raw.syslog raw.cloudtrail raw.auth raw.cicids \
  normalized.events alerts.raw incidents.updates \
  --partitions 4 --replicas 1
```

**Verify Postgres + TimescaleDB:**
```bash
docker compose exec postgres psql -U soc_user -d soc_triager -c "SELECT version();"
# Should show TimescaleDB in the output

# Run the schema migrations
docker compose exec postgres psql -U soc_user -d soc_triager -f /migrations/001_initial.sql
```

**7. Build the Faust stream processing skeleton**

`backend/stream/faust_app.py` — skeleton only (Engineer A provides the normalizer functions):

```python
import faust
from backend.ingestion.normalizers import get_normalizer

app = faust.App('soc-normalizer', broker='kafka://localhost:9092')

raw_syslog = app.topic('raw.syslog', value_type=bytes)
normalized_events = app.topic('normalized.events', value_type=dict)

@app.agent(raw_syslog)
async def normalize_syslog(stream):
    normalizer = get_normalizer('syslog')
    async for raw_line in stream:
        ecs = normalizer(raw_line.decode())
        await normalized_events.send(value=ecs.model_dump())

if __name__ == '__main__':
    app.main()
```

**8. Implement the replay producer**

`backend/ingestion/replay_producer.py` — reads source files, publishes to Redpanda at configurable speed:

```python
python replay_producer.py --source auth --file data/synthetic_auth_log/brute_force.log --speed 1
# Watch events appear in the Redpanda topic:
docker compose exec redpanda rpk topic consume raw.auth --num 5
```

**End of Day 1 checklist:**
- [ ] GitHub repo created with branch protection
- [ ] React app shell deployed to Vercel Production URL — visible and functional
- [ ] Vercel Preview deployment confirmed working on a test PR
- [ ] `BACKEND_API_URL` and `JWT_SECRET` set in Vercel environment variables
- [ ] Docker Compose running on VM: Redpanda, Redis, Postgres/TimescaleDB, MLflow
- [ ] All Redpanda topics created
- [ ] Postgres schema migrations applied
- [ ] Replay producer sending events to `raw.auth` topic (verify with `rpk consume`)
- [ ] Faust skeleton consuming `raw.syslog` without errors

---

## Day 2 — Scoring API, Alert Pipeline, Alert Queue UI (Mock Data)

### Morning (09:00–13:00)

**1. Build the ML Scoring API**

`backend/ml/scoring_app.py` — FastAPI app that loads the MLflow-registered models:

```python
from fastapi import FastAPI
import mlflow.sklearn, mlflow.pytorch

app = FastAPI()

# Load models from MLflow on startup
isolation_forest = mlflow.sklearn.load_model("models:/isolation_forest/production")
autoencoder = mlflow.pytorch.load_model("models:/autoencoder/production")

@app.post("/score", response_model=ScoreResponse)
async def score(request: ScoreRequest) -> ScoreResponse:
    features = request.features.to_array()
    # Isolation Forest
    if_raw = isolation_forest.score_samples([features])[0]
    if_normalized = normalize_if_score(if_raw)
    # Autoencoder
    ae_score = compute_ae_score(autoencoder, features)
    ensemble = 0.6 * if_normalized + 0.4 * ae_score
    return ScoreResponse(
        score=ensemble,
        threshold=THRESHOLD,
        is_anomaly=ensemble > THRESHOLD,
        top_features=compute_top_features(features),
        model_version="if_v1_ae_v1_ensemble",
        latency_ms=0  # filled in by timing middleware
    )

@app.get("/health")
async def health(): return {"status": "ok"}
```

This service runs on port 8001, internal only. Confirm with Engineer A that the `THRESHOLD` value matches what's in `THRESHOLD_DECISION.md`.

**2. Wire Faust: normalized events → feature store → scoring → alerts**

Extend `faust_app.py`:

```python
@app.agent(normalized_events_topic)
async def score_and_alert(stream):
    async for event in stream:
        features = await feature_store.compute_windowed_features(event)
        score_resp = await scoring_client.score(features)  # HTTP POST to localhost:8001
        if score_resp.is_anomaly:
            alert = build_alert_from_event(event, score_resp)
            await alerts_raw_topic.send(value=alert.model_dump())
```

**3. Implement the Postgres schema**

Run the full schema from `system-architecture.md §5.2` as SQL migrations in `backend/migrations/`.

**4. Set up Prometheus**

Add Prometheus scrape configs for Faust worker (port 9092 metrics) and Scoring API (port 8001 metrics). Verify metrics appear at `http://localhost:9090`.

### Afternoon (13:00–17:30)

**5. Build the Alert Queue page (mock data)**

`frontend/src/pages/AlertQueue.tsx` — fully functional against JSON fixture data:

```typescript
// src/fixtures/alerts.json — matches the exact shape of GET /api/alerts response
// The fixture has 20 realistic-looking alerts with varied severities, techniques, statuses
```

Build the complete Alert Queue:
- TanStack Table with all 7 columns from `dashboard.md §3.3`
- Filter bar with severity, status, technique, date range, entity filters
- Filters reflected in URL query string
- Bulk action bar (select → acknowledge / assign to me)
- Row click → Incident Detail drawer stub (just renders the incident ID for now)

**6. Write the first Playwright E2E test**

```typescript
// frontend/e2e/alert-queue.spec.ts
test('alert queue renders rows and filter works', async ({ page }) => {
  await page.goto('/alerts')
  await expect(page.getByRole('table')).toBeVisible()
  const rows = page.getByRole('row')
  await expect(rows).toHaveCount(21)  // 20 data rows + 1 header

  await page.getByLabel('Filter by severity').click()
  await page.getByText('Critical').click()
  await expect(page.getByRole('row')).toHaveCount(/* only critical rows + header */)
})
```

Add this test to CI. Run it against the local dev server, then against the Vercel Preview URL (`PLAYWRIGHT_BASE_URL` env var).

**7. Push to Vercel**

```bash
git add . && git commit -m "Day 2: alert queue with mock data, scoring API, Faust scoring pipeline"
git push origin main
```

Confirm the Alert Queue is interactive on the Production Vercel URL.

**End of Day 2 checklist:**
- [ ] Scoring API (port 8001) running and returning scores from MLflow models
- [ ] Faust pipeline: normalized events → features → scoring → alerts.raw working end-to-end
- [ ] Alert Queue UI fully interactive on Vercel against mock data
- [ ] Playwright E2E test passing in CI
- [ ] Prometheus metrics visible for Faust worker and Scoring API
- [ ] Confirm with Engineer A: ensemble scores on replayed CICIDS2017 attack traffic are visibly higher than benign traffic

---

## Day 3 — BFF, WebSocket, Live Alert Feed, Auth

### Morning (09:00–13:00)

**1. Build the Vercel BFF layer**

```typescript
// frontend/api/_lib/auth.ts
import jwt from 'jsonwebtoken'

export function verifyJWT(authHeader: string | undefined) {
  if (!authHeader?.startsWith('Bearer ')) return null
  try {
    return jwt.verify(authHeader.slice(7), process.env.JWT_SECRET!) as JWTClaims
  } catch { return null }
}

export function requireRole(claims: JWTClaims, ...roles: Role[]) {
  const effective = ROLE_HIERARCHY[claims.role] ?? []
  return roles.some(r => effective.includes(r))
}
```

Build BFF functions for: `/api/auth/login`, `/api/alerts`, `/api/incidents/*`, `/api/mitre/*`, `/api/navigator/layer.json`, `/api/metrics`.

**2. Build the Edge Middleware**

```typescript
// frontend/middleware.ts
import { NextRequest, NextResponse } from 'next/server'
import { verifyJWT } from './api/_lib/auth'

export const config = { matcher: '/api/:path*' }

export function middleware(req: NextRequest) {
  if (req.nextUrl.pathname === '/api/auth/login') return NextResponse.next()
  const claims = verifyJWT(req.headers.get('authorization') ?? '')
  if (!claims) return NextResponse.json({ error: { code: 'UNAUTHORIZED' } }, { status: 401 })
  // Rate limiting via Upstash Redis (see security.md §6.2)
  return NextResponse.next()
}
```

**3. Build the incident correlation service**

`backend/api/routers/incidents.py` — the service that:
- Consumes `alerts.raw` from Redpanda
- Clusters alerts by `(source_ip, technique_category, 5-min window)`
- Creates new incidents or appends to existing ones
- Triggers LLM triage (calls Engineer A's `triage_client.triage_event_cluster()`)
- Writes the `incident_ledger` entry
- Publishes to `incidents.updates` → Redis Pub/Sub → WebSocket fan-out

**4. Implement the FastAPI WebSocket endpoint**

```python
# backend/api/websocket.py
import redis.asyncio as aioredis
from fastapi import WebSocket, WebSocketDisconnect

redis_client = aioredis.from_url("redis://localhost:6379")

@router.websocket("/ws/alerts")
async def alerts_websocket(ws: WebSocket, token: str):
    claims = verify_jwt(token)
    if not claims:
        await ws.close(code=4001)
        return
    await ws.accept()
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("ws:alerts:broadcast")
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await ws.send_text(message["data"])
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe("ws:alerts:broadcast")
```

### Afternoon (13:00–17:30)

**5. Swap Alert Queue from mock data to live WebSocket**

```typescript
// src/hooks/useAlertsFeed.ts
// Use the wsClient.ts implementation from frontend.md §6
// On initial mount: fetch GET /api/alerts (initial page load)
// On WebSocket message: prependAlert() to Zustand store
// Row highlight animation: use a CSS transition on a `isNew` class applied for 1.5 s
```

**6. Build the mock login page**

`/login` route with three big buttons: "Sign in as Analyst", "Sign in as Senior Analyst", "Sign in as Approver". Each calls `POST /api/auth/login` with the appropriate role and stores the JWT in `authStore`.

**End of Day 3 checklist:**
- [ ] BFF functions for all routes deployed to Vercel
- [ ] Edge Middleware validating JWT on all `/api/*` routes
- [ ] Incident correlation service running, creating incidents in Postgres
- [ ] WebSocket endpoint live and pushing messages through Redis Pub/Sub
- [ ] Alert Queue receiving live WebSocket events — rows animate in
- [ ] Mock login working for all 3 roles
- [ ] Playwright test: wait for WebSocket event to appear as a new row in the table

---

## Day 4 — Incident Detail, All Dashboard Pages, RBAC

### Morning (09:00–13:00)

**1. Build the Incident Detail page**

`frontend/src/pages/IncidentDetail.tsx` with all 5 tabs from `dashboard.md §4`:

- **Overview** — `<MarkdownReport markdown={incident.report_md} />`
- **Attack Graph** — `<AttackGraph mermaidSource={incident.graph_mmd} />`
- **MITRE Technique** — fetch `/api/mitre/technique/:id`, render the card
- **Containment Playbook** — syntax-highlighted playbook + `RoleGate`-wrapped Approve button
- **Audit Trail** — `incident.ledger` entries as `<LedgerEntry />` components

**2. Build the approve flow**

```typescript
async function handleApprove() {
  const note = prompt('Approval note (required):')
  if (!note) return
  await api.approvePlaybook(incidentId, note)
  queryClient.invalidateQueries(['incident', incidentId])
  toast.success('Playbook approved')
}
```

The `RoleGate` wrapper ensures non-Approvers never see this button as enabled. But also write the test that calls the API directly with an analyst JWT and confirms `403`.

### Afternoon (13:00–17:30)

**3. Build all remaining pages**
- **Navigator** (`/navigator`) — embed MITRE ATT&CK Navigator, load layer from `/api/navigator/layer.json`
- **Ops Metrics** (`/ops`) — 5 Recharts panels from `/api/metrics`
- **Playbook Library** (`/playbooks`) — table of `containment_templates` from Postgres via API
- **Settings** (`/settings`) — dark mode toggle, WebSocket debug panel

**4. Write the Helm chart skeleton**

`infra/helm/` — one directory per service (`faust-worker`, `scoring-api`, `incident-api`). Each needs:
- `Deployment.yaml` with resource limits and liveness/readiness probes
- `Service.yaml`
- `ConfigMap.yaml` for non-secret config
- `HPA.yaml` for the Faust worker (scale on CPU) and Scoring API (scale on request rate)

These don't need to deploy — they need to exist and be structurally valid. `helm lint` should pass.

**5. Extended Playwright suite**

```typescript
// frontend/e2e/incident-lifecycle.spec.ts
test('full incident lifecycle', async ({ page }) => {
  // Login as Analyst
  // Navigate to Incidents
  // Open first incident
  // Click through all 5 tabs — assert each renders
  // Attempt approve as Analyst — assert button is disabled
  // Switch role to Approver
  // Approve — assert success toast and ledger entry appears
})
```

**End of Day 4 checklist:**
- [ ] All 5 Incident Detail tabs built and functional with live data
- [ ] RBAC tested: Analyst cannot approve; Approver can approve (UI + direct API call)
- [ ] Navigator page loading real `layer.json` from the API
- [ ] Ops Metrics page showing live data (even if some panels are zeroed)
- [ ] Playbook Library populated from the database
- [ ] Helm charts written and passing `helm lint`
- [ ] Full Playwright lifecycle test passing against Preview URL

---

## Day 5 — Hardening, Load Test, Production Deploy, Demo

### All Day (shared with Engineer A)

**1. Security self-review (your surfaces)**

Run through the security checklist from `security.md §9` — your specific items:

```bash
# No secrets in git
git log --all --oneline | head -20
git show HEAD | grep -E 'ANTHROPIC|JWT_SECRET|POSTGRES'  # should be empty

# NPM audit
cd frontend && npm audit --audit-level=high

# Confirm .env is gitignored
git check-ignore -v backend/.env  # should output "backend/.gitignore:.env"

# Confirm Vercel env vars are set
vercel env ls  # shows BACKEND_API_URL, JWT_SECRET, INTERNAL_SERVICE_TOKEN
```

Verify that the `Approve for Ops` button is unreachable for non-Approver roles both in the UI and via a direct `curl` to the FastAPI endpoint.

**2. Load testing**

```bash
# Install k6
brew install k6  # or download from k6.io

# Write a load test script
cat > load_test.js << 'EOF'
import http from 'k6/http'
import { sleep } from 'k6'
export const options = { vus: 50, duration: '2m' }
export default function () {
  http.get('https://<your-vercel-url>/api/alerts', {
    headers: { Authorization: 'Bearer <analyst-jwt>' }
  })
  sleep(1)
}
EOF

k6 run load_test.js
```

Document the results (p50, p95 latency; error rate) in `docs/EVAL_RESULTS.md`.

**3. Frontend performance pass**

```bash
# Build and preview locally
cd frontend && npm run build && npm run preview

# Check bundle size
ls -la dist/assets/*.js | awk '{print $5, $9}'
# Total gzipped JS should be < 400 KB

# Run Lighthouse via Chrome DevTools on the Production URL
# Target: Performance score >= 85
```

If bundle is oversized: check for `mermaid` being included in the initial bundle (should be lazy-loaded), check for duplicate Recharts imports, run `npm run build -- --report` and analyze the treemap.

**4. Production deploy**

```bash
# Merge the final feature branch PR to main
git checkout main && git merge --no-ff day5-hardening
git push origin main

# Vercel auto-deploys to Production
# Monitor the deploy in the Vercel dashboard

# Tag the release
git tag -a v1.0.0-mvp -m "5-day sprint MVP — $(date +%Y-%m-%d)"
git push origin --tags
```

After deploy, run the full Playwright suite against the Production URL:
```bash
PLAYWRIGHT_BASE_URL=https://<your-production-url>.vercel.app npx playwright test
```

All tests must pass.

**5. Finalize documentation**

Write/complete:
- `README.md` — architecture diagram (copy from `system-architecture.md`), local setup instructions, `docker compose up` one-liner, `vercel dev` command
- `docs/SCALING_PATH.md` — your sections: Vercel → dedicated API gateway, Serverless → long-running containers for BFF, Playwright → cross-browser CI matrix

**6. Demo preparation — your role**

In the 10-minute demo walkthrough, you drive the UI. Your script:

- **T+0:** Show the Production Vercel URL loading
- **T+15s:** Show the WebSocket `Connected` pill
- **T+30s:** As Engineer A starts the replay producer, watch the first row animate into the Alert Queue with a yellow highlight
- **T+1min:** Click the alert → open Incident Detail
- **T+2min:** Show all 5 tabs — especially the Attack Graph (impressive visual) and the Containment Playbook
- **T+3min:** Attempt to approve as Analyst — show the disabled button and tooltip
- **T+4min:** Switch to Approver role → approve → show the success toast and the ledger entry with hash chain
- **T+5min:** Navigate to MITRE Navigator — show the heatmap updating with T1110
- **T+6min:** Show Ops Metrics — LLM cost per 1,000 flagged events, pipeline latency
- **T+8min:** Show the Audit Trail — click a hash chain entry, explain the integrity property
- **T+10min:** Summary — "live Vercel URL, real ML model, real Claude triage, real MITRE ATT&CK, fully auditable, RBAC-enforced"

**End of Day 5 checklist:**
- [ ] Security checklist complete: no secrets in git, `npm audit` clean, RBAC verified
- [ ] Load test run and results documented
- [ ] Lighthouse Performance score ≥ 85 on Production URL
- [ ] All Playwright tests passing against Production URL
- [ ] Final merge to `main` deployed to Vercel Production
- [ ] Release tagged in GitHub
- [ ] README and SCALING_PATH.md complete
- [ ] Demo rehearsed — can drive the full 10-minute UI walkthrough without fumbling
- [ ] Backup screen recording of the demo saved locally (in case of live network issues)
