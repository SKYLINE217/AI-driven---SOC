# AI-Driven SOC Triager & MITRE ATT&CK Incident Manager
## Industrial-Grade 5-Day Build Sprint — 2-Engineer Execution Plan (React + Vercel Edition)

**Document version:** 2.0
**Team size:** 2 engineers
- **Engineer A — ML/Data/Backend Lead:** ingestion, streaming, feature engineering, anomaly detection models, LLM triage, MITRE mapping, evaluation
- **Engineer B — Frontend/Platform/DevOps Lead:** React dashboard, API gateway (BFF), auth/RBAC, Vercel CI/CD, testing infrastructure, backend service deployment

**Duration:** 5 working days, 8–9 focused hours/engineer/day (~85 person-hours total)
**Target bar:** A working, demo-able, publicly-reachable MVP (shareable Vercel URL) that follows enterprise SOC architecture patterns (SIEM/SOAR-adjacent), is horizontally scalable, auditable, continuously deployed, and safe to pitch to a security engineering org as a credible pilot proposal.

---

## 1. Executive Summary

This plan builds a **real-time log ingestion → ML anomaly detection → LLM-based severity/context scoring → MITRE ATT&CK TTP mapping → automated incident artifact generation → containment playbook drafting** pipeline, wrapped in an operational SOC dashboard built in **React** and continuously deployed to **Vercel**.

```
[Log Sources] → [Ingestion/Streaming Layer] → [Normalization & Enrichment]
      → [ML Anomaly Detection Engine] → [LLM Contextual Triage Layer]
      → [MITRE ATT&CK Mapping Engine] → [Incident Correlation & Case Mgmt]
      → [Artifact Generator (reports, attack graphs, playbooks)]
      → [BFF / API Gateway] → [React SOC Dashboard on Vercel]
```

**Why split this way:** the heavy, stateful backend (Kafka-compatible streaming bus, ML training/serving, Postgres, LLM calls) cannot live on Vercel's serverless edge runtime — it needs long-running processes and persistent connections. So the architecture is deliberately **two-tier**:

1. **Backend tier** (Engineer A owns the data/ML pieces, Engineer B owns the platform pieces) — runs in Docker Compose on a cloud VM (Railway / Fly.io / a plain EC2-class box; any works) for the sprint, exposed over HTTPS.
2. **Frontend + BFF tier** (Engineer B) — a React (Vite) SPA plus a thin Vercel Serverless/Edge Function layer that proxies, caches, and auth-gates calls to the backend tier. This tier deploys to **Vercel**, giving the team automatic preview URLs per pull request, instant rollbacks, and a real production URL to demo from on Day 5.

**Non-negotiable engineering principles:**
1. **Streaming-first, not batch-first** — the MVP consumes logs as an unbounded stream (Redpanda/Kafka-API), never just reads CSVs in a notebook.
2. **Explainability** — every anomaly score and MITRE mapping carries a human-readable justification (feature attribution + LLM rationale).
3. **Human-in-the-loop by default** — containment scripts are **drafted, never auto-executed**. Hard product/safety boundary.
4. **Auditability** — every pipeline stage writes immutable, timestamped, hash-chained records (append-only incident ledger).
5. **Model + data versioning** from day one (MLflow).
6. **Continuous deployment from day one** — the React app deploys to Vercel on the very first commit (even as a "hello dashboard" shell), so every subsequent day ships an improving, testable, shareable preview link rather than a big-bang Day 5 deploy.

---

## 2. Team Roles & Ownership

| | **Engineer A — ML/Data/Backend Lead** | **Engineer B — Frontend/Platform/DevOps Lead** |
|---|---|---|
| Primary ownership | Log parsing/normalization, streaming pipeline logic, feature engineering, Isolation Forest + Autoencoder models, LLM triage prompt engineering, MITRE mapping logic, evaluation report | React dashboard (all pages/components), BFF/API gateway, auth + RBAC, Vercel project setup & CI/CD, backend infra (Docker Compose, VM hosting, Postgres/Redis/Redpanda ops), testing infrastructure (unit + E2E) |
| Secondary support | Reviews API contracts against dashboard needs; sanity-checks UI copy for analyst usability | Helps wire feature-store/API integration points; reviews model output shapes for UI/latency fit |
| Daily rhythm | 09:00 standup (15 min) · 13:00 integration checkpoint (20 min) · 17:30 end-of-day demo + Vercel deploy verification (15 min) |

**Shared responsibilities:** architecture lock (Day 1 AM), ECS event schema, MITRE schema, security review of containment templates, Vercel environment variable/secrets policy, final demo script (Day 5).

---

## 3. Reference Architecture

### 3.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                  LOG SOURCES (simulated + real-format)                │
│  Syslog │ AWS CloudTrail (JSON, synthetic) │ Linux auth.log (synth)   │
│  CICIDS2017 flow CSVs │ Elastic sample "Security" dataset             │
└───────────────────────────────┬───────────────────────────────────────┘
                                 │ Fluent Bit / Python replay producer
                                 ▼
                 ┌───────────────────────────────┐
                 │  REDPANDA (Kafka-API compat)   │   ── BACKEND TIER ──
                 │  topic per source               │      (Docker Compose
                 └───────────────┬─────────────────┘       on Railway/Fly.io/VM)
                                 ▼
                 ┌───────────────────────────────┐
                 │  STREAM PROCESSOR (Faust)      │
                 │  parse → normalize (ECS) →     │
                 │  enrich (GeoIP/ASN)            │
                 └───────────────┬─────────────────┘
                                 ▼
                 ┌───────────────────────────────┐
                 │  FEATURE STORE                 │
                 │  Redis (hot, windowed) +       │
                 │  TimescaleDB (cold, historical)│
                 └───────────────┬─────────────────┘
                                 ▼
        ┌────────────────────────────────────────────────┐
        │  ML ANOMALY DETECTION ENGINE (FastAPI /score)    │
        │  Isolation Forest + Autoencoder → ensembled score │
        └───────────────────┬──────────────────────────────┘
                             ▼ if score > threshold
        ┌────────────────────────────────────────────────┐
        │  LLM CONTEXTUAL TRIAGE (Claude API, structured   │
        │  JSON: severity, confidence, rationale, MITRE     │
        │  candidate re-ranking)                             │
        └───────────────────┬──────────────────────────────┘
                             ▼
        ┌────────────────────────────────────────────────┐
        │  MITRE ATT&CK MAPPING ENGINE (mitreattack-python) │
        └───────────────────┬──────────────────────────────┘
                             ▼
        ┌────────────────────────────────────────────────┐
        │  INCIDENT CORRELATION / CASE MGMT (FastAPI +       │
        │  Postgres source of truth + hash-chained ledger)   │
        └───────────────────┬──────────────────────────────┘
                             ▼
        ┌────────────────────────────────────────────────┐
        │  ARTIFACT GENERATION SERVICE                       │
        │  Markdown report │ Mermaid attack graph │           │
        │  Ansible/firewall containment playbook (draft only) │
        └───────────────────┬──────────────────────────────┘
                             ▼  HTTPS (REST + WebSocket)
        ┌────────────────────────────────────────────────┐   ── FRONTEND TIER ──
        │  VERCEL EDGE / SERVERLESS FUNCTIONS (BFF layer)   │     (Vercel, global CDN,
        │  - proxies + caches API calls                      │      preview + prod)
        │  - issues/validates short-lived JWTs                │
        │  - rate-limits public routes                        │
        └───────────────────┬──────────────────────────────┘
                             ▼
        ┌────────────────────────────────────────────────┐
        │  REACT + TYPESCRIPT SOC DASHBOARD (Vite build,     │
        │  deployed as a Vercel static/SSR app, WebSocket     │
        │  client for live alert feed)                        │
        └────────────────────────────────────────────────┘
```

### 3.2 Data Flow Contract (ECS-inspired schema)

```json
{
  "@timestamp": "2026-08-10T09:14:22.104Z",
  "event": { "kind": "event", "category": ["authentication"], "action": "ssh_login_failed", "outcome": "failure" },
  "source": { "ip": "203.0.113.44", "geo": {"country_iso_code": "RU"}, "as": {"number": 48693} },
  "destination": { "ip": "10.0.4.12", "port": 22 },
  "user": { "name": "svc-backup", "id": "u-2291" },
  "host": { "name": "prod-db-03", "os": {"family": "linux"} },
  "log": { "source_type": "auth_log", "raw": "<original line, preserved for forensics>" },
  "related": { "hash": "sha256:...(for chain-of-custody)" }
}
```

**Normalize once, reason forever.** Both engineers must agree on this schema in the Day 1 kickoff before any code is written — it is the contract that lets Engineer A's backend and Engineer B's frontend/BFF develop in parallel against a shared shape from hour one.

---

## 4. Technology Stack (industrial-grade, justified)

| Layer | Technology | Why |
|---|---|---|
| Streaming bus | **Redpanda** (Kafka-API compatible, single binary) | De facto SOC ingestion backbone pattern, low ops overhead for a 5-day build |
| Log shipping | **Fluent Bit** | CNCF-graduated, lightweight, native Kafka output |
| Stream processing | **Python + Faust** | Keeps team in Python; document Flink as the scale-out path |
| Feature store (hot) | **Redis** (sorted sets, sliding windows) | Sub-millisecond lookups for real-time scoring |
| Feature store (cold) | **TimescaleDB** (Postgres extension) | SQL-native time series, analyst-queryable |
| ML — anomaly detection | **scikit-learn IsolationForest** + **PyTorch autoencoder**, ensembled | Fast + interpretable, industry-proven on tabular network/auth data |
| Experiment tracking | **MLflow** (local, SQLite backend) | Full param/metric/artifact lineage — no "worked on my laptop" models |
| LLM triage | **Claude (Sonnet-class) via Anthropic API**, structured/tool-use JSON output | Grounded contextual reasoning + analyst-readable rationale |
| MITRE mapping | **`mitreattack-python`** + pinned STIX 2.1 Enterprise ATT&CK corpus | Official, auditable TTP source of truth |
| Case/incident store | **PostgreSQL 16** | ACID source of truth; append-only hash-chained `incident_ledger` |
| Backend API | **FastAPI** (async, OpenAPI auto-docs, Pydantic validation) | Enterprise-standard, self-documenting |
| Real-time push | **WebSockets (FastAPI native)** + Redis Pub/Sub fan-out | Live alert feed, no polling |
| **Frontend** | **React 18 + TypeScript + Vite**, **shadcn/ui**, **Recharts**, official **MITRE ATT&CK Navigator** JS embed, **TanStack Query** for data fetching/caching, **Zustand** for lightweight client state | Modern, testable, fast-building SPA stack; using the real Navigator widget is a strong "industrial-grade" signal |
| **BFF / API gateway** | **Vercel Serverless Functions** (Node/TypeScript) or **Vercel Edge Functions** for auth checks | Keeps secrets off the client, enables per-route rate limiting/caching at the edge, sits natively inside the Vercel deploy |
| **Deployment (frontend)** | **Vercel** — Git-connected project, automatic Preview Deployments per PR, Production deployment on `main` merge | Instant shareable URLs for every day's progress; zero-config CDN, rollback, and env-var management |
| **Deployment (backend)** | **Docker Compose** on **Railway** or **Fly.io** (or any Docker-capable VM) for the sprint; documented **Kubernetes/Helm** path for real scale | Backend needs long-lived stateful processes Vercel's serverless model doesn't support |
| Attack graph rendering | **Mermaid.js** (server-generates syntax, client renders via `mermaid` npm package inside React) | Trivially embeddable in both the dashboard and Markdown incident reports |
| Containment playbooks | Jinja2-templated **Ansible playbook** + firewall rule snippets | SOC/IT-ops lingua franca; nothing auto-executes |
| Auth/AuthZ | **JWT (short-lived) + RBAC** (Analyst / Senior Analyst / Approver), issued by the Vercel BFF, validated by both BFF and FastAPI | Real role separation, especially for the "approve containment" action |
| CI/CD | **GitHub Actions** (lint/test/build for backend) + **Vercel's built-in Git integration** (build/deploy/preview for frontend) | Standard hygiene; Vercel handles frontend CI/CD natively |
| Testing | **Vitest** (frontend unit tests) + **React Testing Library** (component tests) + **Playwright** (E2E, run against live Vercel Preview URLs) + **pytest** (backend unit/integration) | Tests run against *real deployed preview environments*, not just localhost — catches integration/env issues early |
| Observability | **Prometheus + Grafana** (backend ops) + **Vercel Analytics/Speed Insights** (frontend) + `structlog` (structured JSON logs) | Full-stack observability including the frontend's own delivery performance |
| Secrets | Vercel **Environment Variables** (Preview/Production scoped) + `.env`/`python-dotenv` on the backend VM, with documented **HashiCorp Vault** migration path | Never hardcode API keys; Vercel's env-var UI covers the frontend/BFF secret surface cleanly |
| Datasets | **CICIDS2017** subsets, **Elastic** sample security logs, synthetic **AWS CloudTrail** JSON, synthetic **Linux auth.log** | Labeled academic IDS data (precision/recall validation) + realistic enterprise formats (schema/UX realism) |

---

## 5. React Dashboard — Detailed UX/Screen Concepts

This is the artifact stakeholders actually see and judge, so it gets full specification up front. Engineer B builds against this spec starting Day 1.

### 5.1 App shell & navigation
- Left sidebar (collapsible): **Alert Queue**, **Incidents**, **MITRE Navigator**, **Ops Metrics**, **Playbook Library**, **Settings**.
- Top bar: live connection status pill (WebSocket connected/reconnecting/down), role switcher (dev-only, Analyst/Senior Analyst/Approver), search box (entity/IP/technique ID), dark/light toggle.
- Global toast system for new-critical-alert notifications.

### 5.2 Page — Alert Queue (`/alerts`)
- Sortable, filterable data table (TanStack Table): columns = Severity badge, Timestamp, Entity (host/user/IP), MITRE Technique chip, Anomaly Score (mini sparkline), Status (New/Ack/Escalated/Closed), Assignee.
- Filters: severity multi-select, technique multi-select, date range, free-text entity search.
- Row click → slides in an **Incident Detail** drawer (or navigates to `/incidents/:id`).
- New rows animate in via the WebSocket feed with a subtle highlight-fade — this is the "real-time SOC feel" moment that sells the demo.
- Bulk action bar: acknowledge selected, assign to me.

### 5.3 Page — Incident Detail (`/incidents/:id`)
- Header: incident title (auto-generated, e.g. "Brute-Force Credential Access — prod-db-03"), severity badge, status dropdown (role-gated).
- Tabs:
  - **Overview:** rendered Markdown incident report (timeline, entities, evidence excerpts).
  - **Attack Graph:** embedded Mermaid graph (nodes = hosts/users/IPs, edges = observed interactions, colored by role: attacker/victim/pivot), zoom/pan.
  - **MITRE Technique:** card with technique ID, name, tactic, official description pulled from the ATT&CK corpus, confidence score, LLM rationale text.
  - **Containment Playbook:** rendered Jinja2-generated Ansible/firewall snippet, syntax-highlighted, with **Download** button and an **"Approve for Ops"** button — disabled and tooltip-explained for `Analyst` role, enabled only for `Approver` role (real RBAC, verified against the API, not just hidden in the UI).
  - **Audit Trail:** append-only ledger entries for this incident (hash-chain visualization — each entry shows its hash and previous-hash link, a nice concrete "auditability" visual).

### 5.4 Page — MITRE ATT&CK Navigator (`/navigator`)
- Embeds the official MITRE ATT&CK Navigator web component, auto-loaded with a generated `layer.json` heatmap reflecting technique frequency across the current incident set.
- Sidebar list of "top techniques this week" with counts, linking back to filtered Alert Queue views.

### 5.5 Page — Ops Metrics (`/ops`)
- Recharts panels sourced from Prometheus (via a small `/api/metrics` BFF proxy): event throughput (events/sec), alert volume trend (24h/7d), anomaly score distribution histogram, LLM cost-per-1000-flagged-events, end-to-end pipeline latency (p50/p95).
- This page is explicitly built to answer "what does this cost and how fast is it" — the first questions a stakeholder asks.

### 5.6 Page — Playbook Library (`/playbooks`)
- Read-only catalog of the Jinja2 containment templates in the system (brute force → IP block + lockout, lateral movement → segmentation ACL, etc.), so reviewers can audit *what the system is capable of recommending* without digging into the repo.

### 5.7 Component inventory (shared, Storybook-documentable if time allows)
`SeverityBadge`, `TechniqueChip`, `LiveConnectionPill`, `AttackGraph`, `MarkdownReport`, `LedgerEntry`, `RoleGate` (wraps any action button, enforces RBAC client-side as a UX nicety while the API enforces it server-side as the real control), `MetricCard`, `AlertTable`.

---

## 6. Backend — API & Service Detail

### 6.1 FastAPI endpoints (behind the Vercel BFF)
```
GET    /api/alerts                     # filterable, paginated
GET    /api/incidents                  # filterable, paginated
GET    /api/incidents/{id}
GET    /api/incidents/{id}/timeline
GET    /api/incidents/{id}/ledger
POST   /api/incidents/{id}/status      # acknowledge / escalate / close
POST   /api/incidents/{id}/approve     # role-gated: Approver only
GET    /api/incidents/{id}/report.md   # generated markdown
GET    /api/incidents/{id}/graph.mmd   # generated mermaid source
GET    /api/incidents/{id}/playbook    # generated Ansible/firewall snippet
GET    /api/navigator/layer.json       # MITRE Navigator layer export
GET    /api/metrics                    # Prometheus-sourced summary for /ops page
POST   /api/score                      # internal: feature vector -> anomaly score
WS     /ws/alerts                      # live push channel
```

### 6.2 Vercel BFF responsibilities
- Issues short-lived JWTs on mock login (role selector for the demo; documented OIDC/SSO path for production).
- Validates JWT + role claim on every proxied request before forwarding to FastAPI.
- Applies per-IP rate limiting on public routes (Vercel Edge Middleware).
- Caches read-heavy, low-churn responses (e.g., MITRE technique descriptions) at the edge.
- Injects the backend's internal API base URL from a Vercel environment variable so it's never exposed to the client bundle.

### 6.3 Postgres schema (core tables)
`raw_events` (hypertable), `normalized_events`, `entities`, `alerts`, `incidents`, `incident_ledger` (append-only, `sha256(prev_hash + payload)` chained), `users` (role claims), `containment_templates`.

---

## 7. MITRE ATT&CK Integration Detail

- **Corpus:** pull the official `enterprise-attack.json` STIX bundle from MITRE's `cti` GitHub repo, pin a specific version (`/data/mitre/enterprise-attack-v15.1.json`), load via `mitreattack.stix20.MitreAttackData`.
- **Two-stage mapping (avoids LLM hallucination of technique IDs):**
  1. **Heuristic candidate generation** — a rules table maps observable event patterns to a shortlist of 1–5 candidate technique IDs (e.g., high-frequency `ssh_login_failed` from one source IP → candidate `T1110`).
  2. **LLM re-ranking + rationale** — Claude receives the normalized event(s), anomaly score, and the *candidate list only* (never invents IDs), returning one of the provided IDs plus rationale and confidence.
- **Output schema (structured/tool-use):**
```json
{
  "technique_id": "T1110.001",
  "technique_name": "Brute Force: Password Guessing",
  "tactic": "Credential Access",
  "confidence": 0.87,
  "rationale": "17 failed SSH auth attempts from 203.0.113.44 against 4 distinct service accounts within 90 seconds, consistent with automated password guessing rather than user error.",
  "severity": "high",
  "recommended_immediate_action": "Block source IP at edge firewall; force credential rotation for targeted accounts"
}
```
- **Navigator export:** every incident set generates a MITRE ATT&CK Navigator-compatible `layer.json`, consumed directly by the `/navigator` React page.

---

## 8. LLM Triage Layer — Prompting & Safety Design

- **Structured output only** — forced-schema Claude calls validated against a Pydantic model; reject/retry (max 2, with backoff) on schema failure.
- **Context window discipline** — never send raw firehose logs. Only flagged events + ±5 min surrounding context for the same host/user/IP, capped at ~30 events.
- **Batching** — cluster near-duplicate anomalies (same source IP/technique/time window) before calling the LLM once per cluster.
- **Guardrails in the system prompt:** only select from provided MITRE candidate IDs; never fabricate IOCs/CVEs/asset names not present in input; containment recommendations phrased as *drafts for analyst approval*, never as already-executed actions.
- **Cost/latency tracking** — every call logged with token counts + latency; Day 4 produces an explicit cost-per-1,000-flagged-events benchmark, surfaced on the `/ops` dashboard page.

---

## 9. Anomaly Detection ML Design

### 9.1 Feature engineering (per entity, sliding window)
Per `(host, user, source_ip)` over 1-min / 5-min / 1-hr windows: event count, distinct destination ports, failed-vs-success auth ratio, bytes transferred, unique destination IP fan-out (lateral movement signal), time-of-day z-score deviation, process lineage depth, geo-velocity (impossible travel).

### 9.2 Models
- **Isolation Forest** (`n_estimators=200`, `contamination='auto'`) on CICIDS2017 baseline + synthetic features. <5ms/inference, interpretable via path-length contribution.
- **Autoencoder** (PyTorch, 3-layer symmetric bottleneck, trained on "normal" windows only) — reconstruction error as anomaly score, catches subtler behavioral drift.
- **Ensembling:** weighted average of normalized IF score and AE reconstruction-error percentile; threshold tuned to **recall ≥ 0.90 at precision ≥ 0.75** on held-out CICIDS2017 attack days.
- **Explainability:** log top-3 contributing features per score (SHAP `TreeExplainer` if time allows, else path-length deltas) — feeds the LLM prompt so rationale is grounded in real signal.

---

## 10. Day-by-Day Execution Plan

### **DAY 1 — Architecture Lock, Ingestion Pipeline, First Vercel Deploy**

**Shared (09:00–10:30):** Lock the ECS event schema (§3.2), agree repo structure (monorepo: `/backend /frontend /infra /data /docs`), create GitHub repo with branch protection, connect the repo to a new **Vercel project** (Import Project → set root directory to `/frontend`, framework preset = Vite). Provision the Anthropic API key as a Vercel + backend-VM environment variable; wire a one-off "hello world" Claude structured-output call to validate access end-to-end.

**Engineer A (ML/Data/Backend):**
- Download/inspect CICIDS2017 subsets (Wed working-hours, Fri DDoS/PortScan) and Elastic sample security datasets.
- Write source-format → ECS normalizer functions with unit tests per source type.
- Build synthetic AWS CloudTrail JSON and Linux `auth.log` generators with injected attack patterns (brute force, privilege escalation, impossible travel).
- Stand up MLflow tracking (local Docker) and log a trivial baseline run to confirm the harness.

**Engineer B (Frontend/DevOps):**
- Scaffold the React app: `npm create vite@latest frontend -- --template react-ts`, install shadcn/ui, TanStack Query/Table, Recharts, Zustand, React Router.
- Build the app shell (§5.1: sidebar, top bar, routing stubs for all six pages) with placeholder content — this is what goes live on Vercel today.
- **First Vercel deploy:** push to `main`, confirm the Production URL renders the shell; open a test PR to confirm a **Preview Deployment** URL is generated automatically — this per-PR preview flow is what the team will use for review/testing every day going forward.
- Stand up backend `docker-compose.yml` on the hosting VM: Redpanda, Redis, Postgres/TimescaleDB, MLflow, placeholders for FastAPI.
- Create Redpanda topics: `raw.syslog`, `raw.cloudtrail`, `raw.auth`, `raw.cicids`.
- Implement a lightweight Python replay producer (pragmatic substitute for full Fluent Bit tuning within the sprint) streaming sample files into topics at controllable replay speed.
- Implement the Faust stream-processing skeleton: consumes raw topics, calls Engineer A's normalizers, writes ECS events to `normalized.events`, persists to TimescaleDB.

**Testing/QA today:** Vitest installed with one smoke test (`App renders sidebar`); `pytest` installed with normalizer unit tests passing in CI (GitHub Actions workflow added, even if minimal).

**End of Day 1 deliverable:** (1) Logs flow file → Redpanda → Faust normalizer → ECS events in TimescaleDB, verifiable via `psql`. (2) A live Vercel Production URL showing the dashboard shell, plus a confirmed working Preview Deployment on a test PR.

---

### **DAY 2 — Feature Engineering, ML Training, Feature Store, Alert Queue UI (Mocked Data)**

**Engineer A (ML/Data):**
- Implement windowed feature computation (§9.1) as a Faust agent, writing to Redis (hot) and TimescaleDB (cold).
- Train Isolation Forest on CICIDS2017 labeled split; log full metrics (precision, recall, F1, ROC-AUC) to MLflow.
- Build and train the PyTorch autoencoder on the same feature space; log training curves and reconstruction-error distributions.
- Build ensembling/thresholding logic; produce a precision-recall curve artifact and document the chosen operating threshold in `/backend/ml/THRESHOLD_DECISION.md`.

**Engineer B (Platform/Frontend):**
- Build the **model serving service** (`/api/score`, FastAPI): loads latest MLflow-registered model, accepts a feature vector, returns anomaly score + top contributing features, with async batching.
- Wire Faust: normalized events → feature lookup → call scoring service → if score > threshold, publish to `alerts.raw`.
- Implement Postgres schema: `incidents`, `alerts`, `entities`, `incident_ledger` (hash-chained).
- Set up Prometheus metrics endpoints on the Faust worker and FastAPI service.
- **Frontend:** build the Alert Queue page (§5.2) fully against a mocked/fixture data set (JSON fixtures matching the real API shape) — sortable/filterable table, severity badges, sparkline scores. This unblocks UI progress without waiting on live data, and the fixture shape is locked to the real `GET /api/alerts` contract so swapping in live data later is a one-line change.
- Push to Vercel; confirm the Alert Queue is reviewable on the Preview URL, and write the first **Playwright** E2E test (`alert queue renders N rows, filter by severity works`) run against that Preview URL in CI.

**End of Day 2 deliverable:** End-to-end scoring pipeline running live on the backend (replayed CICIDS2017 attack traffic produces visibly higher anomaly scores than benign traffic in Grafana). Alert Queue UI fully interactive on a shareable Vercel Preview URL against realistic mock data, with a passing Playwright test in CI.

---

### **DAY 3 — MITRE Mapping + LLM Triage + BFF Wiring + Live WebSocket Feed**

**Engineer A (ML/Data):**
- Integrate `mitreattack-python`, load and pin the ATT&CK Enterprise STIX bundle.
- Build the heuristic candidate-generation rule table (~15–20 rules covering brute force, port scan, DDoS, privilege escalation, impossible travel, lateral-movement fan-out, exfil-volume spike — mapped to CICIDS2017 attack categories present in the data).
- Build the Claude structured-output client (§8): Pydantic response model, guardrail system prompt, retry/validation logic, unit tests with mocked responses plus live integration tests against real Day-2 flagged events.
- Implement alert clustering (`entity + technique + time-window`) to batch LLM calls.

**Engineer B (Platform/Frontend):**
- Build the **incident correlation service**: consumes `alerts.raw`, applies clustering keys, creates/updates `incidents`, calls Engineer A's MITRE/LLM triage module, writes enriched incidents to Postgres + `incident_ledger`.
- Implement the remaining FastAPI REST endpoints (§6.1) and the `/ws/alerts` WebSocket channel.
- **Build the Vercel BFF layer:** Serverless Functions under `/frontend/api/*` that proxy each backend route, plus an Edge Middleware function that validates the mock-login JWT and role claim before forwarding requests. Set the backend base URL as a Vercel environment variable (Preview and Production scoped separately, so Preview deployments can safely point at a staging backend).
- Swap the Alert Queue from fixtures to the live `/ws/alerts` WebSocket feed via the BFF; add the connection-status pill (§5.1) and row highlight-fade animation.
- Add mock-login page with the Analyst/Senior Analyst/Approver role selector (§5.1, §6.2).

**Testing/QA today:** Playwright test extended to assert a live WebSocket-pushed row appears in the table within N seconds on the Preview URL (using the replay producer to generate a real event during the test run). `pytest` integration test for the MITRE/LLM client against recorded fixtures.

**End of Day 3 deliverable:** A flagged anomaly automatically produces a full incident record with a real MITRE technique ID, tactic, confidence, and LLM rationale — visible via the API and rendering live in the React Alert Queue through the Vercel BFF and WebSocket feed. Demo: replay an attack window and watch a correctly classified `T1110` (brute force) or `T1498` (DDoS) incident appear in the UI within seconds, end to end, on a public Vercel Preview URL.

---

### **DAY 4 — Incident Detail, Attack Graphs, Containment Playbooks, Navigator, Ops Page, RBAC**

**Engineer A (ML/Data):**
- Build the **artifact generation service**: (a) Markdown incident report generator, (b) Mermaid attack-graph definition generator (nodes = hosts/users/IPs, edges = interactions, colored by role: attacker/victim/pivot), (c) containment playbook generator — Jinja2 selects the right Ansible/firewall template by technique category, populated with observed IOCs.
- Run the full evaluation suite against held-out CICIDS2017 attack days + synthetic scenarios; write `/docs/EVAL_RESULTS.md` with precision/recall/F1, MITRE-mapping accuracy, and LLM cost/latency benchmarks. Compute the enterprise-volume cost extrapolation (e.g., "at 50M raw events/day → ~2,000 flagged anomalies/day → estimated LLM cost $X/day").

**Engineer B (Platform/Frontend):**
- Build the **Incident Detail page** (§5.3) in full: Overview tab (rendered Markdown via `react-markdown`), Attack Graph tab (Mermaid render via the `mermaid` npm package), MITRE Technique card, Containment Playbook tab (syntax-highlighted via `shiki` or `prism-react-renderer`) with Download button and the role-gated **Approve for Ops** button — enforced both client-side (`RoleGate` component, UX only) and server-side (FastAPI + BFF reject non-Approver tokens on `POST /api/incidents/{id}/approve` — the real control).
- Build the **MITRE Navigator page** (§5.4): embed the official Navigator component, auto-load the generated `layer.json`.
- Build the **Ops Metrics page** (§5.5): Recharts panels fed by `/api/metrics` (throughput, alert volume trend, score distribution, LLM cost/latency).
- Build the **Playbook Library page** (§5.6) and the **Audit Trail** tab (hash-chain visualization).
- Write the Helm chart skeleton (`/infra/helm/`) mapping each Compose service to a Kubernetes Deployment/Service/ConfigMap, plus an HPA stub on the stream processor and scoring service — documented, not deployed.
- Harden the mock-login into real short-lived JWT issuance with role claims; document the production SSO/OIDC path.
- **Testing:** Playwright suite extended to cover the full incident lifecycle (open incident → view attack graph → view playbook → attempt approve as Analyst [blocked] → switch role to Approver → approve [succeeds]) run against the Preview URL. Vitest/RTL component tests for `RoleGate`, `SeverityBadge`, `AttackGraph`.

**End of Day 4 deliverable:** Full incident lifecycle demo-able end-to-end in the deployed React app, from raw log to a downloadable containment playbook, with real role-gated approval verified by both UI and direct API calls. Evaluation report exists with real numbers. Kubernetes path documented. All pages live on the Vercel Preview URL for stakeholder review.

---

### **DAY 5 — Hardening, Load Testing, Security Review, Production Deploy, Demo Rehearsal**

**Shared (all day, tightly paired):**
- **Load test:** replay logs at 5× then 20× real-time speed (`k6` or a custom async producer) and record end-to-end latency (log ingestion → incident appearing in the deployed UI) under load; document the bottleneck (almost certainly LLM call concurrency) and its mitigation (clustering already reduces call volume by an order of magnitude; async queue-based calling with backpressure is the next step).
- **Security self-review:** secrets not committed (verify `.env` + Vercel env vars only); input validation on all API endpoints (sanitize attacker-controlled log strings before they flow into generated Markdown/Mermaid artifacts — prevent injection via log content); rate limiting on public routes (verify the Vercel Edge Middleware limiter under load); dependency vulnerability scans (`pip-audit`, `npm audit`) wired into CI; confirm Vercel deployment protection (password/SSO on Preview URLs if the repo or data is sensitive).
- **Chaos/failure-mode pass:** kill the Redpanda broker mid-stream, simulate the LLM API timing out; confirm graceful degradation — alerts still land with a "triage pending" state rather than being silently dropped, and the connection-status pill on the frontend correctly reflects "reconnecting."
- **Frontend performance pass:** run Vercel's built-in Speed Insights / Lighthouse against the Production deployment; address any obvious bundle-size or largest-contentful-paint issues before the demo.
- **Promote to Production:** merge the final PR to `main`, confirm the Vercel **Production** deployment (custom domain if available) matches the last-reviewed Preview build exactly; tag the release in GitHub.
- **Documentation:** finalize `README.md` (architecture diagram, local setup, `docker compose up` one-liner for the backend, `vercel dev` for the frontend), `ARCHITECTURE.md`, `EVAL_RESULTS.md`, `SCALING_PATH.md` (Redpanda→Flink, Compose→K8s, single-node Postgres→managed, secrets→Vault, single-call→async batched LLM queue), `THREAT_MODEL.md`.
- **Demo dress rehearsal:** script a 10-minute live walkthrough on the **Production Vercel URL** — replay a multi-stage synthetic attack scenario (recon → brute force → lateral movement → attempted exfil), show correct clustering into one multi-technique incident with an accurate attack-graph timeline, MITRE Navigator heatmap update, generated containment playbook, and a role-gated approval action. Record a backup video capture in case of live-network issues during the actual presentation.

**End of Day 5 deliverable:** A stable, documented, load-tested, security-self-reviewed MVP live on a public Vercel Production URL, with a rehearsed demo script and a full written scaling/production path — ready to present to engineering leadership or a security team as a credible pilot proposal.

---

## 11. Repository Structure

```
soc-triager/
├── frontend/                    # React + Vite app — Vercel root
│   ├── src/
│   │   ├── pages/                # AlertQueue, IncidentDetail, Navigator, Ops, Playbooks, Settings
│   │   ├── components/           # SeverityBadge, TechniqueChip, AttackGraph, RoleGate, ...
│   │   ├── hooks/                 # useAlertsFeed (WebSocket), useAuth, useIncidents
│   │   ├── lib/                   # api client, ws client, auth utils
│   │   └── styles/
│   ├── api/                      # Vercel Serverless Functions (BFF proxy routes)
│   ├── middleware.ts             # Vercel Edge Middleware (JWT/RBAC gate, rate limit)
│   ├── tests/                    # Vitest + RTL unit/component tests
│   ├── e2e/                      # Playwright E2E specs (run against Preview URLs)
│   ├── vercel.json
│   └── vite.config.ts
├── backend/
│   ├── docker-compose.yml
│   ├── ingestion/                # replay producers, source normalizers
│   ├── stream/                   # faust_app.py
│   ├── ml/                       # features, training, models, MLflow artifacts
│   ├── mitre/                    # rules.yaml, mapping_engine.py
│   ├── llm/                      # triage_client.py, prompts/, schemas.py
│   ├── api/                      # FastAPI app, routers, ORM models, websocket.py
│   ├── artifacts/                # report_generator.py, attack_graph.py, playbook_templates/
│   └── tests/
├── infra/
│   └── helm/                     # K8s manifest skeletons
├── data/
│   ├── cicids2017/
│   ├── elastic_samples/
│   ├── synthetic_cloudtrail/
│   ├── synthetic_auth_log/
│   └── mitre/enterprise-attack-v15.1.json
├── docs/
│   ├── ARCHITECTURE.md
│   ├── EVAL_RESULTS.md
│   ├── SCALING_PATH.md
│   └── THREAT_MODEL.md
├── .github/workflows/ci.yml      # backend lint/test/build
└── README.md
```

---

## 12. Acceptance Criteria & Success Metrics

| Metric | Target | How measured |
|---|---|---|
| Anomaly detection recall | ≥ 0.90 on held-out CICIDS2017 attack windows | Confusion matrix vs. dataset ground truth |
| Anomaly detection precision | ≥ 0.75 | Same |
| MITRE technique mapping accuracy | ≥ 85% correct tactic-level classification on labeled synthetic scenarios | Manual spot-check rubric in `EVAL_RESULTS.md` |
| End-to-end latency (log → incident visible in the live Vercel UI) | < 5s at 1× real-time; documented p95 at 20× load | Load test harness + browser timing |
| LLM cost per 1,000 flagged anomalies | Documented, extrapolated to a stated enterprise volume | Token/cost logging, shown on `/ops` |
| System resilience | Zero silent event loss on broker/LLM outage; graceful degraded state visible in UI | Chaos test pass |
| Auditability | Every incident traceable via hash-chained ledger, visualized in the Audit Trail tab | Manual ledger verification test |
| RBAC enforcement | "Approve for Ops" unreachable/disabled for non-Approver both in UI and via direct API call | Security test case + Playwright test |
| Deployment | Production Vercel URL live, matches last-reviewed Preview build, Lighthouse performance score reviewed | Manual verification + Speed Insights |
| Test coverage | Backend unit tests (pytest) + frontend unit/component tests (Vitest/RTL) passing in CI; ≥ 1 E2E Playwright suite covering the full incident lifecycle, run against a live Preview URL | CI status checks required to merge |

---

## 13. Explicit Non-Goals for This Sprint (state these in the demo — it builds credibility)

- **No auto-execution of containment actions** — every playbook is a reviewed, downloadable artifact requiring human approval; a deliberate safety boundary, not a missing feature.
- **No production secrets management (Vault)** — Vercel env vars + `.env` cover the sprint; Vault documented as the immediate next step.
- **No multi-tenant isolation** — single-org assumption for the MVP; documented Phase 2 item.
- **No live cloud API integration** — synthetic CloudTrail-format data used; ingestion is architected so a real `boto3` CloudTrail/S3 poller is a bounded follow-on task.
- **No Flink/Kubernetes deployment executed** — both architected and manifest/skeleton-ready, to show the scale path without spending sprint time on cluster ops.
- **Backend not deployed on Vercel** — deliberate: Vercel hosts the frontend + BFF only; the stateful streaming/ML backend runs on a Docker-capable host, documented in `SCALING_PATH.md`.

---

## 14. Post-Sprint Roadmap (Phase 2 preview)

Phase 2 would prioritize, in order: (1) real cloud-native log source integrations (CloudTrail via EventBridge, Azure Activity Log, GCP Audit Log) rather than synthetic data; (2) migrating the stream processor to Flink for sustained high-throughput deployments; (3) a feedback loop where analyst approve/reject/reclassify actions retrain the Isolation Forest/autoencoder thresholds and refine the MITRE heuristic rule table (active learning loop); (4) SOAR-style playbook auto-execution behind a formal change-approval workflow with full rollback support, once the human-in-the-loop track record justifies it; (5) SSO/OIDC, Vault-backed secrets, multi-tenant data isolation, and moving the BFF to a dedicated API gateway if Vercel's serverless limits are outgrown at real enterprise traffic.

---

*End of plan. Intended to be checked into the repository as `PLAN.md` and referenced directly during the Day 1 kickoff sync.*
