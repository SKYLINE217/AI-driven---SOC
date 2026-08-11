# SOC Triager — Scaling Path to Production

This document describes the production architecture decisions and migration path from the sprint MVP (VM + Vercel) to a production-grade, horizontally scalable platform.

---

## Current Architecture (Sprint MVP)

| Component | Technology | Scale |
|-----------|-----------|-------|
| Backend API | FastAPI on single VM | ~100 concurrent WS connections |
| Streaming | Faust + Redpanda (single node) | ~1,000 events/sec |
| ML Scoring | FastAPI :8001, in-process model | ~50 scores/sec |
| Storage | In-memory + PostgreSQL | <1M incidents |
| Frontend | Vercel (BFF + SPA) | Auto-scaled |
| Auth | HS256 JWT, in-memory session | Dev only |

---

## Stage 1 — Remove Single Points of Failure (3–6 months)

### Streaming: Faust → Apache Flink

**Why:** Faust is excellent for prototyping but single-machine. Flink provides:
- Stateful stream processing with exactly-once semantics
- Horizontal partition-level scaling (add Flink TaskManagers)
- Native Kafka/Redpanda integration with consumer group management
- Fault-tolerant checkpointing to S3/HDFS

**Migration path:**
1. Keep the same Redpanda topics (`raw.*`, `normalized.events`, `alerts.raw`)
2. Rewrite Faust agents as Flink `DataStream` jobs
3. Feature store stays Redis — Flink accesses it via async I/O operator
4. Run both in parallel during cutover; validate identical output

### Kubernetes (K8s) for all services

**Why:** Current single-VM deployment has no automatic failover or horizontal scaling.

**Plan:**
- Use Helm charts in `infra/helm/` (already created)
- Managed K8s: AWS EKS / GCP GKE / Azure AKS
- `incident-api`: 2–10 replicas, HPA on CPU 70%
- `scoring-api`: 2–8 replicas, HPA on CPU 75% (model loading is expensive — scale conservatively)
- `faust-worker` / Flink: one pod per Redpanda partition; HPA on consumer lag metric (custom metric via KEDA)
- Ingress: NGINX + cert-manager for auto-TLS; or AWS ALB + ACM

### Secrets: HashiCorp Vault

**Why:** `.env` and Vercel env vars work for a sprint; production needs secret rotation and audit.

**Plan:**
- Vault Agent sidecar: injects `ANTHROPIC_API_KEY`, `JWT_SECRET`, `POSTGRES_PASSWORD` at pod startup
- Dynamic Postgres credentials (15-min TTL, auto-rotated)
- Vault audit log → SIEM for every secret access
- `ANTHROPIC_API_KEY` in Vault KV v2 with access policy per service

---

## Stage 2 — LLM Cost Optimization (6–12 months)

### Current bottleneck

At 50M events/day with the full Sonnet model on every alert:
- ~$5,000–$20,000/day (depending on flagged rate and cluster size)
- LLM p95 latency (4.2s) is the pipeline bottleneck

### Mitigation strategies

| Strategy | Cost Reduction | Latency Impact |
|----------|---------------|----------------|
| **Anthropic Batch API** | ~50% | +2–6h (async) — acceptable for non-critical triage |
| **Tiered model routing** | ~70% | Haiku for low-confidence (<0.5), Sonnet for high-confidence |
| **Aggressive clustering** | ~80% | Group 20 events per cluster vs 5 — 4× fewer LLM calls |
| **Cache repeated patterns** | ~30% | Redis: hash(technique_id + entity_type) → cached rationale |
| **Fine-tuned open model** | ~95% | Replace Claude with a fine-tuned Llama 3 on historical triage data |

### Recommended path

Short term: Enable Batch API for `triage_pending` alerts (non-real-time queue).  
Medium term: Add Haiku → Sonnet cascade based on IF+AE confidence.  
Long term: Fine-tune an open model (Llama 3 8B or Mistral) on the incident rationale corpus.

---

## Stage 3 — Platform Graduation (12–18 months)

### Vercel → Dedicated API Gateway

**Why:** As load grows, Vercel function cold starts and 10s timeout limits become friction.

**Plan:**
- Move BFF logic to a long-running container (FastAPI or Next.js standalone) behind AWS ALB or Kong Gateway
- Keep Vercel for the SPA only (static assets, CDN)
- API Gateway adds: rate limiting (vs Upstash Redis), request transformation, canary deployments

### Playwright → Cross-Browser CI Matrix

**Current:** Playwright against Chromium only, local + Vercel Preview  
**Production:**
- Matrix: Chromium, Firefox, WebKit (Safari engine) on every PR
- Mobile viewport tests: 375px (iPhone SE), 768px (iPad)
- Visual regression: Percy or Playwright screenshots diff
- Run against staging environment (not Preview) with real backend

### Database: PostgreSQL → TimescaleDB at scale

TimescaleDB hypertables for time-series alert/incident data:
- Automatic partitioning by `created_at` (weekly chunks)
- Compression (90%+ on old chunks)
- `time_bucket()` aggregate queries for Ops Metrics panels
- Continuous aggregates for pre-computed dashboard metrics

### SIEM Integration

As the platform matures, integrate with:
- **Splunk / Elastic SIEM** — forward normalized events and incident summaries
- **PagerDuty / Opsgenie** — trigger pages on critical incidents
- **Jira / ServiceNow** — create tickets automatically on approved incidents

---

## Engineer B — Frontend/Platform Scaling Notes

- **Mermaid lazy loading:** already implemented via dynamic `import('mermaid')` — avoids ~500KB in the initial bundle
- **Bundle splitting:** add `build.rolldownOptions.output.codeSplitting` to split Recharts and react-markdown into separate chunks
- **CDN for ML artifacts:** store MITRE STIX corpus and MLflow model artifacts in S3 + CloudFront
- **WebSocket scaling:** current in-memory WS broadcast doesn't survive multi-pod deployment; migrate fan-out to Redis Pub/Sub or Kafka consumer group per pod

---

## Engineer A — Backend/ML Scaling Notes

- **Flink checkpointing:** use S3 state backend; checkpoint every 60s
- **Feature store:** migrate from Redis to Apache Flink's RocksDB state backend for stateful features at high throughput
- **Model serving:** migrate from MLflow `load_model()` at startup to Triton Inference Server for GPU acceleration + dynamic batching
- **MITRE corpus:** pin to a specific ATT&CK release; verify SHA-256 on startup; update quarterly
