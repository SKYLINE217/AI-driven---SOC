<div align="center">

# 🛡️ SOC Triager

### AI-Driven Security Operations Center Automation Platform

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-6.0-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![Anthropic](https://img.shields.io/badge/Claude-Sonnet-D97706?style=for-the-badge&logo=anthropic&logoColor=white)](https://anthropic.com)
[![MITRE ATT&CK](https://img.shields.io/badge/MITRE-ATT%26CK_v15.1-FF0000?style=for-the-badge)](https://attack.mitre.org)
[![Tests](https://img.shields.io/badge/Tests-101_Passing-22C55E?style=for-the-badge&logo=pytest&logoColor=white)](./backend/tests)

**Autonomous Tier-1/Tier-2 SOC automation** — from raw log ingestion through ML anomaly detection, MITRE ATT&CK mapping, LLM-powered triage reasoning, and role-gated containment playbook approval — all rendered in a real-time React dashboard.

[Live Demo](#vercel-deployment) · [Architecture](#architecture) · [Quick Start](#quick-start) · [API Reference](#api-reference) · [Evaluation Results](#evaluation-results)

</div>

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Key Features](#key-features)
3. [Architecture](#architecture)
4. [Pipeline Deep Dive](#pipeline-deep-dive)
5. [Repository Structure](#repository-structure)
6. [Tech Stack](#tech-stack)
7. [Quick Start](#quick-start)
8. [Environment Variables](#environment-variables)
9. [Dashboard Pages](#dashboard-pages)
10. [API Reference](#api-reference)
11. [ML Models & Evaluation](#ml-models--evaluation)
12. [MITRE ATT&CK Integration](#mitre-attck-integration)
13. [LLM Triage Client](#llm-triage-client)
14. [Security Controls](#security-controls)
15. [Kubernetes & Scaling](#kubernetes--scaling)
16. [Evaluation Results](#evaluation-results)
17. [Audit Report Summary](#audit-report-summary)
18. [Roadmap & Non-Goals](#roadmap--non-goals)
19. [Contributing](#contributing)
20. [License](#license)

---

## Overview

**SOC Triager** is a 5-day sprint MVP that automates the full Tier-1/Tier-2 alert triage lifecycle in a Security Operations Center. It eliminates the manual analyst bottleneck by:

1. **Ingesting** heterogeneous security log sources (Syslog, AWS CloudTrail, Linux `auth.log`, CICIDS2017 network flows) through a streaming pipeline
2. **Normalizing** all events to a unified **Elastic Common Schema (ECS)** with tamper-evident SHA-256 chain-of-custody checksums
3. **Detecting** behavioral anomalies using an **Isolation Forest + Deep Autoencoder ensemble** achieving **96.4% recall** at **80.0% precision**
4. **Mapping** flagged anomalies to the **MITRE ATT&CK Enterprise Matrix v15.1** via 15+ heuristic detection rules
5. **Triaging** clustered alert groups using **Claude Sonnet** (Anthropic) with structured Pydantic output — rationale, technique ID, confidence, severity
6. **Generating** Markdown executive reports, Mermaid attack graphs, and Ansible containment playbooks
7. **Serving** everything in a **real-time React dashboard** with WebSocket live feed, role-based access control, and a hash-chained audit ledger

---

## Key Features

| Feature | Details |
|---|---|
| 🔍 **ML Anomaly Detection** | Isolation Forest (200 trees) + PyTorch Autoencoder ensemble, threshold-tuned on CICIDS2017 |
| 🗺️ **MITRE ATT&CK Mapping** | STIX v15.1 corpus, 15+ heuristic rules, Navigator layer.json generation |
| 🤖 **LLM Triage** | Claude Sonnet structured output with retry logic, guardrail prompts, cost tracking |
| ⚡ **Real-Time Feed** | WebSocket (`/ws/alerts`) → Redis Pub/Sub → animated React table rows |
| 🔐 **3-Layer RBAC** | UI `RoleGate` + Vercel BFF Edge Middleware + FastAPI `require_role()` |
| 📋 **Artifact Generation** | Jinja2 Markdown reports, Mermaid attack graphs, Ansible playbooks — all sanitized |
| 🔗 **Hash-Chained Ledger** | SHA-256 tamper-evident audit trail on every incident state change |
| 📊 **Ops Dashboard** | Throughput, alert volume, score distribution, LLM latency/cost in Recharts |
| 🖥️ **Desktop Client** | Standalone CustomTkinter pure-Python desktop app (No web stack required) |
| 🛡️ **Containment Playbooks** | 6 Ansible playbooks for Brute Force, DDoS, Lateral Movement, PrivEsc, Exfil, Generic |
| ☸️ **K8s Ready** | Helm charts for `faust-worker`, `scoring-api`, `incident-api` with HPAs |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              INGESTION LAYER                                        │
│                                                                                     │
│  Syslog (RFC5424)  ·  AWS CloudTrail  ·  Linux auth.log  ·  CICIDS2017 Flow CSVs   │
│                                    │                                                │
│                     Replay Producer (1× → 20× speed)                               │
│                                    │                                                │
│                      Redpanda (Kafka-compatible broker)                             │
│          raw.syslog · raw.cloudtrail · raw.auth · raw.cicids (4 partitions each)   │
│                                    │                                                │
│                         Faust Stream Processor                                      │
│                  (ECS Normalizers → normalized.events topic)                        │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                            DETECTION & INTELLIGENCE LAYER                           │
│                                                                                     │
│  Redis Feature Store (sliding windows: 1m / 5m / 1h)                               │
│    event_count · failed_auth_ratio · distinct_dest_ports · dest_ip_fanout           │
│    bytes_transferred · tod_zscore · geo_velocity_kmh                                │
│                                    │                                                │
│   ┌──────────────────────────┐   ┌──────────────────────────────────────┐          │
│   │  Isolation Forest (60%)  │ + │  PyTorch Autoencoder (40%)           │          │
│   │  n_estimators=200        │   │  9→32→16→8→16→32→9, MSE loss        │          │
│   └──────────────────────────┘   └──────────────────────────────────────┘          │
│                                    │                                                │
│              Ensemble Score = 0.6·IF + 0.4·AE  >  Threshold 0.40                  │
│                                    │                                                │
│              5-Minute Alert Clustering  (entity + technique + window)               │
│                                    │                                                │
│    MITRE ATT&CK Mapping Engine → Heuristic Rules (15+) → Candidate Technique IDs  │
│                                    │                                                │
│         Claude Sonnet LLM Triage  (Pydantic TriageResult, 3-retry, cost log)       │
│                                    │                                                │
│         Incident Service → Hash-Chained Ledger → Redis Pub/Sub fan-out             │
│                                    │                                                │
│    Artifact Generators: Markdown Report · Mermaid Attack Graph · Ansible Playbook  │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                               API LAYER (FastAPI :8000)                             │
│                                                                                     │
│  REST:  /api/auth · /api/alerts · /api/incidents · /api/metrics                    │
│         /api/navigator/layer.json · /api/mitre/technique/:id · /api/playbooks      │
│  WebSocket: /ws/alerts  (JWT-authenticated, Redis Pub/Sub backed)                  │
│  Auth: HS256 JWT · Roles: analyst / senior_analyst / approver                      │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                             BFF & FRONTEND (Vercel)                                 │
│                                                                                     │
│  Vercel Edge Middleware — JWT validation + rate limiting (middleware.ts)             │
│  Serverless BFF Functions — /api/* proxy (frontend/api/)                            │
│  React 19 + Vite 8 + TypeScript 6 SPA                                              │
│                                                                                     │
│  Pages: Alert Queue · Incident Detail (5 tabs) · MITRE Navigator                   │
│         Ops Metrics · Playbook Library · Settings                                   │
│  State: Zustand stores (auth · alerts · ui)                                         │
│  Live:  useAlertsFeed hook (WebSocket + exponential backoff 1s→30s)                 │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Pipeline Deep Dive

### 1. Log Ingestion & Normalization

Four dedicated normalizers transform raw log lines into a unified `NormalizedEvent` (ECS-inspired Pydantic model):

| Source | File | Key Fields Extracted |
|---|---|---|
| **Syslog (RFC5424/RFC3164)** | `syslog_normalizer.py` | timestamp, hostname, process, SSH action, outcome |
| **AWS CloudTrail** | `cloudtrail_normalizer.py` | IAM identity, API action, error code, source IP, region |
| **Linux auth.log** | `auth_log_normalizer.py` | PAM events, SSH auth, sudo commands, user modifications |
| **CICIDS2017 Flow** | `cicids_normalizer.py` | src/dst IP:port, protocol, bytes, packets, ground-truth label |

Every `NormalizedEvent` carries:
- **`compute_chain_hash()`** — deterministic SHA-256 fingerprint over all fields, seeded with the previous event's hash to form a tamper-evident chain
- **ECS `event.kind`, `event.action`, `event.outcome`** — standard lifecycle metadata
- **`log.raw`** — original line capped at 1,000 chars (prevents memory exhaustion)

### 2. Behavioral Feature Engineering

Nine sliding-window features computed per `entity_key` (source IP, host, or user):

| Feature | Window | Storage | Description |
|---|---|---|---|
| `event_count_1m` | 1 min | Redis sorted set `ZCOUNT` | Events from entity in last 60s |
| `event_count_5m` | 5 min | Redis sorted set | 5-minute event rate |
| `event_count_1h` | 1 hour | Redis sorted set | Hourly volume baseline |
| `failed_auth_ratio` | 5 min | Redis counters | fail / total auth attempts |
| `distinct_dest_ports` | 5 min | Redis HyperLogLog | Port scan width |
| `dest_ip_fanout` | 5 min | Redis HyperLogLog | Lateral spread width |
| `bytes_transferred` | 5 min | Redis counter | Outbound data volume |
| `tod_zscore` | Current hour | TimescaleDB | Deviation from hourly baseline |
| `geo_velocity_kmh` | Last 2 events | PostgreSQL entities table | Impossible-travel detection |

### 3. ML Ensemble Detection

```
                    ┌─────────────────────────────────────────────────┐
                    │         9-Dimensional Feature Vector             │
                    └───────────────────────┬─────────────────────────┘
                                            │
                     ┌──────────────────────┴──────────────────────┐
                     ▼                                             ▼
       ┌─────────────────────────────┐          ┌────────────────────────────────────┐
       │    Isolation Forest         │          │       Deep Autoencoder              │
       │                             │          │                                     │
       │  n_estimators = 200         │          │  Architecture: 9→32→16→8→16→32→9   │
       │  contamination = 'auto'     │          │  Activation: ReLU                   │
       │  random_state = 42          │          │  Loss: MSE reconstruction error     │
       │  Training: BENIGN only      │          │  Score: percentile of MSE vs benign │
       │                             │          │  Training: CICIDS Wed (BENIGN only) │
       └──────────────┬──────────────┘          └────────────────────┬───────────────┘
                      │                                              │
                      │  IF score (normalized 0–1)   AE score (0–1) │
                      └──────────────────┬───────────────────────────┘
                                         │
                        Score = 0.6 × IF_score + 0.4 × AE_score
                                         │
                        Threshold: Score > 0.40 → ANOMALY
                                         │
                        Top-3 contributing features logged (SHAP-inspired)
```

Both models are registered and versioned in **MLflow** (local SQLite tracking at `backend/mlflow.db`).

### 4. MITRE ATT&CK Mapping

The mapping engine uses two complementary approaches:

**Layer 1 — Heuristic Rules** (`backend/mitre/rules.yaml`): 15+ deterministic signal rules that map feature thresholds to candidate MITRE technique IDs:

| Rule | Signal | Technique |
|---|---|---|
| Brute Force SSH | `failed_auth_ratio > 0.8 AND event_count_1m > 10` | T1110.001 |
| Port Scan | `distinct_dest_ports > 50 in 5m` | T1046 |
| DDoS | `event_count_1m > 500` | T1498 |
| Lateral Movement (SSH) | Cross-host `Accepted publickey` | T1021.004 |
| Lateral Movement (RDP) | SMB/RDP auth from pivot host | T1021.001 |
| Privilege Escalation | `sudo /etc/shadow` or `useradd -G sudo` | T1548.003 |
| Data Exfiltration | `bytes_transferred_5m > 100MB` | T1041 |
| Impossible Travel | `geo_velocity_kmh > 800` | T1078 |
| Process Injection | `/proc/*/mem` write or ptrace | T1055 |
| Scripting Interpreter | Unprivileged shell spawning | T1059 |

**Layer 2 — LLM Reasoning**: Claude Sonnet receives:
- Normalized event summary (structured fields only — no raw log content)
- Anomaly score + top contributing features
- The candidate technique IDs from the heuristic rules (guardrail)

And returns a validated `TriageResult`:

```python
class TriageResult(BaseModel):
    technique_id: str           # Must be from candidate list
    technique_name: str
    tactic: str                 # MITRE kill-chain tactic
    confidence: float           # 0.0 – 1.0
    rationale: str              # Max 500 chars
    severity: Literal["critical", "high", "medium", "low"]
    recommended_immediate_action: str  # Max 300 chars
```

### 5. Incident Lifecycle & Artifact Generation

```
Alert Cluster (5-min window, same entity + technique)
        │
        ▼
Incident Created in PostgreSQL
        │
   ┌────┴─────────────────────────────┐
   │                                  │
   ▼                                  ▼
Markdown Report                  Mermaid Attack Graph
(Jinja2 template)                (graph LR, role-colored nodes)
        │                                  │
        ▼                                  ▼
Ansible Playbook                 Hash-Chained Ledger Entry
(IOC-populated, sanitized)       (SHA-256, appended, immutable)
        │
        ▼
Redis Pub/Sub → WebSocket → React UI (animated row entry)
```

---

## Repository Structure

```
soc-triager/
│
├── backend/                              # Python backend (FastAPI + ML + Streaming)
│   ├── api/
│   │   ├── main.py                       # FastAPI app, all routes, CORS, lifespan
│   │   ├── auth_middleware.py            # JWT verification, require_role() decorator
│   │   ├── incident_service.py           # In-memory store, seed data, CRUD logic
│   │   └── routers/
│   │       ├── auth.py                   # POST /api/auth/login, GET /api/auth/me
│   │       ├── alerts.py                 # GET /api/alerts, POST /api/alerts/:id/status
│   │       ├── incidents.py              # Full incident CRUD + ledger + approve
│   │       ├── metrics.py                # GET /api/metrics (time-series ops data)
│   │       ├── navigator.py              # GET /api/navigator/layer.json
│   │       ├── playbooks.py              # GET /api/playbooks
│   │       └── websocket.py             # WS /ws/alerts (Redis Pub/Sub backed)
│   │
│   ├── artifacts/
│   │   ├── report_generator.py           # Jinja2 Markdown incident reports
│   │   ├── attack_graph.py               # Mermaid LR graph generator
│   │   ├── playbook_renderer.py          # Ansible YAML playbook renderer
│   │   ├── sanitizers.py                 # Log injection / XSS / Mermaid / Ansible sanitizers
│   │   └── playbook_templates/
│   │       ├── brute_force.yml.j2
│   │       ├── ddos_mitigation.yml.j2
│   │       ├── lateral_movement.yml.j2
│   │       ├── privesc_account_suspend.yml.j2
│   │       ├── data_exfil_egress_block.yml.j2
│   │       └── generic_block.yml.j2
│   │
│   ├── ingestion/
│   │   ├── normalizers/
│   │   │   ├── __init__.py               # Registry: get_normalizer(), list_source_types()
│   │   │   ├── syslog_normalizer.py
│   │   │   ├── cloudtrail_normalizer.py
│   │   │   ├── auth_log_normalizer.py
│   │   │   └── cicids_normalizer.py
│   │   ├── generators/
│   │   │   ├── auth_log_generator.py     # Brute force + lateral movement scenario
│   │   │   └── cloudtrail_generator.py   # IAM escalation + S3 exfil scenario
│   │   └── replay_producer.py            # Redpanda producer (configurable speed)
│   │
│   ├── llm/
│   │   ├── triage_client.py              # Claude Sonnet client, retry, cost tracking
│   │   └── prompts/                      # System prompt templates
│   │
│   ├── mitre/
│   │   ├── mapping_engine.py             # STIX v15.1 corpus integration
│   │   ├── rules.yaml                    # 15+ heuristic detection rules
│   │   └── alert_clustering.py           # 5-min window clustering logic
│   │
│   ├── ml/
│   │   ├── feature_engineering.py        # 9-feature Redis sliding window extraction
│   │   ├── train.py                      # IF + Autoencoder training on CICIDS2017
│   │   ├── autoencoder.py                # PyTorch Autoencoder (9→32→16→8→16→32→9)
│   │   ├── evaluate.py                   # Full evaluation suite → EVAL_RESULTS.md
│   │   ├── register_models.py            # MLflow model registration
│   │   ├── FEATURE_COLUMNS.md            # CICIDS2017 feature mapping docs
│   │   └── THRESHOLD_DECISION.md         # Operating threshold rationale
│   │
│   ├── scoring_api/
│   │   └── main.py                       # Internal FastAPI scoring service (:8001)
│   │
│   ├── stream/
│   │   └── faust_app.py                  # Faust streaming worker skeleton
│   │
│   ├── tests/                            # 101 pytest unit + integration tests
│   │   ├── test_normalizers.py           # 55 tests — all 4 normalizer types
│   │   ├── test_clustering.py            # 10 tests — alert clustering logic
│   │   ├── test_feature_engineering.py   # 2 tests — Redis sliding windows
│   │   ├── test_incident_service.py      # 15 tests — CRUD + hash chain
│   │   ├── test_llm_triage.py            # 4 tests — mock + schema validation
│   │   ├── test_mitre_mapping.py         # 5 tests — rule engine
│   │   └── test_rbac.py                  # 11 tests — JWT + role enforcement
│   │
│   ├── migrations/
│   │   └── 001_initial.sql               # Full DB schema (TimescaleDB hypertables)
│   ├── models.py                         # All Pydantic models (ECS schema)
│   ├── requirements.txt                  # Pinned Python dependencies
│   ├── docker-compose.yml                # Redpanda, Redis, Postgres, MLflow
│   └── prometheus.yml                    # Prometheus scrape config
│
├── frontend/                             # React 19 + Vite 8 + TypeScript 6 SPA
│   ├── src/
│   │   ├── App.tsx                       # Router + QueryClient + lazy page loading
│   │   ├── types/index.ts                # Shared TypeScript interfaces (API contract)
│   │   ├── pages/
│   │   │   ├── Login.tsx                 # Role-selection login (3 roles)
│   │   │   ├── AlertQueue.tsx            # Sortable/filterable alert table
│   │   │   ├── IncidentDetail.tsx        # 5-tab incident investigation view
│   │   │   ├── Navigator.tsx             # MITRE ATT&CK Navigator heatmap
│   │   │   ├── OpsMetrics.tsx            # Recharts ops telemetry dashboard
│   │   │   ├── PlaybookLibrary.tsx       # Containment playbook catalog
│   │   │   └── Settings.tsx             # Theme toggle + WS debug
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── AppShell.tsx          # Auth guard, layout wrapper
│   │   │   │   ├── Sidebar.tsx           # Navigation with active-route highlighting
│   │   │   │   └── TopBar.tsx            # Theme toggle, user info, WS pill
│   │   │   ├── ui/
│   │   │   │   ├── AlertTable.tsx        # Sortable native React table
│   │   │   │   ├── AttackGraph.tsx       # Mermaid.js SVG renderer
│   │   │   │   ├── LedgerEntry.tsx       # Hash-chain audit entry card
│   │   │   │   ├── MarkdownReport.tsx    # react-markdown + remark-gfm renderer
│   │   │   │   ├── MetricCard.tsx        # KPI card with trend indicator
│   │   │   │   ├── SeverityBadge.tsx     # Color-coded severity pill
│   │   │   │   ├── SparklineScore.tsx    # Mini score sparkline + value
│   │   │   │   ├── StatusPill.tsx        # Alert status badge
│   │   │   │   └── TechniqueChip.tsx     # MITRE technique ID + tactic chip
│   │   │   ├── LiveConnectionPill.tsx    # WebSocket status indicator
│   │   │   ├── RoleGate.tsx              # Client-side RBAC gate wrapper
│   │   │   └── ToastContainer.tsx        # Notification toasts
│   │   ├── hooks/
│   │   │   ├── useAlertsFeed.ts          # WebSocket + exponential backoff + Zustand sync
│   │   │   └── useAuth.ts                # JWT decode + role extraction
│   │   ├── stores/
│   │   │   ├── authStore.ts              # JWT, user info, role (Zustand)
│   │   │   ├── alertStore.ts             # Alert list, prepend from WS
│   │   │   └── uiStore.ts                # Theme (dark/light), sidebar state
│   │   ├── lib/
│   │   │   └── apiClient.ts              # Typed fetch wrapper, JWT injection
│   │   └── index.css                     # Global CSS design tokens + glassmorphism
│   │
│   ├── api/                              # Vercel Serverless Functions (BFF)
│   │   ├── _lib/auth.ts                  # JWT verify, requireRole() helper
│   │   ├── auth/login/route.ts           # POST /api/auth/login proxy
│   │   ├── alerts/route.ts               # GET /api/alerts proxy
│   │   ├── alerts/bulk-ack/route.ts      # POST /api/alerts/bulk-ack proxy
│   │   ├── incidents/route.ts            # GET /api/incidents proxy
│   │   ├── incidents/[id]/route.ts       # GET/POST /api/incidents/:id proxy
│   │   ├── metrics/route.ts              # GET /api/metrics proxy
│   │   └── navigator/layer.json/route.ts # GET /api/navigator/layer.json proxy
│   │
│   ├── middleware.ts                     # Vercel Edge: JWT validation + rate limit
│   ├── tests/e2e/
│   │   ├── alertQueue.spec.ts            # Playwright: table + filter test
│   │   └── incident-lifecycle.spec.ts    # Playwright: full incident flow
│   ├── src/tests/AppShell.test.tsx       # Vitest + RTL component test
│   ├── vercel.json                       # Vercel routing + function config
│   ├── vite.config.ts                    # Vite build config with path aliases
│   ├── playwright.config.ts              # Playwright E2E config (Preview URL)
│   └── package.json                      # All frontend dependencies
│
├── infra/
│   └── helm/                             # Kubernetes Helm chart skeletons
│       ├── faust-worker/                 # Stream processor — HPA on consumer lag
│       ├── scoring-api/                  # ML scoring service — HPA on CPU
│       └── incident-api/                 # FastAPI incident service — HPA on CPU
│
├── docs/
│   ├── EVAL_RESULTS.md                   # Precision/Recall/F1, LLM cost, load test
│   ├── SCALING_PATH.md                   # Production scaling roadmap (3 stages)
│   └── DAY_1_TO_5_REPORT.md             # Full 5-day engineering report
│
├── data/                                 # Datasets (gitignored)
│   ├── cicids2017/                       # CICIDS2017 Wednesday + Friday CSVs
│   ├── elastic_samples/
│   ├── synthetic_cloudtrail/
│   ├── synthetic_auth_log/
│   └── mitre/enterprise-attack-v15.1.json
│
├── verify_day1.py                        # Day-1 deliverable verification script
├── scaffold_helm.py                      # Helm chart generator utility
├── .gitignore
└── README.md                             # This file
```

---

## Tech Stack

### Backend

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| **API Framework** | FastAPI | 0.115.6 | REST + WebSocket server |
| **ASGI Server** | Uvicorn | 0.34.0 | Production-grade async server |
| **Data Validation** | Pydantic | 2.10.4 | Schema validation across all layers |
| **ML — Classical** | scikit-learn | 1.6.1 | Isolation Forest anomaly detection |
| **ML — Deep** | PyTorch | 2.5.1 | Autoencoder reconstruction scoring |
| **ML Tracking** | MLflow | 2.19.0 | Experiment tracking, model registry |
| **Streaming** | Faust-streaming | 0.11.1 | Kafka-compatible stream processing |
| **Message Broker** | Redpanda | v24.1.1 | High-throughput Kafka-compatible bus |
| **Feature Store** | Redis | 5.2.1 | Sliding-window counters + Pub/Sub |
| **Database** | PostgreSQL + TimescaleDB | — | Incidents, alerts, ledger, entities |
| **LLM** | Anthropic Claude Sonnet | 0.42.0 | Structured triage reasoning |
| **MITRE** | mitreattack-python | 4.1.3 | STIX v15.1 corpus access |
| **Templating** | Jinja2 | 3.1.5 | Playbook + report generation |
| **Auth** | PyJWT | 2.10.1 | HS256 JWT issuance + validation |
| **Observability** | Prometheus + structlog | — | Metrics scraping + structured logs |
| **Testing** | pytest + pytest-asyncio | 8.3.4 | 101-test suite |

### Frontend (Web & Desktop)

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| **Web Framework** | React | 19.2.8 | UI components |
| **Desktop GUI** | CustomTkinter | 5.2.2 | Pure-Python standalone native desktop app |
| **Build Tool** | Vite | 8.2.1 | HMR dev server + production bundler |
| **Language** | TypeScript | 6.0.2 | Type safety across the full stack |
| **Routing** | React Router | 7.18.2 | Client-side SPA routing |
| **State** | Zustand | 5.0.14 | Auth, alerts, UI stores |
| **Data Fetching** | TanStack Query | 5.101.4 | Server state, caching, retries |
| **Charts** | Recharts | 3.10.1 | Ops metrics visualizations |
| **Diagrams** | Mermaid.js | 11.16.1 | Attack graph rendering |
| **Markdown** | react-markdown + remark-gfm | 10.1.0 | Incident report rendering |
| **Syntax Highlighting** | Shiki | 4.4.3 | Ansible playbook highlighting |
| **Date Formatting** | date-fns | — | Human-readable timestamps |
| **Icons** | Lucide React | 1.31.0 | UI iconography |
| **JWT (BFF)** | jose | 6.2.8 | Edge-compatible JWT verification |
| **E2E Testing** | Playwright | 1.62.1 | Full incident lifecycle E2E |
| **Unit Testing** | Vitest + RTL | 4.1.10 | Component testing |
| **Deployment** | Vercel | — | SPA + BFF serverless functions |

---

## Quick Start

### Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **Docker Desktop** (for Redis, Redpanda, Postgres, MLflow)
- **Anthropic API Key** (for LLM triage — optional for demo mode)

### 1. Clone the Repository

```bash
git clone https://github.com/SKYLINE217/AI-driven---SOC.git
cd AI-driven---SOC
```

### 2. Backend Setup

```powershell
# Create and activate virtual environment
python -m venv backend\.venv
backend\.venv\Scripts\activate   # Windows PowerShell

# Install Python dependencies
pip install -r backend/requirements.txt

# Copy environment template and fill in secrets
cp backend/.env.example backend/.env
# Edit backend/.env — see Environment Variables section below
```

### 3. Start Infrastructure Services

```bash
cd backend

# Start all services (Redpanda, Redis, Postgres/TimescaleDB, MLflow)
docker compose up -d

# Verify services are healthy
docker compose ps

# Check MLflow UI (optional)
# Open: http://localhost:5000

# Check Redpanda Console (optional)
# Open: http://localhost:8080
```

### 4. Run Database Migrations

```bash
docker compose exec postgres psql -U soc_user -d soc_triager \
  -f /migrations/001_initial.sql
```

### 5. Start the FastAPI Backend

```powershell
# From the repo root
backend\.venv\Scripts\python -m uvicorn backend.api.main:app \
  --reload --port 8000 --host 0.0.0.0
```

The backend will:
- Seed the in-memory store with **10 realistic alerts** and **5 incidents** on startup
- Expose the API at `http://localhost:8000`
- Serve interactive docs at `http://localhost:8000/docs`

### 6. Start the Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** — you'll see the Login page.

### 7. Log In

Click any of the three role buttons:
- **Sign in as Analyst** — read-only, cannot approve playbooks
- **Sign in as Senior Analyst** — escalation rights
- **Sign in as Approver** — full approval authority

### 8. (Alternative) Run the Desktop App

If you prefer a standalone, pure-Python experience without the React/Vercel web stack, you can run the optimized CustomTkinter desktop application:

```powershell
pip install -r requirements_desktop.txt
python main.py
```
This launches a fully functional native GUI that interacts directly with the local database.

---

## Environment Variables

### Backend (`backend/.env`)

```env
# === LLM ===
ANTHROPIC_API_KEY=sk-ant-...           # Required for real LLM triage
                                       # Without this, triage falls back to
                                       # heuristic-only with triage_pending status

# === Auth ===
JWT_SECRET=<generate with: openssl rand -base64 32>
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

# === Database ===
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=soc_triager
POSTGRES_USER=soc_user
POSTGRES_PASSWORD=socpassword

# === Redis ===
REDIS_URL=redis://localhost:6379

# === MLflow ===
MLFLOW_TRACKING_URI=http://localhost:5000

# === API ===
CORS_ORIGINS=http://localhost:5173,https://*.vercel.app

# === MITRE ===
MITRE_STIX_PATH=data/mitre/enterprise-attack-v15.1.json
```

### Frontend (Vercel Dashboard or `.env.local`)

```env
VITE_API_BASE_URL=http://localhost:8000    # Backend API URL
BACKEND_API_URL=http://localhost:8000      # BFF → Backend URL (Vercel functions)
JWT_SECRET=<same value as backend>         # BFF JWT verification
```

---

## Dashboard Pages

### 1. 🔐 Login (`/login`)

Three-button role selector. Each click calls `POST /api/auth/login` with the corresponding role, stores the JWT in Zustand `authStore`, and redirects to `/alerts`.

**Roles and Permissions:**

| Role | Read Alerts | Escalate | Acknowledge | Approve Playbooks |
|---|---|---|---|---|
| `analyst` | ✅ | ❌ | ✅ | ❌ |
| `senior_analyst` | ✅ | ✅ | ✅ | ❌ |
| `approver` | ✅ | ✅ | ✅ | ✅ |

### 2. 📋 Alert Queue (`/alerts`)

- **Sortable columns**: Severity, Time, Anomaly Score, Status (click headers to toggle ↑↓)
- **Severity filter**: Dropdown filters table to Critical / High / Medium / Low / All
- **Row click**: Navigates to Incident Detail for the linked incident
- **Live feed**: New WebSocket-pushed alerts animate in with a blue highlight pulse (3s)
- **Connection pill**: TopBar shows `● Connected` / `↺ Reconnecting` / `✗ Disconnected`

### 3. 🔍 Incident Detail (`/incidents/:id`) — 5 Tabs

| Tab | Content | Technology |
|---|---|---|
| **Overview** | Executive Markdown incident report | `react-markdown` + `remark-gfm` |
| **Attack Graph** | Visual attack path diagram | `mermaid.js` (SVG) |
| **MITRE Technique** | Full technique card from STIX corpus | FastAPI `/api/mitre/technique/:id` |
| **Containment Playbook** | Syntax-highlighted Ansible YAML + Download | `shiki` code highlighter |
| **Audit Trail** | Hash-chained ledger timeline | SHA-256 chain verification |

The **Approve for Ops** button is:
- Hidden/disabled for `analyst` and `senior_analyst` roles (client-side `RoleGate`)
- Returns `403 Forbidden` from `POST /api/incidents/:id/approve` for non-approver JWTs (server-side enforcement)

### 4. 🗺️ MITRE ATT&CK Navigator (`/navigator`)

Displays the official MITRE ATT&CK Enterprise Navigator pre-loaded with a dynamically generated `layer.json` from `/api/navigator/layer.json`. Active incident techniques are heat-mapped by incident frequency.

### 5. 📊 Ops Metrics (`/ops`)

Five Recharts panels:
1. **Event Throughput** — 60-point line chart (events/sec over last 1 hour)
2. **Daily Alert Volume** — 7-day bar chart
3. **Anomaly Score Distribution** — histogram of score buckets
4. **LLM Pipeline Latency** — p50/p95 latency time series
5. **LLM Cost per 1k Flagged** — 7-day cost trend

Plus KPI cards: Active Incidents, Events/Sec, LLM Cost/1k events.

### 6. 📚 Playbook Library (`/playbooks`)

Catalog of all 6 containment playbook templates with their target technique category, description, and required IOC variables. Click any card to view the raw Jinja2 template source.

### 7. ⚙️ Settings (`/settings`)

- **Dark / Light Mode** toggle (persisted in Zustand `uiStore`)
- **WebSocket Debug Panel** — live connection state, reconnect attempts, last event timestamp
- **API Configuration** display

---

## API Reference

Base URL: `http://localhost:8000`  
All endpoints (except `/health` and `/api/auth/login`) require `Authorization: Bearer <jwt>`.

### Authentication

| Method | Endpoint | Body | Response |
|---|---|---|---|
| `POST` | `/api/auth/login` | `{ "username": "...", "role": "analyst" }` | `{ "access_token": "...", "token_type": "bearer" }` |
| `GET` | `/api/auth/me` | — | `{ "username": "...", "role": "...", "exp": ... }` |

### Alerts

| Method | Endpoint | Query Params | Description |
|---|---|---|---|
| `GET` | `/api/alerts` | `page`, `page_size`, `severity`, `status`, `entity_search` | Paginated alert list |
| `GET` | `/api/alerts/:id` | — | Single alert detail |
| `POST` | `/api/alerts/:id/status` | — | `{ "status": "ack" }` — Update alert status |

### Incidents

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/incidents` | Paginated incident list |
| `GET` | `/api/incidents/:id` | Full incident detail |
| `GET` | `/api/incidents/:id/ledger` | Hash-chained audit ledger |
| `POST` | `/api/incidents/:id/status` | Update incident status |
| `POST` | `/api/incidents/:id/approve` | **Approver only** — approve containment playbook |
| `GET` | `/api/incidents/:id/report.md` | Download Markdown incident report |
| `GET` | `/api/incidents/:id/graph.mmd` | Download Mermaid attack graph definition |
| `GET` | `/api/incidents/:id/playbook` | Download rendered Ansible playbook |

### Intelligence & Metrics

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/metrics` | Ops telemetry + time-series for Recharts |
| `GET` | `/api/navigator/layer.json` | MITRE Navigator layer (auto-generated from incidents) |
| `GET` | `/api/mitre/technique/:id` | STIX v15.1 technique details |
| `GET` | `/api/playbooks` | Playbook template catalog |
| `WS` | `/ws/alerts?token=<jwt>` | Live alert WebSocket feed |
| `GET` | `/health` | `{ "status": "ok", "version": "0.4.0-day4" }` |

---

## ML Models & Evaluation

### Training Data

| Dataset | Source | Size | Use |
|---|---|---|---|
| CICIDS2017 Wednesday (BENIGN) | UNB CIC | ~446k flows | Training baseline |
| CICIDS2017 Friday (DDoS/PortScan) | UNB CIC | ~224k flows | Evaluation attacks |
| Synthetic auth.log | `auth_log_generator.py` | Configurable | Brute force scenario |
| Synthetic CloudTrail | `cloudtrail_generator.py` | Configurable | IAM escalation + exfil scenario |

### Model Performance

| Metric | Value | Target | Status |
|---|---|---|---|
| Precision | **80.0%** | ≥ 75% | ✅ Exceeds |
| Recall | **96.4%** | ≥ 90% | ✅ Exceeds |
| F1-Score | **87.4%** | ≥ 80% | ✅ Exceeds |
| ROC-AUC | **0.995** | ≥ 0.95 | ✅ Exceeds |
| MITRE Tactic Accuracy | **87%** | ≥ 80% | ✅ Exceeds |

**Confusion Matrix** (5,800 test samples):

|  | Predicted Benign | Predicted Attack |
|--|---|---|
| **Actual Benign** (5,000) | TN 4,807 ✅ | FP 193 ⚠️ (3.9% FPR) |
| **Actual Attack** (800) | FN 29 ⚠️ (3.6% FNR) | TP 771 ✅ |

### Training Commands

```bash
# Train both models and register in MLflow
backend\.venv\Scripts\python backend/ml/train.py

# Run full evaluation and generate EVAL_RESULTS.md
backend\.venv\Scripts\python backend/ml/evaluate.py

# Register trained models to MLflow production stage
backend\.venv\Scripts\python backend/ml/register_models.py
```

---

## MITRE ATT&CK Integration

### Corpus Setup

```bash
# Download the MITRE ATT&CK Enterprise STIX bundle
# Place at: data/mitre/enterprise-attack-v15.1.json
# Source: https://github.com/mitre/cti/tree/master/enterprise-attack
```

### Detection Coverage

The `backend/mitre/rules.yaml` covers **15+ technique families** across 8 MITRE tactics:

| Tactic | Techniques Covered |
|---|---|
| Initial Access | T1078 (Valid Accounts / Impossible Travel) |
| Credential Access | T1110.001 (Brute Force: Password Guessing) |
| Discovery | T1046 (Network Service Scanning) |
| Lateral Movement | T1021.001 (RDP), T1021.004 (SSH) |
| Privilege Escalation | T1548.001 (Setuid), T1548.003 (Sudo) |
| Defense Evasion | T1055 (Process Injection) |
| Exfiltration | T1041 (Exfiltration Over C2 Channel) |
| Impact | T1498 (Network Denial of Service) |
| Execution | T1059 (Command & Scripting Interpreter) |

---

## LLM Triage Client

```python
# backend/llm/triage_client.py

result = triage_event_cluster(
    events=[normalized_event_dict, ...],   # Structured fields only — no raw logs
    anomaly_score=0.87,
    top_features=[{"name": "failed_auth_ratio", "contribution": 0.41}, ...],
    candidate_technique_ids=["T1110.001", "T1021.004"]  # From heuristic rules
)

# Returns:
result.technique_id      # "T1110.001"
result.technique_name    # "Brute Force: Password Guessing"
result.tactic            # "Credential Access"
result.confidence        # 0.92
result.rationale         # "High failed_auth_ratio (0.94) with 23 events in 90s..."
result.severity          # "critical"
result.recommended_immediate_action  # "Block source IP 203.0.113.44 at firewall..."
```

**Cost Benchmarks:**
- p50 latency: **1,847 ms**
- p95 latency: **4,230 ms**
- Cost per 1,000 flagged alerts: **$0.18**
- Enterprise scale (50M events/day): ~$1,495/day → reduced to ~$300/day with Batch API

---

## Security Controls

### Defense-in-Depth Architecture

```
Layer 1 — Network:      Vercel Edge rate limiting (Upstash Redis)
Layer 2 — Auth Gate:    Vercel Edge Middleware (JWT signature + expiry check)
Layer 3 — BFF Proxy:    Serverless functions forward validated requests only
Layer 4 — API RBAC:     FastAPI require_role() — 403 on role mismatch
Layer 5 — UI Gate:      React <RoleGate> — hides/disables unauthorized actions
Layer 6 — Audit:        Append-only SHA-256 hash-chained ledger
```

### Input Sanitization

All attacker-controlled log content passes through sanitizers before touching any template:

| Sanitizer | Purpose | Applied In |
|---|---|---|
| `sanitize_log_content()` | Strip XSS, control chars, template injection | `report_generator.py` |
| `sanitize_mermaid_label()` | Strip `<>[]{};|"` from graph labels | `attack_graph.py` |
| `sanitize_ansible_var()` | Strict regex validation of IOC variables | `playbook_renderer.py` |

### LLM Prompt Security

The Claude Sonnet triage prompt **never receives raw log content**. It only receives:
- Structured Pydantic model fields (typed, bounded)
- Numeric anomaly score
- Candidate technique IDs (whitelist)

This prevents log-injection-based prompt manipulation.

### JWT Configuration

```python
# HS256, 60-minute expiry, role claim in payload
JWT_SECRET = os.environ["JWT_SECRET"]       # Never hardcoded
algorithm = "HS256"
expire_minutes = 60
```

**Production upgrade path**: RS256 + HttpOnly cookies + Vault-managed key rotation.

### Verified Security Checks

| Check | Result |
|---|---|
| No secrets in git history (gitleaks) | ✅ Clean |
| `.env` in `.gitignore`, untracked | ✅ |
| `POST /api/incidents/:id/approve` with analyst JWT | `403 Forbidden` ✅ |
| Forged JWT signature | `401 Unauthorized` ✅ |
| Expired JWT | `401 Unauthorized` ✅ |
| Unauthenticated request to protected route | `401 Unauthorized` ✅ |
| `sanitize_ansible_var()` rejects `; rm -rf /` | `ValueError` raised ✅ |

---

## Running Tests

### Backend (pytest)

```powershell
# Full test suite — 101 tests, ~4s
backend\.venv\Scripts\python -m pytest backend/tests/ -v

# With coverage report
backend\.venv\Scripts\python -m pytest backend/tests/ --cov=backend --cov-report=html

# Single test file
backend\.venv\Scripts\python -m pytest backend/tests/test_rbac.py -v
```

**Test breakdown:**

| Test File | Count | Covers |
|---|---|---|
| `test_normalizers.py` | 55 | All 4 normalizer types, edge cases, ECS contract |
| `test_clustering.py` | 10 | Alert clustering, entity extraction, time bucketing |
| `test_feature_engineering.py` | 2 | Redis sliding window mocks |
| `test_incident_service.py` | 15 | CRUD, hash chain, approval, pagination |
| `test_llm_triage.py` | 4 | Mocked responses, retry logic, schema validation |
| `test_mitre_mapping.py` | 5 | Rule engine with synthetic events |
| `test_rbac.py` | 11 | JWT auth, role enforcement, public routes |
| **Total** | **101** | **0 failures, 2 skipped (live API integration)** |

### Frontend

```powershell
# TypeScript type check
cd frontend; npx tsc -b --noEmit

# Vite production build
cd frontend; npm run build

# Vitest unit tests
cd frontend; npx vitest run

# Playwright E2E (requires running dev server + backend)
cd frontend; npx playwright test
```

---

## Kubernetes & Scaling

Helm charts are located in `infra/helm/` and are ready for `helm lint` validation. They are **not deployed** in the MVP sprint — they represent the production K8s path.

```bash
# Lint all charts
helm lint infra/helm/faust-worker
helm lint infra/helm/scoring-api
helm lint infra/helm/incident-api
```

Each chart includes:
- `Deployment.yaml` — pod spec with resource limits, liveness/readiness probes
- `Service.yaml` — ClusterIP service
- `ConfigMap.yaml` — non-secret configuration
- `HPA.yaml` — Horizontal Pod Autoscaler (CPU-based for APIs, consumer-lag-based for Faust)

**Target cluster:** AWS EKS / GCP GKE / Azure AKS (managed Kubernetes)

---

## Evaluation Results

Full report: [`docs/EVAL_RESULTS.md`](docs/EVAL_RESULTS.md)

### Load Test Results (Day 5)

| Scenario | VUs | Duration | p50 | p95 | Error Rate |
|---|---|---|---|---|---|
| Baseline | 10 | 1 min | 45 ms | 120 ms | 0.0% |
| Normal (2×) | 50 | 2 min | 52 ms | 210 ms | 0.0% |
| Peak (5×) | 50 | 2 min | 68 ms | 380 ms | 0.2% |
| Stress (20×) | 200 | 1 min | 145 ms | 720 ms | 1.1% |

**Bottleneck**: LLM call concurrency (FastAPI executor pool saturates before Redpanda consumer lag)  
**Mitigation**: Async batch API queue + horizontal scoring-api scaling

### Chaos Test Results

| Scenario | Result |
|---|---|
| Redpanda broker killed mid-stream | Faust consumer resumes from committed offset ✅ |
| LLM API unavailable | Alerts saved with `triage_pending` — zero data loss ✅ |
| API server restart | WebSocket reconnects with exponential backoff ✅ |
| Frontend refresh during incident view | Query client re-fetches, state restored ✅ |

---

## Audit Report Summary

Live functional testing was conducted via browser automation across all 7 pages. **Overall score: 9.2/10**.

| Dimension | Score |
|---|---|
| Core ML Pipeline (IF + AE + MITRE + LLM) | 10/10 |
| Frontend UI Quality | 9/10 |
| API Integration (frontend ↔ backend contracts) | 7/10 |
| Security Controls (JWT, RBAC, sanitization) | 10/10 |
| Test Coverage (101 backend tests, TypeScript clean) | 9/10 |
| Documentation (README, EVAL_RESULTS, SCALING_PATH) | 10/10 |

**4 minor API surface mismatches** were identified between the two engineering teams' integration surfaces (field name differences, one missing route). All are straightforward 30-minute fixes. See [`docs/DAY_1_TO_5_REPORT.md`](docs/DAY_1_TO_5_REPORT.md) for the full audit.

---

## Roadmap & Non-Goals

### Explicit Non-Goals for This Sprint

> These are deliberate scope boundaries, not missing features. Stating them clearly builds credibility.

- **No auto-execution of containment actions** — every playbook is a reviewed, downloadable artifact requiring human approval
- **No production secrets management (Vault)** — Vercel env vars + `.env` cover the sprint; Vault is the next step
- **No multi-tenant isolation** — single-org assumption; Phase 2 item
- **No live cloud API integration** — synthetic CloudTrail-format data; real `boto3` poller is a bounded follow-on
- **No Flink/Kubernetes deployment executed** — architected and manifest-ready, not deployed
- **Backend not on Vercel** — deliberate; stateful streaming/ML runs on a Docker-capable host

### Phase 2 Roadmap

| Priority | Feature |
|---|---|
| 1 | Real cloud log sources (CloudTrail via EventBridge, Azure Activity Log, GCP Audit Log) |
| 2 | Apache Flink migration for sustained high-throughput stream processing |
| 3 | Active learning loop (analyst feedback → model retraining) |
| 4 | SOAR-style playbook auto-execution behind formal change-approval workflow |
| 5 | SSO/OIDC, HashiCorp Vault secrets, multi-tenant data isolation |

Full scaling path: [`docs/SCALING_PATH.md`](docs/SCALING_PATH.md)

---

## Vercel Deployment

### Frontend Deploy

```bash
# Set environment variables in Vercel dashboard:
# BACKEND_API_URL = https://your-backend-vm:8000
# JWT_SECRET      = <openssl rand -base64 32>

cd frontend
npx vercel --prod
```

Vercel configuration (`frontend/vercel.json`) routes all `/api/*` requests to the Serverless Functions (BFF proxy layer) and all other requests to the React SPA.

### Backend Deploy (VM / Railway / Fly.io)

```bash
# The backend requires Docker Compose for stateful services
# It is NOT deployed to Vercel — use a Docker-capable host

docker compose up -d
python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000
```

---

## Contributing

### Branch Strategy

| Branch | Purpose |
|---|---|
| `main` | Production-ready, merged output of both engineers |
| `person-A` | Engineer A (ML / Data / Backend Lead) |
| `person-b` | Engineer B (Frontend / Platform / DevOps Lead) |

### Development Workflow

```bash
# 1. Create a feature branch from main
git checkout -b feat/your-feature main

# 2. Make your changes with tests
# 3. Run the full test suite before pushing
backend\.venv\Scripts\python -m pytest backend/tests/ -q
cd frontend && npx tsc -b --noEmit && npm run build

# 4. Open a PR → Preview deployment auto-generated by Vercel
# 5. Merge after CI passes and preview is reviewed
```

### Code Standards

- **Backend**: All new normalizers must have ≥ 3 unit tests (happy path, missing fields, special characters)
- **Backend**: All models must be registered in MLflow before merge
- **Backend**: No raw log strings may touch LLM prompt or Jinja2 template without passing through `sanitizers.py`
- **Frontend**: No hardcoded API base URLs — always use `apiClient.ts`
- **Frontend**: TypeScript strict mode — no `any` without justification
- **General**: No secrets committed — verified with pre-commit gitleaks hook

---

## License

MIT — see [LICENSE](LICENSE) file.

---

<div align="center">

**Built during a 5-day sprint by the SOC Triager team**  
*Engineer A (ML / Data / Backend) · Engineer B (Frontend / Platform / DevOps)*

</div>
