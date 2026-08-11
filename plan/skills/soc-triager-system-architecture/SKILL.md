---
name: soc-triager-system-architecture
description: Use this skill whenever the user asks how the SOC Triager system fits together end-to-end — component diagrams, the two-tier (Vercel frontend/BFF + VM backend) split, data flow from raw log to UI, database schema (TimescaleDB hypertables + Postgres tables), the Faust agent pipeline, or the repository layout. This is the canonical architecture reference — trigger it for any "how does X talk to Y" or "where does this data live" question about SOC Triager, and treat it as authoritative over any informal diagram the user describes; if there's a conflict, this document wins and the code should be changed to match it, not the other way around.
---

# SOC Triager — System Architecture (Canonical Reference)

> This document supersedes any informal diagrams. If the user's mental model of the architecture conflicts with what's below, flag the conflict — this is the source of truth.

## Guiding principles → architectural expression

| Principle | How it shows up in the architecture |
|---|---|
| Streaming-first | Redpanda/Kafka-API bus; Faust consumer; no CSV-batch processing in the hot path |
| Explainability | Every anomaly score carries top-3 contributing features; every MITRE mapping carries LLM rationale |
| Human-in-the-loop | Containment playbooks are drafts only; no automated execution path exists anywhere |
| Auditability | Append-only, hash-chained `incident_ledger`; every state change recorded |
| Continuous deployment | Vercel auto-deploys on every commit; the system is always demo-able |
| Defense in depth | Auth enforced at BFF and FastAPI independently; secrets in env vars, never in code |
| Graceful degradation | LLM timeout → `triage_pending`; broker outage → no silent event loss |

## Tier decomposition

Split into two tiers because Vercel's serverless/edge runtime cannot host long-running stateful processes (Faust workers, ML model servers, persistent Postgres connections).

```
FRONTEND TIER (Vercel)                         BACKEND TIER (Docker Compose on a VM)
React SPA ──▶ Vercel BFF (Serverless/Edge)      FastAPI Incident+Alert API (8000, TLS via Caddy)
  WebSocket client ◀──  - JWT issue+validate     FastAPI ML Scoring API (8001, internal only)
                        - Role enforcement            │
                        - Rate limiting        ┌──────┼───────┬────────┐
                        - Response caching     Postgres  Redis  Redpanda  MLflow
                        - Backend URL inject   (Timescale) (hot cache,  (Kafka-  (experiment
                             │                             WS fan-out)   API)     tracking)
                             │ HTTPS REST + WebSocket           ▲
                             └─────────────────────────────────┤
                                                        Faust Stream Processor
                                                        (normalize → enrich → feature
                                                         compute → score → alert → incident)
                                                                 ▲
                                                        Log Replay Producer / Fluent Bit
                                                        (synthetic CICIDS2017, CloudTrail, auth.log)

                                                        Prometheus + Grafana (internal observability)
```

## Component-level architecture

### Log ingestion
`backend/ingestion/replay_producer.py` reads source files and publishes to Redpanda at controllable speed. Sources: CICIDS2017 CSVs → `raw.cicids`; synthetic CloudTrail JSON → `raw.cloudtrail`; synthetic auth.log → `raw.auth`; syslog samples → `raw.syslog`. Fluent Bit is documented as the production replacement (Kubernetes DaemonSet, Phase 2) — the Python producer is sufficient for the sprint.

### Streaming bus — Redpanda
Kafka-API compatible, single binary, no ZooKeeper. Flow:
```
raw.syslog, raw.cloudtrail, raw.auth, raw.cicids
  ──▶ [faust-normalizer-cg] ──▶ normalized.events
normalized.events ──▶ [faust-feature-cg] ──▶ Redis hot store + TimescaleDB cold store
                                          ──▶ [scoring call] ──▶ alerts.raw (if anomaly)
alerts.raw ──▶ [alert-consumer-cg] ──▶ incident correlation ──▶ Postgres incidents table
                                                              ──▶ incidents.updates topic
incidents.updates ──▶ [ws-fan-out-cg] ──▶ Redis Pub/Sub ──▶ WebSocket connections
```

### Stream processing — Faust agents
- **`normalize_and_enrich`** — consumes `raw.*` (union of all source topics), produces `normalized.events`. Format-specific parsing → ECS normalization → GeoIP/ASN enrichment.
- **`compute_features`** — consumes `normalized.events`, writes directly to Redis + TimescaleDB (no topic output). Sliding-window aggregation, feature vector construction.
- **`score_and_alert`** — consumes `normalized.events` (after feature write completes), produces `alerts.raw` conditionally. Calls Scoring API → if `score > threshold`, builds and publishes an alert.
- **`correlate_incidents`** — consumes `alerts.raw`, produces `incidents.updates`. Cluster matching → incident create/update → LLM triage → MITRE mapping → artifact generation → ledger write.

### Feature store
- **Redis (hot):** sliding-window aggregates per `(host, user, source_ip)` entity tuple. Sub-millisecond reads on the scoring path. TTL-managed, no persistence required (rebuildable from TimescaleDB).
- **TimescaleDB (cold):** `feature_snapshots` hypertable. Used for autoencoder training baseline, analyst SQL queries, time-of-day z-score baseline, geo-velocity calculation.

### ML engine
```
FeatureVector (19 features)
  ├─▶ IsolationForest (n_estimators=200, contamination='auto') ─▶ IF score (0–1)
  └─▶ Autoencoder (3-layer symmetric bottleneck, 8 units) ─▶ reconstruction error ─▶ AE score (0–1)
       Both loaded from MLflow model registry
                    ▼
       Weighted ensemble: 0.6×IF + 0.4×AE ─▶ Score → is_anomaly → top_features
```

### LLM triage pipeline
```
Anomaly alert(s)
  ├─▶ Clustering: same (source_ip, technique_category, 5-min window) → one LLM call per cluster
  ├─▶ Heuristic rule table → candidate MITRE technique IDs (1–5)
  └─▶ Claude Sonnet (structured output)
        Input: structured event summary + candidates + anomaly score
        Output: { technique_id, confidence, rationale, severity, recommended_action }
        Validated by Pydantic schema; max 2 retries on schema failure → else triage_pending
```

### Incident management
New alert in `alerts.raw` → query for an open incident with matching `(entity, technique, <5 min old)`. If found, append. If not, create new incident: auto-generate title, set status `new`, trigger artifact generation, write `INCIDENT_CREATED` to `incident_ledger`.

### Artifact generation
Async worker (Celery or `asyncio.create_task`), triggered on incident creation and significant status updates. Produces and stores in Postgres (never generated at request time — latency benefit):
1. Markdown report → `incidents.report_md`
2. Mermaid attack graph → `incidents.graph_mmd`
3. Containment playbook (Ansible) → `incidents.playbook_draft`

### API gateway — FastAPI
- **`backend/api/incident_app.py`** (port 8000, external): REST for alerts/incidents/MITRE/metrics/artifacts, WebSocket `/ws/alerts`, JWT validation middleware, Prometheus instrumentation, structured JSON logging (`structlog`).
- **`backend/ml/scoring_app.py`** (port 8001, internal only): `POST /score`. Never exposed externally — called only by the Faust worker. Loads models from MLflow on startup, version pinned in config.

### WebSocket fan-out
`FastAPI /ws/alerts` subscribes to Redis Pub/Sub channel `ws:alerts:broadcast`. Faust (on new alert) or the Incident API (on status update) publishes to that channel. This decouples WebSocket connection management (potentially multiple FastAPI instances) from the event source.

### BFF — Vercel Functions
```
/api/auth/login       Edge Function (JWT issuance)
/api/alerts           Serverless Function (proxy + cache 10s)
/api/incidents/*      Serverless Function (proxy, role gate)
/api/mitre/*          Serverless Function (proxy + cache 60s)
/api/navigator/*      Serverless Function (proxy + cache 60s)
/api/metrics          Serverless Function (proxy + transform)
/api/ws/alerts        Edge Function (WebSocket proxy)
middleware.ts         Edge Middleware (JWT validate + rate limit, runs on all /api/* routes)
```
Backend base URL is read from the `BACKEND_API_URL` Vercel environment variable — different values for Preview (staging backend) vs Production.

## Data flow — end to end (SSH brute-force example)

```
t=0ms    Replay producer reads auth.log line → published to raw.auth
t=5-8ms  Faust normalize_and_enrich: parse → ECS → GeoIP enrich → normalized.events
t=10-13ms Faust compute_features: Redis ZADD/HINCRBY updates
t=14-21ms score_and_alert: read features from Redis → POST to Scoring API (8001)
          IsolationForest 0.91, Autoencoder 0.79 → ensemble 0.87 > threshold 0.72 → alert published
t=22-30ms correlate_incidents: no existing open incident → create new
          heuristic rules → candidates [T1110, T1110.001]
t=30ms   Claude Sonnet API call (structured output)
t=1800ms Claude responds: technique_id T1110.001, confidence 0.87, severity high
t=1801-1804ms Incident created in Postgres; artifact generation queued; ledger entry written;
          new alert published to Redis Pub/Sub ws:alerts:broadcast
t=1805-1815ms FastAPI WS handler → all connected clients → React useAlertsFeed → Zustand
          store → AlertTable re-renders with yellow-highlight animation

Total: ~1.8 s, dominated by the LLM API call. Target: < 5 s end-to-end at 1× real-time.
```

## Database schema

**TimescaleDB hypertables** (time-partitioned):
- `raw_events(id, timestamp, source_type, raw_payload JSONB)` — hypertable on `timestamp`, 1-day chunks
- `normalized_events(id, timestamp, source_type, ecs_event JSONB, source_ip INET, destination_host, event_action, user_name)` — hypertable, indexed on `(source_ip, timestamp DESC)` and `(destination_host, timestamp DESC)`
- `feature_snapshots(id, window_end, entity_key, features JSONB)` — hypertable on `window_end`, 1-week chunks

**Regular Postgres tables:**
- `entities(id, type CHECK IN ('host','user','ip'), value, first_seen, last_seen, UNIQUE(type,value))`
- `alerts(id, incident_id FK, severity CHECK, timestamp, source_ip, destination_host, user_name, technique_id, tactic, anomaly_score NUMERIC(4,3), score_history NUMERIC(4,3)[], top_features JSONB, status CHECK IN ('new','ack','escalated','closed'), assignee, created_at)`
- `incidents(id, title, severity, status, technique_id, technique_name, tactic, confidence, llm_rationale, recommended_action, report_md, graph_mmd, playbook_draft, playbook_approved BOOLEAN, playbook_approved_by, playbook_approved_at, created_at, updated_at)`
- `incident_ledger(seq BIGSERIAL, incident_id FK, hash UNIQUE, prev_hash, timestamp, action, actor, payload JSONB)` — **append-only**, row-level security policy `FOR INSERT` only, no `UPDATE`/`DELETE` permitted
- `users(id, email UNIQUE, role CHECK IN ('analyst','senior_analyst','approver'), created_at)`
- `llm_call_log(id, called_at, model, input_tokens, output_tokens, latency_ms, cluster_size, technique_result, cost_usd NUMERIC(10,6))`
- `containment_templates(id, name, technique_category, template_source, ioc_variables TEXT[], created_at)`

## Repository layout (full tree)

```
soc-triager/
├── frontend/  (Vercel root)
│   ├── src/{pages,components,hooks,stores,lib,styles}/
│   ├── api/                # BFF: auth/login.ts, alerts/*, incidents/[id]/*, mitre/*, navigator/*, metrics/*
│   ├── middleware.ts
│   ├── tests/  e2e/{alert-queue,incident-lifecycle,rbac}.spec.ts
│   ├── vercel.json  vite.config.ts
├── backend/
│   ├── docker-compose.yml
│   ├── ingestion/{replay_producer.py, normalizers/{syslog,cloudtrail,auth_log,cicids}_normalizer.py}
│   ├── stream/faust_app.py
│   ├── ml/{feature_engineering,isolation_forest,autoencoder,ensemble,train,scoring_app}.py, THRESHOLD_DECISION.md
│   ├── mitre/{rules.yaml, mapping_engine.py}
│   ├── llm/{triage_client.py, prompts/system_prompt.txt, schemas.py}
│   ├── api/{main.py, routers/{alerts,incidents,mitre,metrics}.py, models.py, schemas.py, auth.py, websocket.py}
│   ├── artifacts/{report_generator,attack_graph,playbook_renderer}.py, playbook_templates/*.ansible.j2
│   └── tests/{test_normalizers,test_scoring,test_llm_client,test_mitre_mapping,test_incidents,test_rbac,test_ledger}.py
├── infra/helm/{faust-worker,scoring-api,incident-api,artifact-worker}/
├── data/{cicids2017,elastic_samples,synthetic_cloudtrail,synthetic_auth_log,mitre/enterprise-attack-v15.1.json}/
├── docs/{ARCHITECTURE,EVAL_RESULTS,SCALING_PATH,THREAT_MODEL}.md
├── .github/workflows/ci.yml
└── README.md
```

## Scaling path (post-sprint)

| Bottleneck | Sprint solution | Production solution |
|---|---|---|
| Stream processing throughput | Faust (Python, single worker) | Apache Flink (stateful, distributed, exactly-once) |
| ML scoring latency | Sync HTTP call from Faust | Async queue + model server pool (TorchServe/Triton) |
| LLM call volume | Alert clustering (10× reduction) | Async LLM queue with priority lanes; Claude Batch API for non-urgent triage |
| Postgres write throughput | Single TimescaleDB node | TimescaleDB Multinode or Citus |
| WebSocket connections | Single FastAPI process | Socket.io cluster with Redis adapter, or Pusher/Ably |
| Container orchestration | Docker Compose on single VM | Kubernetes (Helm charts in `/infra/helm/`) |
| Secrets | `.env` + Vercel env vars | HashiCorp Vault, dynamic DB credentials |
| Log sources | Python replay producer | Fluent Bit DaemonSet + CloudTrail EventBridge + Azure Activity Log |

## When answering questions with this skill

For endpoint-level detail use `soc-triager-api-reference`; for service implementation code use `soc-triager-backend`; for security/threat model use `soc-triager-security` and `soc-triager-cia-triad-access-control`; for UI structure use `soc-triager-dashboard-design` and `soc-triager-frontend`.
