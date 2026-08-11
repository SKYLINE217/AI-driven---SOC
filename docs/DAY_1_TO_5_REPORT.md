# SOC Triager — Comprehensive Day 1 to Day 5 Engineering Report

**Repository:** [AI-driven---SOC](https://github.com/SKYLINE217/AI-driven---SOC)  
**Authors:** Engineer A (ML / Data / Backend Lead) & Engineer B (Frontend / Platform / DevOps Lead)  
**Date:** 2026-08-11  

---

## 1. Executive Summary & System Overview

**SOC Triager** is an autonomous Tier-1/Tier-2 Security Operations Center platform designed to automate the security alert lifecycle:
1. Ingesting heterogeneous high-volume security logs (Syslog, AWS CloudTrail, Linux `auth.log`, CICIDS2017 flow data).
2. Transforming logs into a unified **Elastic Common Schema (ECS)** representation with tamper-evident **SHA-256 chain-of-custody checksums**.
3. Computing sliding-window behavioral features in **Redis** (hot) and **TimescaleDB** (cold).
4. Running real-time anomaly detection via an **Isolation Forest + Deep Autoencoder ensemble** ($0.6 \cdot \text{IF} + 0.4 \cdot \text{AE}$) achieving **96.4% recall** and **80.0% precision** at an operating threshold of 0.40.
5. Clustering related alerts across 5-minute windows and mapping observed anomalies to the **MITRE ATT&CK Enterprise Matrix (v15.1)** using heuristic rules and **Claude Sonnet LLM triage**.
6. Generating rich investigation and remediation artifacts: **Markdown executive incident reports**, **Mermaid attack graphs**, and **Ansible containment playbooks**.
7. Serving real-time incident data via a **Vercel-deployed React/Vite SPA** backed by a **FastAPI REST + WebSocket layer** with multi-layer **Role-Based Access Control (RBAC)**.

---

## 2. Daily Engineering Deliverables (Day 1 – Day 5)

```
┌───────────────────────────────────────────────────────────────────────────────────────┐
│                                 INGESTION LAYER                                       │
│  Syslog (RFC5424) · AWS CloudTrail · Linux auth.log · CICIDS2017 Flow Data            │
│                                        │                                              │
│                                        ▼                                              │
│              Faust Stream Processor (Redpanda) → ECS Normalizers                      │
│                                        │                                              │
│                                        ▼                                              │
│               Sliding-Window Feature Store (Redis Hot / TimescaleDB Cold)             │
│                                        │                                              │
│                                        ▼                                              │
│          ML Scoring API (FastAPI :8001) — Isolation Forest + Autoencoder Ensemble     │
│                         (Anomaly Score > 0.40 Operating Threshold)                    │
│                                        │                                              │
│                                        ▼                                              │
│               5-Min Alert Clustering → MITRE ATT&CK Mapping Engine                    │
│                                        │                                              │
│                                        ▼                                              │
│               Claude Sonnet LLM Triage Client (Pydantic Structured Output)            │
│                                        │                                              │
│                                        ▼                                              │
│          Incident Service → Cryptographic Hash-Chained Audit Ledger → Redis Pub/Sub  │
│                                        │                                              │
│                                        ▼                                              │
│   Artifact Generators: Markdown Executive Report · Mermaid Attack Graph · Playbooks   │
├───────────────────────────────────────────────────────────────────────────────────────┤
│                                 API & BFF LAYER                                       │
│  FastAPI (:8000) REST & WebSocket (/ws/alerts) · Vercel Serverless BFF & Edge Gate   │
├───────────────────────────────────────────────────────────────────────────────────────┤
│                             FRONTEND DASHBOARD (Vercel)                               │
│  Alert Queue · Incident Detail (5 Tabs) · ATT&CK Navigator · Ops Metrics · RBAC Gate  │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

---

### **Day 1 — Architecture Lock, Ingestion Pipeline, Synthetic Data & App Shell**

#### Core Accomplishments:
- **Architecture Lock & Contracts:**
  - Standardized unified Pydantic data schemas in `backend/models.py` (`NormalizedEvent`, `EventInfo`, `SourceInfo`, `DestinationInfo`, `HostInfo`, `LogInfo`, `UserSummary`).
  - Implemented deterministic SHA-256 event fingerprinting (`compute_chain_hash()`) to guarantee log integrity.
  - Established monorepo structure (`/backend`, `/frontend`, `/infra`, `/data`, `/docs`).
- **Source Normalizers (`backend/ingestion/normalizers/`):**
  - `syslog_normalizer.py`: RFC5424/RFC3164 parser with process identification and SSH pattern extraction.
  - `cloudtrail_normalizer.py`: AWS JSON event parser extracting IAM identities and API actions.
  - `auth_log_normalizer.py`: Linux PAM and SSH authentication log parser.
  - `cicids_normalizer.py`: Network flow CSV record normalizer.
  - `normalizers/__init__.py`: Central registry with `get_normalizer()` and defensive fallbacks.
- **Synthetic Attack Scenario Generators (`backend/ingestion/generators/`):**
  - `auth_log_generator.py`: Multi-stage SSH brute-force attacks, privilege escalation via `sudo /etc/shadow`, and lateral movement via `svc-backup`.
  - `cloudtrail_generator.py`: AWS console brute-force, IAM privilege escalation (`AdministratorAccess`), and S3 bucket mass exfiltration.
- **Frontend App Shell:**
  - Initialized Vite + React 18 + TypeScript environment with custom design tokens, dark/light mode toggle, and Lucide icons.
  - Built main application layout (`AppShell.tsx`, `Sidebar.tsx`, `TopBar.tsx`) with routing for all 6 core views.
- **Infrastructure Stack (`docker-compose.yml`):**
  - Standalone Redpanda (7 topics: `raw.syslog`, `raw.cloudtrail`, `raw.auth`, `raw.cicids`, `normalized.events`, `alerts.raw`, `incidents.updates`).
  - Redis, PostgreSQL/TimescaleDB, and MLflow tracking server.
  - Faust stream consumer skeleton and replay producer utility.
- **Verification:** `verify_day1.py` and `test_normalizers.py` passed with 100% success.

---

### **Day 2 — Behavioral Feature Store, ML Model Ensemble Training & Alert Queue UI**

#### Core Accomplishments:
- **Sliding-Window Feature Engineering (`backend/ml/feature_engineering.py`):**
  - Implemented 9 numerical features: `event_count_1m`, `event_count_5m`, `event_count_1h`, `failed_auth_ratio`, `distinct_dest_ports`, `dest_ip_fanout`, `bytes_transferred`, `tod_zscore`, `geo_velocity_kmh`.
  - Built async Redis pipeline queries utilizing sorted sets (`ZCOUNT`), HyperLogLog (`PFCOUNT`), and atomic counters.
- **ML Ensemble Model Training (`backend/ml/train.py`):**
  - **Isolation Forest:** 200 trees, sub-sampling on benign traffic baselines.
  - **PyTorch Autoencoder (`autoencoder.py`):** Symmetric deep network ($9 \to 32 \to 16 \to 8 \to 16 \to 32 \to 9$) trained on reconstruction error.
  - **Ensemble Calibration:** $\text{Score} = 0.6 \cdot S_{\text{IF}} + 0.4 \cdot S_{\text{AE}}$.
  - **Threshold Decision:** Documented in `THRESHOLD_DECISION.md` (threshold = 0.40, yielding 96.4% recall and 80.0% precision).
  - **MLflow Registry:** Registered production models via `register_models.py`.
- **Model Scoring Microservice:**
  - Internal FastAPI scoring service on port 8001 with feature attribution extraction.
  - Connected Faust streaming worker to scoring API and routed anomalies to `alerts.raw`.
- **Interactive Alert Queue Page (`AlertQueue.tsx`):**
  - TanStack Table with 7 columns, severity badges, sparkline anomaly scores, multi-field filtering, search, and bulk operations.

---

### **Day 3 — MITRE ATT&CK Engine, Claude Sonnet LLM Triage, Vercel BFF & Live WebSocket**

#### Core Accomplishments:
- **MITRE ATT&CK Mapping Engine (`backend/mitre/mapping_engine.py`):**
  - Integrated official STIX 2.0 Enterprise ATT&CK v15.1 corpus with automated technique extraction and tactic kill-chain resolution.
- **Heuristic Detection Rules (`backend/mitre/rules.yaml`):**
  - 15+ rules mapping anomalous behavior to MITRE techniques (T1110.001 Brute Force, T1046 Port Scan, T1498 DDoS, T1021.001/004 Lateral Movement, T1548.001/003 PrivEsc, T1041 Exfiltration, T1078 Impossible Travel, T1059 Scripting, T1055 Process Injection).
- **Alert Clustering (`backend/mitre/alert_clustering.py`):**
  - Grouped alerts across 5-minute windows by `(entity_key, technique_category)`, reducing LLM calls by ~5×.
- **Claude Sonnet LLM Triage Client (`backend/llm/triage_client.py`):**
  - Enforced Pydantic `TriageResult` schema with system prompt guardrails, 3-attempt exponential backoff retry logic, and latency/cost tracking.
- **Incident Correlation & State Machine (`backend/api/incident_service.py`):**
  - Aggregated alerts into stateful incidents, executed MITRE + LLM triage, maintained hash-chained ledger, and triggered Redis Pub/Sub events.
- **Real-Time Streaming & BFF Layer:**
  - FastAPI `/ws/alerts` WebSocket endpoint backed by Redis Pub/Sub.
  - Vercel Serverless BFF (`/frontend/api/*`) and Edge Middleware (`frontend/middleware.ts`) for JWT verification and rate limiting.
  - Frontend live feed with animated row entry and connection health indicator.
- **Role-Based Mock Auth:**
  - Login view (`Login.tsx`) supporting Analyst, Senior Analyst, and Approver personas.

---

### **Day 4 — Incident Investigation, Attack Graphs, Containment Playbooks & Enterprise RBAC**

#### Core Accomplishments:
- **Dynamic Artifact Generation Engine (`backend/artifacts/`):**
  - `report_generator.py`: Jinja2 Markdown incident reports with executive summaries, chronological event timelines, entity tables, and sanitized raw log evidence.
  - `attack_graph.py`: Dynamic Mermaid LR topology generator rendering visual attack paths with role-based node color coding.
  - `playbook_renderer.py`: Jinja2 Ansible playbook generator rendering production containment automation across 5 threat classes (`brute_force`, `ddos_mitigation`, `lateral_movement`, `privesc_account_suspend`, `data_exfil_egress_block`, `generic_block`).
  - `sanitizers.py`: Strict defense-in-depth sanitizers preventing log injection, XSS, and template manipulation.
- **Comprehensive Incident Detail Page (`IncidentDetail.tsx`):**
  - 5 interactive tabs: Overview (Markdown), Attack Graph (Mermaid), MITRE Detail (STIX references), Containment Playbook (YAML syntax highlighted), and Audit Trail (hash-chained ledger).
- **Enterprise RBAC Enforcement:**
  - Client-side `<RoleGate>` restricting playbook approval to Approvers.
  - Server-side FastAPI `require_role("approver")` rejecting unauthorized approval requests with `403 Forbidden`.
- **Remaining Dashboard Views:**
  - MITRE Navigator (`Navigator.tsx`) with dynamic `layer.json`.
  - Ops Metrics (`OpsMetrics.tsx`) with 5 Recharts visualizations (throughput, volume, score distribution, LLM telemetry).
  - Playbook Library (`PlaybookLibrary.tsx`) and Settings (`Settings.tsx`).
- **Kubernetes Helm Charts (`infra/helm/`):**
  - Authored manifests for `faust-worker`, `scoring-api`, and `incident-api` with HPAs and probes.

---

### **Day 5 — Hardening, Load Testing, Chaos Resilience & Scaling Roadmap**

#### Core Accomplishments:
- **Security Self-Review & Defense-in-Depth:**
  - Zero secrets in git history (gitleaks verified); runtime secrets strictly in `.env` / Vercel env vars.
  - Input sanitization verified on all log-to-artifact render paths.
  - Prompt injection protection: LLM receives only structured, validated Pydantic models.
  - Multi-layer RBAC verified (Analyst token $\to$ 403 on approval, forged/expired token $\to$ 401).
- **Load Testing & Bottleneck Identification:**
  - Simulated high-throughput traffic at 1×, 5×, and 20× peak load.
  - Baseline p50: 45ms, p95: 120ms (0% error rate); 20× peak p50: 145ms, p95: 720ms (1.1% error rate).
  - Bottleneck identified: LLM API concurrency; documented mitigation via async queue batching and tiered model routing.
- **Chaos Engineering & Resilience:**
  - Verified graceful fallback to `triage_pending` status during broker/LLM outages without event loss.
  - Frontend exponential backoff reconnection (1s $\to$ 30s cap) tested under service restarts.
- **Production Scaling Roadmap (`docs/SCALING_PATH.md`):**
  - Stage 1: Faust $\to$ Apache Flink, VM $\to$ Managed K8s (EKS/GKE), HashiCorp Vault.
  - Stage 2: Anthropic Batch API (50% cost reduction), Tiered LLM routing (Haiku $\to$ Sonnet), open-weights model fine-tuning (Llama-3 8B).
  - Stage 3: Dedicated API Gateway, cross-browser Playwright matrix, SIEM/SOAR connectors (Splunk, PagerDuty, ServiceNow).
- **Testing & QA:**
  - 101 automated pytest unit and integration tests passing cleanly.

---

## 3. System Evaluation Scorecard

| Evaluation Dimension | Sprint Target | Achieved Result | Status | Verification Source |
| :--- | :--- | :--- | :--- | :--- |
| **Anomaly Detection Recall** | $\ge 90.0\%$ | **96.4%** | ✅ Exceeded | `docs/EVAL_RESULTS.md` |
| **Anomaly Detection Precision** | $\ge 75.0\%$ | **80.0%** | ✅ Exceeded | `docs/EVAL_RESULTS.md` |
| **F1-Score** | $\ge 80.0\%$ | **87.4%** | ✅ Exceeded | `docs/EVAL_RESULTS.md` |
| **ROC-AUC Score** | $\ge 0.950$ | **0.995** | ✅ Exceeded | `docs/EVAL_RESULTS.md` |
| **MITRE Tactic Accuracy** | $\ge 80.0\%$ | **87.0%** (Spot-check) | ✅ Exceeded | `docs/EVAL_RESULTS.md` |
| **LLM Cost per 1k Flagged** | $< \$0.50$ | **$0.18** | ✅ Exceeded | `docs/EVAL_RESULTS.md` |
| **Pipeline Latency (p50)** | $< 3,000\text{ ms}$ | **1,847 ms** | ✅ Exceeded | `docs/EVAL_RESULTS.md` |
| **Multi-Layer RBAC Gate** | 100% Enforced | **Verified (403 on API & UI)** | ✅ Verified | `backend/tests/test_rbac.py` |
| **Cryptographic Audit Chain** | Deterministic SHA-256 | **Verified Chain Integrity** | ✅ Verified | `backend/tests/test_incident_service.py` |
| **Automated Backend Tests** | 100% Passing | **101 Passed / 0 Failed** | ✅ Verified | `pytest backend/tests/` |

---

## 4. Repository Structure & Artifact References

```
soc-triager/
├── backend/
│   ├── api/                    # FastAPI app + routers + auth middleware
│   │   ├── main.py
│   │   ├── auth_middleware.py
│   │   ├── incident_service.py
│   │   └── routers/            # auth, alerts, incidents, websocket
│   ├── artifacts/              # Report/graph/playbook generators + sanitizers
│   ├── ingestion/              # Normalizers (Syslog, CloudTrail, auth.log, CICIDS)
│   ├── llm/                    # Claude Sonnet triage client
│   ├── mitre/                  # MITRE ATT&CK mapping engine + rules.yaml
│   ├── ml/                     # Isolation Forest, Autoencoder, feature eng., evaluate.py
│   ├── stream/                 # Faust agent skeleton
│   └── tests/                  # 101 tests (normalizers, clustering, incidents, RBAC, LLM)
├── frontend/
│   ├── src/
│   │   ├── pages/              # AlertQueue, IncidentDetail (5 tabs), Navigator, Ops, Playbooks, Settings
│   │   ├── components/ui/      # AlertTable, AttackGraph, MarkdownReport, LedgerEntry, RoleGate, MetricCard
│   │   ├── hooks/              # useAuth, useAlertsFeed (WS + exponential backoff)
│   │   └── stores/             # authStore, alertStore, uiStore (Zustand)
│   ├── api/                    # Vercel BFF serverless functions
│   └── middleware.ts            # Vercel Edge JWT validation
├── infra/
│   └── helm/                   # Kubernetes Helm chart skeletons
├── docs/
│   ├── DAY_1_TO_5_REPORT.md    # Complete 5-day engineering report
│   ├── EVAL_RESULTS.md         # Precision/Recall/F1, LLM cost, load test
│   └── SCALING_PATH.md         # Production scaling roadmap
└── README.md
```
