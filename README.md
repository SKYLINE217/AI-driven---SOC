# SOC Triager — AI-Driven Security Operations Platform

> **Real MITRE ATT&CK mapping · Claude Sonnet LLM triage · ML anomaly detection · Fully auditable RBAC**

An end-to-end Security Operations Center automation system that ingests raw logs, detects anomalies with an Isolation Forest + Autoencoder ensemble, maps them to MITRE ATT&CK techniques with an LLM, creates incidents with hash-chained audit trails, and presents everything via a real-time React dashboard.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  INGESTION LAYER                                                     │
│  Syslog / CloudTrail / auth.log / CICIDS2017                        │
│       ↓                                                             │
│  Faust (Redpanda) → Normalizers → Feature Engineering (Redis)       │
│       ↓                                                             │
│  Scoring API (FastAPI :8001) — IF + AE Ensemble (MLflow)           │
│       ↓  (anomaly_score > threshold)                                │
│  MITRE Mapping Engine → LLM Triage Client (Claude Sonnet)          │
│       ↓                                                             │
│  Incident Service → Hash-Chained Ledger → WebSocket Fan-out        │
│       ↓                                                             │
│  Artifact Generation: Markdown Report · Mermaid Graph · Playbook   │
├─────────────────────────────────────────────────────────────────────┤
│  API LAYER  (FastAPI :8000)                                         │
│  JWT auth + RBAC · REST + WebSocket                                 │
├─────────────────────────────────────────────────────────────────────┤
│  FRONTEND  (Vite + React + TypeScript → Vercel)                    │
│  Alert Queue · Incident Detail (5 tabs) · Navigator · Ops · Library │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Quick Start — Local Development

### Prerequisites
- Python 3.11+, Node 18+, Docker & Docker Compose

### 1. Backend

```powershell
cd e:\SOC

# Create virtual environment
python -m venv backend\.venv
backend\.venv\Scripts\activate  # Windows

# Install dependencies
pip install -r backend/requirements.txt

# Copy and fill in secrets
cp backend/.env.example backend/.env
# Edit backend/.env: ANTHROPIC_API_KEY, JWT_SECRET, etc.

# Start the FastAPI server
python -m uvicorn backend.api.main:app --reload --port 8000
```

### 2. Frontend

```powershell
cd e:\SOC\frontend
npm install
npm run dev
# Opens at http://localhost:5173
```

### 3. Infrastructure (Docker Compose)

```bash
cd e:\SOC
docker compose up -d redpanda redis postgres mlflow

# Verify services
# MLflow UI: http://localhost:5000
# Redpanda Console: http://localhost:8080
```

---

## Running Tests

```powershell
# Full backend test suite (101 tests, ~2s)
cd e:\SOC
backend\.venv\Scripts\python -m pytest backend/tests/ -v

# Frontend TypeScript + Vite build check
cd frontend; npm run build

# Evaluation script (generates docs/EVAL_RESULTS.md)
backend\.venv\Scripts\python backend/ml/evaluate.py
```

---

## Project Structure

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
│   ├── EVAL_RESULTS.md         # Precision/Recall/F1, LLM cost, load test
│   └── SCALING_PATH.md         # Production scaling roadmap
└── plan/skills/                # Agent skill definitions (playbooks for this sprint)
```

---

## Key Design Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| ML model | IF + AE ensemble (0.6/0.4) | Complementary: IF for global outliers, AE for reconstruction anomalies |
| LLM | Claude Sonnet via Anthropic SDK | Best balance of reasoning quality and cost |
| Audit trail | Hash-chained ledger | Tamper-detectable without a blockchain |
| Auth | HS256 JWT, in-memory storage | Sprint scope; production → RS256 + HttpOnly cookies |
| WS reconnect | Exponential backoff (1s → 30s cap) | Resilient to transient network issues |
| Playbooks | Jinja2 with `sanitize_ansible_var()` | Security: all IOC variables validated before render |

---

## Security Controls

- **Authentication:** HS256 JWT (production: RS256 + Vault)
- **Authorization:** 3-layer RBAC — UI (`RoleGate`), BFF (Edge Middleware), FastAPI (`require_role()`)
- **Input validation:** All log content sanitized before Markdown/Mermaid/Ansible render
- **Prompt injection:** LLM receives only structured fields — never raw log content
- **Audit:** Append-only hash-chained ledger on every state change
- **Secrets:** Never in code — Vercel env vars + backend `.env` (gitignored)

---

## Evaluation Results

| Metric | Value | Target |
|--------|-------|--------|
| Precision | 80.0% | ≥ 75% ✅ |
| Recall | 96.4% | ≥ 90% ✅ |
| ROC-AUC | 0.995 | ≥ 0.95 ✅ |
| MITRE Tactic Accuracy | 87% | ≥ 80% ✅ |
| LLM Cost / 1k flagged | $0.18 | — |
| Pipeline p50 latency | 1850ms | — |

See [docs/EVAL_RESULTS.md](docs/EVAL_RESULTS.md) for the full report.

---

## Vercel Deployment

```bash
# Set environment variables in Vercel dashboard:
# BACKEND_API_URL = https://your-backend-vm:8000
# JWT_SECRET = <openssl rand -base64 32>

# Deploy from frontend/
cd frontend
npx vercel --prod
```

---

## License

MIT — see LICENSE file.
