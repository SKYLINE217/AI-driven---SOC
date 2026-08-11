# SOC Triager — System Architecture

> **Audience:** Both engineers; serves as the canonical reference for how all components fit together.
> **This document supersedes any informal diagrams.** Changes must be made here first, then reflected in code.

---

## 1. Guiding Principles

| Principle | Architectural Expression |
|---|---|
| Streaming-first | Redpanda/Kafka-API bus; Faust consumer; no CSV-batch processing in the hot path |
| Explainability | Every anomaly score carries top-3 contributing features; every MITRE mapping carries LLM rationale |
| Human-in-the-loop | Containment playbooks are drafts only; no automated execution path exists |
| Auditability | Append-only, hash-chained `incident_ledger`; every state change recorded |
| Continuous deployment | Vercel auto-deploys on every commit; the system is always demo-able |
| Defense in depth | Auth enforced at BFF and FastAPI independently; secrets in env vars, never in code |
| Graceful degradation | LLM timeout → `triage_pending`; broker outage → no silent event loss |

---

## 2. Tier Decomposition

The architecture is intentionally split into two tiers because Vercel's serverless edge runtime cannot host long-running stateful processes (Faust workers, ML model servers, Postgres connections).

```
┌────────────────────────────────────────────────────────────────────┐
│  FRONTEND TIER  (Vercel — global CDN, auto-preview, zero-config)  │
│                                                                    │
│  ┌──────────────────┐     ┌──────────────────────────────────┐    │
│  │  React SPA       │────▶│  Vercel BFF                      │    │
│  │  (Vite build,    │     │  Serverless + Edge Functions      │    │
│  │   static assets  │     │  - JWT issue + validation         │    │
│  │   on global CDN) │     │  - Role enforcement               │    │
│  │                  │◀────│  - Rate limiting                  │    │
│  │  WebSocket client│     │  - Response caching               │    │
│  └──────────────────┘     │  - Backend URL injection          │    │
│                           └─────────────────┬────────────────┘    │
└─────────────────────────────────────────────│────────────────────-┘
                                              │ HTTPS REST + WebSocket
┌─────────────────────────────────────────────│────────────────────-┐
│  BACKEND TIER  (Docker Compose on Railway / Fly.io / EC2-class VM)│
│                                             ▼                     │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │  FastAPI Incident + Alert API  (port 8000, TLS via Caddy)│     │
│  │  FastAPI ML Scoring API        (port 8001, internal)     │     │
│  └──────────────────────┬─────────────────────────────────--┘     │
│           ┌─────────────┼─────────────┬──────────────┐            │
│           ▼             ▼             ▼              ▼            │
│       Postgres       Redis        Redpanda       MLflow           │
│    (TimescaleDB)  (hot cache,   (Kafka-API)    (experiment        │
│                    WS fan-out)   streaming bus   tracking)        │
│           ▲             ▲                                         │
│           └─────────────┘                                         │
│                    ▲                                              │
│           ┌────────┴──────────────────────────────────────┐      │
│           │  Faust Stream Processor                        │      │
│           │  (normalize → enrich → feature compute →      │      │
│           │   score → alert → incident)                    │      │
│           └────────────────────────────────────────────────┘      │
│                    ▲                                              │
│           ┌────────┴──────────────────────────────────────┐      │
│           │  Log Replay Producer / Fluent Bit              │      │
│           │  (synthetic CICIDS2017, CloudTrail, auth.log)  │      │
│           └────────────────────────────────────────────────┘      │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │  Prometheus + Grafana (internal observability)           │     │
│  └──────────────────────────────────────────────────────────┘     │
└───────────────────────────────────────────────────────────────────┘
```

---

## 3. Component-Level Architecture

### 3.1 Log Ingestion Layer

**Components:** Replay Producer, Fluent Bit (optional for sprint)

The replay producer (`backend/ingestion/replay_producer.py`) reads source files and publishes to Redpanda at controllable speed:

```
CICIDS2017 CSV files  ─────────────────────────────────▶ raw.cicids
Synthetic CloudTrail JSON  ─────────────────────────────▶ raw.cloudtrail
Synthetic auth.log  ────────────────────────────────────▶ raw.auth
Syslog samples  ────────────────────────────────────────▶ raw.syslog
```

**Fluent Bit** (documented as the production replacement for the replay producer): configured with Kafka output plugin, deployed as a DaemonSet in Kubernetes (Phase 2). During the sprint, the Python producer is pragmatically sufficient.

### 3.2 Streaming Bus — Redpanda

Kafka-API compatible, single-binary, no ZooKeeper dependency. Consumer groups allow horizontal scaling of the Faust worker fleet:

```
raw.syslog ──────┐
raw.cloudtrail ──┤──▶ [faust-normalizer-cg] ──▶ normalized.events
raw.auth ────────┤
raw.cicids ──────┘

normalized.events ──▶ [faust-feature-cg] ──▶ (Redis hot store + TimescaleDB cold store)
                                          ──▶ [scoring call] ──▶ alerts.raw (if anomaly)

alerts.raw ──▶ [alert-consumer-cg] ──▶ [incident correlation] ──▶ Postgres incidents table
                                                                 ──▶ incidents.updates topic

incidents.updates ──▶ [ws-fan-out-cg] ──▶ Redis Pub/Sub ──▶ WebSocket connections
```

### 3.3 Stream Processing — Faust

Faust is a Python stream processing library (Kafka Streams-inspired). Each `@app.agent` is a coroutine that processes events from one or more topics:

**Agent: `normalize_and_enrich`**
- Consumes: `raw.*` (all source topics, union)
- Produces: `normalized.events`
- Operations: format-specific parsing → ECS normalization → GeoIP/ASN enrichment

**Agent: `compute_features`**
- Consumes: `normalized.events`
- Produces: nothing (writes to Redis and TimescaleDB directly)
- Operations: sliding window aggregation, feature vector construction

**Agent: `score_and_alert`**
- Consumes: `normalized.events` (after feature write completes)
- Produces: `alerts.raw` (conditionally)
- Operations: calls Scoring API → if `score > threshold`, builds alert and publishes

**Agent: `correlate_incidents`**
- Consumes: `alerts.raw`
- Produces: `incidents.updates`
- Operations: cluster matching → incident create/update → LLM triage → MITRE mapping → artifact generation → ledger write

### 3.4 Feature Store

**Redis (hot):** sliding window aggregates per `(host, user, source_ip)` entity tuple. Sub-millisecond read for the scoring path. TTL-managed; no persistence required (can be rebuilt from TimescaleDB).

**TimescaleDB (cold):** `feature_snapshots` hypertable. Used for:
- Autoencoder training (historical baseline)
- Analyst queries (SQL-accessible)
- Time-of-day z-score baseline computation
- Geo-velocity calculation (compare current event location to previous event location for same user)

### 3.5 ML Engine

Two models run in the Scoring API service:

```
FeatureVector (19 features)
    │
    ├──▶ IsolationForest ──▶ IF score (0–1)
    │    n_estimators=200
    │    contamination='auto'
    │
    └──▶ Autoencoder ──▶ Reconstruction error ──▶ AE score (0–1)
         3-layer symmetric
         bottleneck (8 units)
         │
         └── Both loaded from MLflow model registry
                          │
                          ▼
              Weighted ensemble: 0.6×IF + 0.4×AE
                          │
                          ▼
                 Score → is_anomaly → top_features
```

### 3.6 LLM Triage Pipeline

```
Anomaly alert(s)
    │
    ├──▶ Clustering: same (source_ip, technique_category, 5-min window)
    │                → one LLM call per cluster
    │
    ├──▶ Heuristic rule table → candidate MITRE technique IDs (1–5)
    │
    └──▶ Claude Sonnet (structured output / tool use)
              Input: structured event summary + candidates + anomaly score
              Output: { technique_id, confidence, rationale, severity, recommended_action }
              Validated by Pydantic schema
              Max 2 retries on schema failure → else triage_pending
```

### 3.7 Incident Management

```
New alert arrives in alerts.raw
    │
    ├──▶ Query: does an open incident exist with matching (entity, technique, <5 min old)?
    │
    ├── YES: append alert to existing incident → update incident timestamp, alert_count
    │
    └── NO: create new incident
              → auto-generate title
              → assign to alert queue (status: new)
              → trigger artifact generation
              → write INCIDENT_CREATED to incident_ledger
```

### 3.8 Artifact Generation

Async worker (Celery or `asyncio.create_task`) triggered on incident creation and on significant status updates:

1. **Markdown report** — Jinja2 template → rendered Markdown → stored in `incidents.report_md`
2. **Mermaid graph** — Python graph builder → Mermaid syntax string → stored in `incidents.graph_mmd`
3. **Containment playbook** — technique-category selector → Jinja2 Ansible template → sanitized variable substitution → stored in `incidents.playbook_draft`

All three are pre-generated and stored in Postgres; the API serves them on demand without runtime generation (latency benefit).

### 3.9 API Gateway — FastAPI

Two FastAPI applications:

**`backend/api/incident_app.py`** (port 8000, external):
- REST routes for alerts, incidents, MITRE, metrics, artifacts
- WebSocket route (`/ws/alerts`) for live push
- JWT validation middleware on all routes
- Prometheus metrics instrumentation
- Structured JSON logging (structlog)

**`backend/ml/scoring_app.py`** (port 8001, internal only):
- `POST /score` — accepts feature vector, returns anomaly score
- Not exposed externally; called only by the Faust worker
- Model loading from MLflow on startup; version pinned in config

### 3.10 WebSocket Fan-Out

```
FastAPI /ws/alerts handler
    │ subscribes to
    ▼
Redis Pub/Sub channel: ws:alerts:broadcast
    ▲ publishes to
    │
Faust agent (on new alert created)
    or
Incident API (on status update)
```

This pattern decouples the WebSocket connection management (FastAPI, potentially multiple instances) from the event source (Faust worker). Any backend service can publish to the Redis channel; all connected WebSocket clients receive the message.

### 3.11 BFF — Vercel Functions

```
/api/auth/login       ─── Edge Function (JWT issuance)
/api/alerts           ─── Serverless Function (proxy + cache 10s)
/api/incidents/*      ─── Serverless Function (proxy, role gate)
/api/mitre/*          ─── Serverless Function (proxy + cache 60s)
/api/navigator/*      ─── Serverless Function (proxy + cache 60s)
/api/metrics          ─── Serverless Function (proxy + transform)
/api/ws/alerts        ─── Edge Function (WebSocket proxy)
middleware.ts         ─── Edge Middleware (JWT validate + rate limit, runs on all /api/* routes)
```

The backend's base URL is stored in `BACKEND_API_URL` Vercel environment variable — different values for Preview (staging backend) and Production (prod backend).

---

## 4. Data Flow — End to End

The following traces a single SSH brute-force event from raw log to UI:

```
t=0ms    Replay producer reads auth.log line: "Failed password for root from 203.0.113.44..."
t=1ms    Published to Redpanda topic raw.auth (partition by source IP)

t=5ms    Faust normalize_and_enrich agent reads from raw.auth
t=6ms    auth_log_normalizer parses the line into ECS NormalizedEvent
t=7ms    GeoIP enricher adds source.geo.country_iso_code: "RU"
t=8ms    Published to normalized.events

t=10ms   Faust compute_features agent reads normalized event
t=11ms   Redis: ZADD event to event_count_1m sorted set
t=12ms   Redis: HINCRBY failed_auth_count for entity key
t=13ms   Faust score_and_alert agent reads same event

t=14ms   score_and_alert reads feature vector from Redis
t=17ms   HTTP POST to Scoring API (localhost:8001/score)
t=20ms   IsolationForest scores: 0.91; Autoencoder scores: 0.79
t=20ms   Ensemble: 0.87 > threshold (0.72) → is_anomaly: true
t=21ms   Alert published to alerts.raw

t=22ms   Faust correlate_incidents agent reads from alerts.raw
t=23ms   No existing open incident for this (entity, technique_category, window) → create new

t=25ms   Heuristic rule table: event_count_1m > 10 AND event.action = ssh_login_failed → candidates [T1110, T1110.001]

t=30ms   Claude Sonnet API call (structured output)
         Input: { source_ip: "203.0.113.44", target_host: "prod-db-03", event_count: 17, candidates: [...] }

t=1800ms Claude response: { technique_id: "T1110.001", confidence: 0.87, rationale: "...", severity: "high" }

t=1801ms Incident record created in Postgres
t=1802ms Artifact generation tasks queued (asyncio)
t=1803ms INCIDENT_CREATED written to incident_ledger with hash chain
t=1804ms New alert payload published to Redis Pub/Sub ws:alerts:broadcast

t=1805ms FastAPI WebSocket handler receives Pub/Sub message
t=1806ms All connected WebSocket clients receive { type: "new_alert", alert: {...} }

t=1810ms React useAlertsFeed hook receives WebSocket message
t=1812ms Zustand alertStore updated
t=1815ms AlertTable re-renders; new row prepended with yellow highlight animation

Total: ~1.8 s (dominated by LLM API call latency)
```

Target: < 5 s end-to-end at 1× real-time. Verified on Day 5 load test.

---

## 5. Database Schema

### 5.1 TimescaleDB Hypertables

```sql
-- Raw event store (hypertable on @timestamp, 1-day chunks)
CREATE TABLE raw_events (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    source_type TEXT NOT NULL,
    raw_payload JSONB NOT NULL
);
SELECT create_hypertable('raw_events', 'timestamp');

-- Normalized ECS events (hypertable, 1-day chunks)
CREATE TABLE normalized_events (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    source_type TEXT NOT NULL,
    ecs_event JSONB NOT NULL,
    source_ip INET,
    destination_host TEXT,
    event_action TEXT,
    user_name TEXT
);
SELECT create_hypertable('normalized_events', 'timestamp');
CREATE INDEX ON normalized_events (source_ip, timestamp DESC);
CREATE INDEX ON normalized_events (destination_host, timestamp DESC);

-- Feature snapshots (hypertable, 1-week chunks)
CREATE TABLE feature_snapshots (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    window_end TIMESTAMPTZ NOT NULL,
    entity_key TEXT NOT NULL,
    features JSONB NOT NULL
);
SELECT create_hypertable('feature_snapshots', 'window_end');
```

### 5.2 Incident Store (Regular Postgres Tables)

```sql
CREATE TABLE entities (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('host', 'user', 'ip')),
    value TEXT NOT NULL,
    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(type, value)
);

CREATE TABLE alerts (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    incident_id UUID REFERENCES incidents(id),
    severity TEXT NOT NULL CHECK (severity IN ('critical','high','medium','low','info')),
    timestamp TIMESTAMPTZ NOT NULL,
    source_ip INET,
    destination_host TEXT,
    user_name TEXT,
    technique_id TEXT NOT NULL,
    tactic TEXT NOT NULL,
    anomaly_score NUMERIC(4,3) NOT NULL,
    score_history NUMERIC(4,3)[] DEFAULT '{}',
    top_features JSONB,
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new','ack','escalated','closed')),
    assignee TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE incidents (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    title TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    technique_id TEXT NOT NULL,
    technique_name TEXT NOT NULL,
    tactic TEXT NOT NULL,
    confidence NUMERIC(4,3),
    llm_rationale TEXT,
    recommended_action TEXT,
    report_md TEXT,
    graph_mmd TEXT,
    playbook_draft TEXT,
    playbook_approved BOOLEAN DEFAULT FALSE,
    playbook_approved_by TEXT,
    playbook_approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE incident_ledger (
    seq BIGSERIAL PRIMARY KEY,
    incident_id UUID NOT NULL REFERENCES incidents(id),
    hash TEXT NOT NULL UNIQUE,          -- SHA-256 of (prev_hash + payload)
    prev_hash TEXT NOT NULL,            -- "0"*64 for the first entry
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    action TEXT NOT NULL,               -- INCIDENT_CREATED, STATUS_ESCALATED, PLAYBOOK_APPROVED, etc.
    actor TEXT NOT NULL,                -- user identity or "system"
    payload JSONB NOT NULL
);
-- No UPDATE or DELETE on this table — enforced via row security policy
ALTER TABLE incident_ledger ENABLE ROW LEVEL SECURITY;
CREATE POLICY ledger_insert_only ON incident_ledger FOR INSERT WITH CHECK (true);
-- (No SELECT policy restriction — any authenticated service can read)

CREATE TABLE users (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK (role IN ('analyst','senior_analyst','approver')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE llm_call_log (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    called_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    model TEXT NOT NULL,
    input_tokens INT NOT NULL,
    output_tokens INT NOT NULL,
    latency_ms INT NOT NULL,
    cluster_size INT NOT NULL,
    technique_result TEXT,
    cost_usd NUMERIC(10,6)
);

CREATE TABLE containment_templates (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL,
    technique_category TEXT NOT NULL,
    template_source TEXT NOT NULL,       -- Jinja2 template content
    ioc_variables TEXT[] NOT NULL,       -- list of required Jinja2 vars
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 6. Repository Layout

```
soc-triager/
├── frontend/                         # Vercel root directory
│   ├── src/
│   │   ├── pages/
│   │   │   ├── AlertQueue.tsx
│   │   │   ├── IncidentDetail.tsx
│   │   │   ├── Navigator.tsx
│   │   │   ├── OpsMetrics.tsx
│   │   │   ├── PlaybookLibrary.tsx
│   │   │   └── Settings.tsx
│   │   ├── components/
│   │   │   ├── SeverityBadge.tsx
│   │   │   ├── TechniqueChip.tsx
│   │   │   ├── LiveConnectionPill.tsx
│   │   │   ├── AttackGraph.tsx
│   │   │   ├── MarkdownReport.tsx
│   │   │   ├── LedgerEntry.tsx
│   │   │   ├── RoleGate.tsx
│   │   │   ├── MetricCard.tsx
│   │   │   ├── AlertTable.tsx
│   │   │   └── SparklineScore.tsx
│   │   ├── hooks/
│   │   │   ├── useAlertsFeed.ts
│   │   │   ├── useAuth.ts
│   │   │   ├── useIncidents.ts
│   │   │   ├── useIncidentDetail.ts
│   │   │   ├── useMitreLayer.ts
│   │   │   └── useMetrics.ts
│   │   ├── stores/
│   │   │   ├── alertStore.ts
│   │   │   ├── authStore.ts
│   │   │   └── uiStore.ts
│   │   ├── lib/
│   │   │   ├── apiClient.ts
│   │   │   ├── wsClient.ts
│   │   │   └── authUtils.ts
│   │   └── styles/
│   ├── api/                          # Vercel Serverless Functions (BFF)
│   │   ├── auth/login.ts
│   │   ├── alerts/index.ts
│   │   ├── alerts/bulk-ack.ts
│   │   ├── incidents/[id]/index.ts
│   │   ├── incidents/[id]/status.ts
│   │   ├── incidents/[id]/approve.ts
│   │   ├── incidents/[id]/playbook.ts
│   │   ├── mitre/technique/[id].ts
│   │   ├── navigator/layer.ts
│   │   └── metrics/index.ts
│   ├── middleware.ts                  # Vercel Edge Middleware (JWT + rate limit)
│   ├── tests/                        # Vitest + React Testing Library
│   ├── e2e/                          # Playwright specs
│   │   ├── alert-queue.spec.ts
│   │   ├── incident-lifecycle.spec.ts
│   │   └── rbac.spec.ts
│   ├── vercel.json
│   └── vite.config.ts
│
├── backend/
│   ├── docker-compose.yml
│   ├── ingestion/
│   │   ├── replay_producer.py
│   │   └── normalizers/
│   │       ├── syslog_normalizer.py
│   │       ├── cloudtrail_normalizer.py
│   │       ├── auth_log_normalizer.py
│   │       └── cicids_normalizer.py
│   ├── stream/
│   │   └── faust_app.py
│   ├── ml/
│   │   ├── feature_engineering.py
│   │   ├── isolation_forest.py
│   │   ├── autoencoder.py
│   │   ├── ensemble.py
│   │   ├── train.py
│   │   ├── scoring_app.py
│   │   └── THRESHOLD_DECISION.md
│   ├── mitre/
│   │   ├── rules.yaml
│   │   └── mapping_engine.py
│   ├── llm/
│   │   ├── triage_client.py
│   │   ├── prompts/
│   │   │   └── system_prompt.txt
│   │   └── schemas.py
│   ├── api/
│   │   ├── main.py
│   │   ├── routers/
│   │   │   ├── alerts.py
│   │   │   ├── incidents.py
│   │   │   ├── mitre.py
│   │   │   └── metrics.py
│   │   ├── models.py                 # SQLAlchemy ORM models
│   │   ├── schemas.py                # Pydantic request/response schemas
│   │   ├── auth.py                   # JWT validation dependency
│   │   └── websocket.py
│   ├── artifacts/
│   │   ├── report_generator.py
│   │   ├── attack_graph.py
│   │   ├── playbook_renderer.py
│   │   └── playbook_templates/
│   │       ├── brute_force.ansible.j2
│   │       ├── lateral_movement.ansible.j2
│   │       ├── ddos.ansible.j2
│   │       ├── priv_esc.ansible.j2
│   │       └── exfil.ansible.j2
│   └── tests/
│       ├── test_normalizers.py
│       ├── test_scoring.py
│       ├── test_llm_client.py
│       ├── test_mitre_mapping.py
│       ├── test_incidents.py
│       ├── test_rbac.py
│       └── test_ledger.py
│
├── infra/
│   └── helm/                         # K8s manifest skeletons (not deployed in sprint)
│       ├── faust-worker/
│       ├── scoring-api/
│       ├── incident-api/
│       └── artifact-worker/
│
├── data/
│   ├── cicids2017/
│   ├── elastic_samples/
│   ├── synthetic_cloudtrail/
│   ├── synthetic_auth_log/
│   └── mitre/enterprise-attack-v15.1.json
│
├── docs/
│   ├── ARCHITECTURE.md               ← this file
│   ├── EVAL_RESULTS.md
│   ├── SCALING_PATH.md
│   └── THREAT_MODEL.md
│
├── .github/workflows/ci.yml
└── README.md
```

---

## 7. Scaling Path (Post-Sprint)

| Bottleneck | Sprint Solution | Production Solution |
|---|---|---|
| Stream processing throughput | Faust (Python, single worker) | Apache Flink (stateful, distributed, exactly-once) |
| ML scoring latency | Sync HTTP call from Faust | Async queue + model server pool (TorchServe / Triton) |
| LLM call volume | Alert clustering (10× reduction) | Async LLM queue with priority lanes; Claude Batch API for non-urgent triage |
| Postgres write throughput | Single TimescaleDB node | TimescaleDB Multinode or Citus (horizontal sharding) |
| WebSocket connections | Single FastAPI process | Socket.io cluster with Redis adapter, or Pusher/Ably |
| Container orchestration | Docker Compose on single VM | Kubernetes (Helm charts in `/infra/helm/`, HPAs on Faust worker and Scoring API) |
| Secrets | .env files + Vercel env vars | HashiCorp Vault with dynamic database credentials |
| Log sources | Python replay producer | Fluent Bit DaemonSet + CloudTrail EventBridge + Azure Activity Log integration |
