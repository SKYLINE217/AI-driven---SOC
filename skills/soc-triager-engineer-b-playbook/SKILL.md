---
name: soc-triager-engineer-b-playbook
description: Use this skill whenever the user is acting as, or asking on behalf of, SOC Triager's "Engineer B — Frontend/Platform/DevOps Lead" and wants to know what to do today, in what order, or with what code/commands — React scaffolding, Vercel deploy, Docker Compose infra, the Faust skeleton, the Scoring API, the BFF, WebSocket, all dashboard pages, RBAC, Helm charts, load testing, or the Day 5 production-deploy/demo checklist for their surfaces. Trigger this for "what should I do next", "give me today's checklist", "write the BFF/component/e2e-test code", or any Day 1–5 task explicitly assigned to Engineer B. This is a personal, sequential, checklist-driven playbook — follow it in order rather than jumping ahead, and check off items against the end-of-day checklists before moving to the next day.
---

# SOC Triager — Engineer B Playbook (Frontend / Platform / DevOps Lead)

> **Your role:** you own the platform — infrastructure, the BFF that secures it, the React dashboard that shows it, and the deployment pipeline that delivers it continuously. You're also the integration point: when Engineer A's backend produces data, your code turns it into a usable product. (See the companion `soc-triager-engineer-a-playbook` skill for their side.)
> **Daily rhythm:** 09:00 standup (15 min) · 13:00 integration checkpoint (20 min) · 17:30 end-of-day deploy verification (15 min).
> **Golden rule:** the Vercel Production URL must be live and functional at the end of *every* day — not just locally, not just on a feature branch. Every day's work ships.

## Day 1 — Infrastructure, Vercel deploy, app shell

**Morning:**
1. Attend the architecture kickoff (09:00–10:30, shared). Lock the ECS event schema (you need exact field names for the Alert Queue's column bindings) and the `NormalizedEvent`/`FeatureVector`/`ScoreResponse` Pydantic models with Engineer A. Confirm the monorepo layout.
2. Create the GitHub repo (private), branch protection on `main` (require PR + status checks, no direct push).
3. Scaffold React: `npm create vite@latest frontend -- --template react-ts`; `npx shadcn@latest init` + add button/badge/card/dialog/drawer/sheet/tabs/tooltip; install `@tanstack/react-query @tanstack/react-table zustand react-router-dom recharts react-markdown remark-gfm rehype-sanitize mermaid shiki`; dev deps `vitest @testing-library/react @testing-library/user-event @testing-library/jest-dom jsdom @playwright/test`.
4. Build the app shell (`AppShell.tsx`, `Sidebar.tsx`, `TopBar.tsx`) — this is the only thing that goes live today, but it **must** go live today: all 6 sidebar links with route stubs (`<h1>Alert Queue</h1>` placeholders), dark/light toggle persisted to Zustand, `LiveConnectionPill` stub showing "Disconnected". Write all shared TypeScript types in `src/types/index.ts` today (Engineer A will also reference them).
5. Create the Vercel project (root `frontend`, framework Vite, build `npm run build`, output `dist`); set env vars `BACKEND_API_URL` (initially `http://localhost:8000`) and `JWT_SECRET` (`openssl rand -base64 32`, same value Preview and Production). Push, confirm Production URL renders the sidebar, and open a test PR to confirm a Preview deployment auto-generates.

**Afternoon:**
6. On the backend VM: `docker compose up -d redpanda redis postgres mlflow`; create Redpanda topics (`raw.syslog raw.cloudtrail raw.auth raw.cicids normalized.events alerts.raw incidents.updates`, 4 partitions/1 replica); verify Postgres+TimescaleDB and run `001_initial.sql`.
7. Build the Faust skeleton (`backend/stream/faust_app.py`) — Engineer A supplies the normalizer functions, you own the agent wiring.
8. Implement the replay producer (`backend/ingestion/replay_producer.py`) and verify events land in `raw.auth` via `rpk topic consume`.

**End of Day 1 checklist:** GitHub repo + branch protection · React app shell live on Vercel Production and visible/functional · Preview deploy confirmed on a test PR · `BACKEND_API_URL`/`JWT_SECRET` set · Docker Compose running (Redpanda/Redis/Postgres/MLflow) · all topics created · migrations applied · replay producer sending to `raw.auth` · Faust skeleton consuming `raw.syslog` without errors.

## Day 2 — Scoring API, alert pipeline, Alert Queue UI (mock data)

**Morning:**
1. Build the ML Scoring API (`backend/ml/scoring_app.py`, FastAPI, port 8001, internal-only) that loads MLflow-registered models on startup and exposes `POST /score` + `GET /health`. Confirm the `THRESHOLD` matches Engineer A's `THRESHOLD_DECISION.md`.
2. Wire Faust: `normalized_events` → `feature_store.compute_windowed_features` → HTTP call to Scoring API → publish to `alerts.raw` if anomalous.
3. Implement the full Postgres schema as migrations (see `soc-triager-system-architecture §Database schema`).
4. Set up Prometheus scrape configs for the Faust worker and Scoring API; verify metrics at `localhost:9090`.

**Afternoon:**
5. Build the Alert Queue page (`frontend/src/pages/AlertQueue.tsx`) fully functional against a 20-row JSON fixture matching the real `GET /api/alerts` shape: TanStack Table with all 7 columns, full filter bar (severity/status/technique/date-range/entity) reflected in the URL, bulk action bar, row-click → Incident Detail drawer stub.
6. Write the first Playwright test (`frontend/e2e/alert-queue.spec.ts`) — table renders, filter narrows rows. Add to CI; run against local dev and the Vercel Preview URL.
7. Push and confirm the Alert Queue is interactive on Production.

**End of Day 2 checklist:** Scoring API running, returning MLflow-model scores · Faust pipeline (normalize→features→score→`alerts.raw`) working end-to-end · Alert Queue interactive on Vercel with mock data · Playwright test passing in CI · Prometheus metrics visible · confirm with Engineer A that ensemble scores are visibly higher on replayed attack traffic than benign.

## Day 3 — BFF, WebSocket, live alert feed, auth

**Morning:**
1. Build the BFF auth helpers (`frontend/api/_lib/auth.ts`): `verifyJWT()`, `requireRole()`. Build BFF functions for `/api/auth/login`, `/api/alerts`, `/api/incidents/*`, `/api/mitre/*`, `/api/navigator/layer.json`, `/api/metrics`.
2. Build the Edge Middleware (`frontend/middleware.ts`) — validates JWT on every `/api/*` route except `/api/auth/login`; wires in rate limiting (Upstash Redis sliding window).
3. Build the incident correlation service (`backend/api/routers/incidents.py`) — consumes `alerts.raw`, clusters by `(source_ip, technique_category, 5-min window)`, creates/updates incidents, calls Engineer A's `triage_client.triage_event_cluster()`, writes the ledger entry, publishes to `incidents.updates` → Redis Pub/Sub → WebSocket fan-out.
4. Implement the FastAPI WebSocket endpoint (`backend/api/websocket.py`) — validates the JWT from the `token` query param, subscribes to `ws:alerts:broadcast` via `redis.asyncio`, streams messages to the client.

**Afternoon:**
5. Swap the Alert Queue from mock data to the live WebSocket using `wsClient.ts` (see `soc-triager-frontend` for the reconnect/heartbeat implementation): initial mount → `GET /api/alerts`; WS message → `prependAlert()` into Zustand; 1.5 s `isNew` highlight class.
6. Build the mock login page (`/login`) with three role buttons, each calling `POST /api/auth/login` and storing the JWT in `authStore`.

**End of Day 3 checklist:** BFF functions deployed for all routes · Edge Middleware validating JWT on all `/api/*` · incident correlation service running, creating Postgres incidents · WebSocket endpoint live via Redis Pub/Sub · Alert Queue receiving live rows that animate in · mock login working for all 3 roles · Playwright test for a WebSocket-driven new row.

## Day 4 — Incident Detail, all dashboard pages, RBAC

**Morning:**
1. Build the Incident Detail page with all 5 tabs (Overview, Attack Graph, MITRE Technique, Containment Playbook with `RoleGate`-wrapped Approve, Audit Trail) — see `soc-triager-dashboard-design` for the exact spec of each tab.
2. Build the approve flow (`handleApprove()` — prompt for a required note, `api.approvePlaybook()`, invalidate the incident query, success toast). `RoleGate` prevents non-Approvers from seeing it enabled — but also write a test that calls the API directly with an analyst JWT and confirms `403` (the UI gate is not the real control).

**Afternoon:**
3. Build the remaining pages: Navigator (embed MITRE ATT&CK Navigator, load `/api/navigator/layer.json`), Ops Metrics (5 Recharts panels from `/api/metrics`), Playbook Library (table of `containment_templates`), Settings (dark mode toggle, WS debug panel).
4. Write the Helm chart skeleton (`infra/helm/`) — one directory per service (`faust-worker`, `scoring-api`, `incident-api`), each with `Deployment.yaml` (resource limits, liveness/readiness probes), `Service.yaml`, `ConfigMap.yaml`, `HPA.yaml` for the worker/scoring services. Don't deploy — must pass `helm lint`.
5. Extended Playwright suite: full incident lifecycle (login → open incident → click through all 5 tabs → attempt approve as Analyst, assert disabled → switch to Approver → approve → assert toast + ledger entry).

**End of Day 4 checklist:** all 5 Incident Detail tabs functional with live data · RBAC tested both in UI and via direct API call · Navigator loading real `layer.json` · Ops Metrics showing live data · Playbook Library populated from the DB · Helm charts pass `helm lint` · full Playwright lifecycle test passing against Preview URL.

## Day 5 — Hardening, load test, production deploy, demo

**All day (shared with Engineer A):**
1. **Security self-review (your surfaces):** confirm no secrets in git history (`git show HEAD | grep -E 'ANTHROPIC|JWT_SECRET|POSTGRES'` should be empty); `npm audit --audit-level=high`; confirm `.env` is gitignored; confirm Vercel env vars are set (`BACKEND_API_URL`, `JWT_SECRET`, `INTERNAL_SERVICE_TOKEN`); verify "Approve for Ops" is unreachable for non-Approvers both in the UI and via a direct `curl`.
2. **Load testing:** write and run a `k6` script against `https://<vercel-url>/api/alerts` with an analyst JWT (50 VUs, 2 min); document p50/p95 latency and error rate in `docs/EVAL_RESULTS.md`.
3. **Frontend performance pass:** `npm run build && npm run preview`; check gzipped bundle size (< 400 KB target); run Lighthouse on the Production URL (target ≥ 85). If oversized, check that `mermaid` is lazy-loaded, check for duplicate Recharts imports, and inspect the `--report` treemap.
4. **Production deploy:** merge the final PR to `main`; confirm Vercel Production deploy; tag the release (`git tag -a v1.0.0-mvp`); run the full Playwright suite against the Production URL with `PLAYWRIGHT_BASE_URL` set — all tests must pass.
5. **Finalize docs:** `README.md` (architecture diagram, local setup, `docker compose up`, `vercel dev`), your sections of `docs/SCALING_PATH.md` (Vercel → dedicated API gateway, Serverless → long-running BFF containers, Playwright → cross-browser CI matrix).
6. **Demo prep (you drive the UI):** T+0 Production URL loads; T+15s WS `Connected` pill; T+30s first row animates in as Engineer A starts the replay producer; T+1min open Incident Detail; T+2min show all 5 tabs; T+3min attempt approve as Analyst (disabled + tooltip); T+4min switch to Approver, approve, show toast + ledger; T+5min Navigator heatmap; T+6min Ops Metrics; T+8min Audit Trail hash chain; T+10min summary line: "live Vercel URL, real ML model, real Claude triage, real MITRE ATT&CK, fully auditable, RBAC-enforced."

**End of Day 5 checklist:** security checklist complete · load test documented · Lighthouse ≥ 85 on Production · all Playwright tests pass against Production · final merge deployed · release tagged · README + SCALING_PATH complete · demo rehearsed end-to-end · backup screen recording saved locally.

## Related skills

For the shared architecture/schema/API contract, consult `soc-triager-system-architecture`, `soc-triager-frontend`, `soc-triager-dashboard-design`, and `soc-triager-api-reference`. For the RBAC/JWT enforcement rules behind Day 3-4-5 work, consult `soc-triager-security` and `soc-triager-cia-triad-access-control`. For the overall sprint context and non-goals, consult `soc-triager-plan`.
