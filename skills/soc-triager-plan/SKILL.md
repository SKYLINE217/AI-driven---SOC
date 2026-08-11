---
name: soc-triager-plan
description: Use this skill whenever the user is working on the "SOC Triager" project (an AI-driven Security Operations Center incident triage + MITRE ATT&CK mapping platform) and asks about the overall sprint plan, timeline, day-by-day goals, team roles, acceptance criteria, non-goals, or the post-sprint roadmap. Trigger this any time the user mentions "SOC Triager", "5-day sprint", "Engineer A / Engineer B", asks "what should I be doing today", asks for the schedule/plan, or asks whether something is in scope for the MVP. Always consult this skill before answering scope, timeline, or ownership questions about SOC Triager — do not guess at the schedule from memory.
---

# SOC Triager — Master Sprint Plan

## What this project is

An **AI-driven SOC (Security Operations Center) Triager & MITRE ATT&CK Incident Manager**: a pipeline that ingests security logs as a live stream, runs ML anomaly detection, uses an LLM (Claude) for contextual triage, maps findings to MITRE ATT&CK techniques, auto-generates incident artifacts (reports, attack graphs, draft containment playbooks), and surfaces everything in a real-time React dashboard deployed on Vercel.

```
[Log Sources] → [Ingestion/Streaming] → [Normalization & Enrichment]
  → [ML Anomaly Detection] → [LLM Contextual Triage] → [MITRE ATT&CK Mapping]
  → [Incident Correlation & Case Mgmt] → [Artifact Generator]
  → [BFF / API Gateway] → [React SOC Dashboard on Vercel]
```

**Team:** 2 engineers, 5 working days, ~8-9 focused hours/day/engineer (~85 person-hours total).
**Target:** A working, demo-able, publicly reachable MVP on a real Vercel URL, following enterprise SOC architecture patterns, that is safe to pitch to a security engineering org as a pilot proposal.

## Two-tier architecture — why the split exists

Vercel's serverless/edge runtime **cannot** host long-running stateful processes (Kafka-compatible streaming, ML model serving, persistent Postgres connections). So:

1. **Backend tier** — Docker Compose on a normal VM (Railway / Fly.io / EC2-class). Owns: Redpanda (streaming), Faust (stream processing), ML scoring, LLM triage, MITRE mapping, Postgres/TimescaleDB, Redis, MLflow.
2. **Frontend + BFF tier** — React (Vite) SPA + thin Vercel Serverless/Edge Function layer that proxies, caches, and auth-gates calls to the backend. Deploys continuously to **Vercel** (preview URL per PR, instant rollback, real production URL).

The backend is **never** deployed to Vercel — this is a deliberate architectural decision, not an oversight.

## Non-negotiable engineering principles

1. **Streaming-first, not batch-first** — consume logs as an unbounded stream (Redpanda/Kafka-API), never just read CSVs in a notebook.
2. **Explainability** — every anomaly score and MITRE mapping carries a human-readable justification (feature attribution + LLM rationale).
3. **Human-in-the-loop by default** — containment scripts are **drafted, never auto-executed**. This is a hard product/safety boundary — state it explicitly in the demo, it builds credibility.
4. **Auditability** — every pipeline stage writes immutable, timestamped, hash-chained records (append-only incident ledger).
5. **Model + data versioning from day one** (MLflow).
6. **Continuous deployment from day one** — the React app deploys to Vercel on the very first commit, even as a "hello dashboard" shell.

## Team roles & ownership

| | **Engineer A — ML/Data/Backend Lead** | **Engineer B — Frontend/Platform/DevOps Lead** |
|---|---|---|
| Owns | Log parsing/normalization, streaming pipeline logic, feature engineering, Isolation Forest + Autoencoder models, LLM triage prompt engineering, MITRE mapping logic, evaluation report | React dashboard (all pages/components), BFF/API gateway, auth + RBAC, Vercel project setup & CI/CD, backend infra (Docker Compose, VM hosting, Postgres/Redis/Redpanda ops), testing infra (unit + E2E) |
| Supports | Reviews API contracts against dashboard needs; sanity-checks analyst-facing UI copy | Wires feature-store/API integration points; reviews model output shapes for UI/latency fit |

**Daily rhythm (both engineers):** 09:00 standup (15 min) · 13:00 integration checkpoint (20 min) · 17:30 end-of-day demo + Vercel deploy verification (15 min).

**Shared responsibilities:** architecture lock (Day 1 AM), ECS event schema, MITRE schema, security review of containment templates, Vercel environment variable/secrets policy, final demo script (Day 5).

For the full hour-by-hour breakdown of what each engineer does, see the companion skills `soc-triager-engineer-a-playbook` and `soc-triager-engineer-b-playbook`. This skill covers only the shared, whole-project view.

## Day-by-day milestones (shared view)

| Day | Theme | End-of-day bar |
|---|---|---|
| **1** | Architecture lock, ingestion, app shell, infra stand-up | App shell live on Vercel Production URL; Docker Compose backend running with all topics/DB created; normalizers unit-tested |
| **2** | Feature engineering, ML training, Scoring API, Alert Queue UI (mock data) | Isolation Forest trained and registered in MLflow; Scoring API live; Alert Queue renders mock/live data |
| **3** | MITRE mapping, LLM triage client, BFF, WebSocket live feed | LLM triage client working with retries + schema validation; BFF deployed; Alert Queue receives live WebSocket rows |
| **4** | Artifact generation, evaluation report, Incident Detail + all pages, RBAC | Full incident lifecycle demo-able end-to-end: raw log → downloadable containment playbook, role-gated approval verified in UI and via direct API call; `EVAL_RESULTS.md` has real numbers |
| **5** | Hardening, load test, security review, production deploy, demo rehearsal | Stable, documented, load-tested, security-reviewed MVP live on public Vercel Production URL; rehearsed 10-minute demo; full scaling/production path written |

## Repository structure

```
soc-triager/
├── frontend/          # React + Vite app — Vercel root (pages/, components/, hooks/, lib/, styles/, api/ [BFF], middleware.ts, tests/, e2e/)
├── backend/           # docker-compose.yml, ingestion/, stream/, ml/, mitre/, llm/, api/, artifacts/, tests/
├── infra/helm/        # K8s manifest skeletons (not deployed in sprint)
├── data/              # cicids2017/, elastic_samples/, synthetic_cloudtrail/, synthetic_auth_log/, mitre/enterprise-attack-v15.1.json
├── docs/              # ARCHITECTURE.md, EVAL_RESULTS.md, SCALING_PATH.md, THREAT_MODEL.md
├── .github/workflows/ci.yml
└── README.md
```

## Acceptance criteria & success metrics

| Metric | Target |
|---|---|
| Anomaly detection recall | ≥ 0.90 on held-out CICIDS2017 attack windows |
| Anomaly detection precision | ≥ 0.75 |
| MITRE technique mapping accuracy | ≥ 85% correct at tactic level (manual spot-check) |
| End-to-end latency (log → incident visible in live UI) | < 5 s at 1× real-time; p95 documented at 20× load |
| LLM cost per 1,000 flagged anomalies | Documented, extrapolated to enterprise volume |
| System resilience | Zero silent event loss on broker/LLM outage; graceful degraded state visible in UI |
| Auditability | Every incident traceable via hash-chained ledger |
| RBAC enforcement | "Approve for Ops" unreachable/disabled for non-Approver in UI **and** via direct API call |
| Deployment | Production Vercel URL live, matches last-reviewed Preview build |
| Test coverage | Backend pytest + frontend Vitest/RTL passing in CI; ≥ 1 E2E Playwright suite covering full incident lifecycle against a live Preview URL |

## Explicit non-goals for this sprint

State these in the demo — it builds credibility, it shows deliberate scoping rather than missing features:

- **No auto-execution of containment actions** — every playbook is a reviewed, downloadable artifact requiring human approval.
- **No production secrets management (Vault)** — Vercel env vars + `.env` cover the sprint; Vault is the documented next step.
- **No multi-tenant isolation** — single-org assumption; documented Phase 2 item.
- **No live cloud API integration** — synthetic CloudTrail-format data used; a real `boto3` poller is a bounded follow-on task.
- **No Flink/Kubernetes deployment executed** — both architected and manifest/skeleton-ready, not spent on cluster ops.
- **Backend not deployed on Vercel** — deliberate; documented in `SCALING_PATH.md`.

## Post-sprint roadmap (Phase 2 preview)

In priority order: (1) real cloud-native log source integrations (CloudTrail/EventBridge, Azure Activity Log, GCP Audit Log); (2) migrate stream processor to Flink for sustained high-throughput; (3) analyst feedback loop that retrains IF/autoencoder thresholds and refines MITRE heuristics (active learning); (4) SOAR-style playbook auto-execution behind a formal change-approval workflow with rollback, once human-in-the-loop track record justifies it; (5) SSO/OIDC, Vault-backed secrets, multi-tenant isolation, dedicated API gateway if Vercel serverless limits are outgrown.

## When answering questions with this skill

- If asked "what day are we on / what should I do next", cross-reference the day-by-day table above and point to the matching section in `soc-triager-engineer-a-playbook` or `soc-triager-engineer-b-playbook`.
- If asked "is X in scope", check the non-goals list first.
- If asked about a specific technical subsystem (e.g. "how does the LLM triage prompt work", "what's the JWT payload"), defer to the more specific companion skills (`soc-triager-backend`, `soc-triager-security`, `soc-triager-api-reference`, etc.) rather than guessing — this skill is the project-level index, not the implementation detail.
