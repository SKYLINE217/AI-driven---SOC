# SOC Triager — Backend Architecture & Implementation Guide

> **Owner:** Engineer A (ML/Data/Pipeline), Engineer B (Platform/Infrastructure)
> **Scope:** All services running in Docker Compose on the backend VM — streaming pipeline, ML serving, FastAPI, Postgres, Redis, Redpanda, Prometheus, MLflow.

---

## 1. Architecture Overview

The backend is a **multi-service, streaming-first pipeline** that processes log events as an unbounded stream from ingestion through ML scoring, LLM triage, MITRE mapping, incident management, and artifact generation.

```
[Log Replay Producer]
        │ Kafka Producer API
        ▼
[Redpanda — Kafka-API Streaming Bus]
        │ Faust Consumer
        ▼
[Stream Processor — Faust]
  parse → normalize (ECS) → enrich (GeoIP/ASN)
        │
        ├── writes → TimescaleDB (normalized_events)
        ▼
[Feature Store Writer — Faust Agent]
  windowed feature computation
        │
        ├── hot features → Redis (sorted sets, sliding windows)
        └── cold features → TimescaleDB (feature_snapshots)
                │
                ▼
[ML Scoring Service — FastAPI /score]
  Isolation Forest + Autoencoder ensemble
        │ if score > threshold
        ▼
[LLM Triage + MITRE Mapping Module]
  Claude Sonnet → structured JSON output
        │
        ▼
[Incident Correlation Service — FastAPI]
  cluster alerts → create/update incidents → hash-chain ledger
        │
        ▼
[Artifact Generation Service]
  Markdown report, Mermaid graph, Ansible playbook (draft)
        │
        ▼
[FastAPI REST + WebSocket Gateway]  ←── BFF on Vercel proxies to here
```

---

## 2. Service Inventory

### 2.1 Docker Compose Services

```yaml
services:
  redpanda:           # Kafka-API streaming bus, single-binary
  redis:              # Hot feature store, WebSocket fan-out pub/sub
  postgres:           # TimescaleDB — event store, feature cold store, incident DB
  mlflow:             # Experiment tracking (SQLite backend, /mlruns volume)
  fluent-bit:         # Log shipper (optional; Python replay producer used in sprint)
  faust-worker:       # Stream processing: normalize, enrich, feature compute
  scoring-api:        # FastAPI /score endpoint, ML model serving
  incident-api:       # FastAPI — incidents, alerts, artifacts, WebSocket
  artifact-worker:    # Async worker for report/graph/playbook generation
  prometheus:         # Metrics scraping
  grafana:            # Ops dashboard (internal; frontend uses /api/metrics BFF)
```

### 2.2 Port Map

| Service | Internal Port | External (VM) |
|---|---|---|
| Redpanda | 9092 (Kafka), 9644 (Admin) | 9092, 9644 |
| Redis | 6379 | 6379 (bind 127.0.0.1 in production) |
| Postgres/TimescaleDB | 5432 | 5432 (bind 127.0.0.1) |
| MLflow UI | 5000 | 5000 |
| Scoring API | 8001 | 8001 |
| Incident API | 8000 | 8000 (HTTPS via reverse proxy) |
| Prometheus | 9090 | 9090 (bind 127.0.0.1) |
| Grafana | 3001 | 3001 |

The **Incident API (8000)** is the only port exposed externally over HTTPS. A reverse proxy (Caddy or Nginx) handles TLS termination.

---

## 3. Streaming Bus — Redpanda

### 3.1 Topics

| Topic | Partitions | Retention | Publisher | Consumer |
|---|---|---|---|---|
| `raw.syslog` | 4 | 24 h | Replay producer / Fluent Bit | Faust worker |
| `raw.cloudtrail` | 4 | 24 h | Replay producer | Faust worker |
| `raw.auth` | 4 | 24 h | Replay producer | Faust worker |
| `raw.cicids` | 4 | 24 h | Replay producer | Faust worker |
| `normalized.events` | 8 | 7 d | Faust worker | Feature store agent, TimescaleDB sink |
| `alerts.raw` | 4 | 7 d | Scoring service (via Faust) | Incident correlation service |
| `incidents.updates` | 2 | 7 d | Incident API | WebSocket fan-out worker |

### 3.2 Consumer Group Design

- `faust-normalizer-cg` — consumes all `raw.*` topics; stateless, scale horizontally
- `faust-feature-cg` — consumes `normalized.events`; stateful (windowed aggregations), one partition = one agent instance
- `alert-consumer-cg` — consumes `alerts.raw`; incident correlation service

### 3.3 Replay Producer

Located at `backend/ingestion/replay_producer.py`. Streams CICIDS2017 CSVs and synthetic log files into the appropriate raw topics at a configurable replay speed:

```python
python replay_producer.py \
  --source cicids2017 \
  --file data/cicids2017/Wednesday-workingHours.pcap.IANA_labels.csv \
  --speed 10  # 10× real-time
```

The producer injects controlled attack patterns (brute force at T+300s, lateral movement at T+600s) into synthetic auth.log streams for deterministic demo scenarios.

---

## 4. Stream Processor — Faust

### 4.1 File: `backend/stream/faust_app.py`

**Key agents:**

```python
@app.agent(raw_syslog_topic)
async def process_syslog(stream):
    async for raw_event in stream:
        ecs = normalize_syslog(raw_event)
        ecs = await enrich_geoip(ecs)
        await normalized_events_topic.send(value=ecs)
        await db.insert_normalized_event(ecs)

@app.agent(normalized_events_topic)
async def compute_features(stream):
    async for event in stream:
        features = await feature_store.compute_windowed_features(event)
        score_response = await scoring_client.score(features)
        if score_response.score > THRESHOLD:
            alert = build_alert(event, score_response)
            await alerts_raw_topic.send(value=alert)
```

### 4.2 Normalizers

One normalizer function per source type, all in `backend/ingestion/normalizers/`:

- `syslog_normalizer.py` — parses RFC5424 syslog into ECS
- `cloudtrail_normalizer.py` — maps AWS CloudTrail JSON fields to ECS
- `auth_log_normalizer.py` — parses Linux `/var/log/auth.log` format
- `cicids_normalizer.py` — maps CICIDS2017 CSV columns to ECS flow events

All normalizers are unit-tested in `backend/tests/test_normalizers.py` with sample lines from each source type.

### 4.3 GeoIP / ASN Enrichment

Uses the MaxMind GeoLite2 City and ASN databases (downloaded on container startup via `geoipupdate`):

```python
from geoip2.database import Reader

geo_reader = Reader('/data/GeoLite2-City.mmdb')
asn_reader = Reader('/data/GeoLite2-ASN.mmdb')

def enrich_geoip(event: ECSEvent) -> ECSEvent:
    try:
        geo = geo_reader.city(event.source.ip)
        event.source.geo.country_iso_code = geo.country.iso_code
        asn = asn_reader.asn(event.source.ip)
        event.source.as_.number = asn.autonomous_system_number
    except Exception:
        pass  # enrichment is best-effort, never blocks the pipeline
    return event
```

---

## 5. Feature Store

### 5.1 Hot Features — Redis

Sliding window aggregations stored as Redis sorted sets and hashes, keyed by `entity_key = f"{host}:{user}:{source_ip}"`.

| Feature Name | Redis Structure | Window | TTL |
|---|---|---|---|
| `event_count_1m` | ZADD (event_ts, event_id) | 1 min | 10 min |
| `event_count_5m` | ZADD | 5 min | 30 min |
| `event_count_1h` | ZADD | 1 h | 2 h |
| `failed_auth_ratio` | HSET (fail_count, total_count) | 5 min | 30 min |
| `distinct_dest_ports` | PFADD (HyperLogLog) | 5 min | 30 min |
| `dest_ip_fanout` | PFADD | 5 min | 30 min |
| `bytes_transferred` | INCRBY | 5 min | 30 min |

`feature_store.compute_windowed_features(event)` reads these keys and returns a `FeatureVector` Pydantic model.

### 5.2 Cold Features — TimescaleDB

`feature_snapshots` hypertable: `(entity_key, window_end_ts, feature_json)`. Partitioned by time (1-week chunks). Used by the autoencoder for training on historical baseline.

---

## 6. ML Scoring Service

### 6.1 File: `backend/ml/scoring_service.py` (served as FastAPI)

**Endpoint:** `POST /score`

```python
class ScoreRequest(BaseModel):
    entity_key: str
    features: FeatureVector
    event_id: str

class ScoreResponse(BaseModel):
    score: float               # 0.0–1.0, higher = more anomalous
    threshold: float
    is_anomaly: bool
    top_features: list[FeatureContribution]  # top-3 contributing features
    model_version: str
    latency_ms: float
```

**Ensemble logic:**

```python
def ensemble_score(feature_vector: FeatureVector) -> float:
    if_score = isolation_forest.score_samples([feature_vector.to_array()])[0]
    if_normalized = normalize_if_score(if_score)  # -1..0 → 0..1

    ae_input = torch.tensor(feature_vector.to_array(), dtype=torch.float32)
    ae_recon = autoencoder(ae_input)
    ae_error = F.mse_loss(ae_recon, ae_input).item()
    ae_normalized = reconstruction_error_to_percentile(ae_error)

    return 0.6 * if_normalized + 0.4 * ae_normalized
```

### 6.2 Models

Both models are registered in **MLflow** and loaded by version tag (e.g., `models:/isolation_forest/production`):

- `IsolationForest`: `n_estimators=200`, `contamination='auto'`, trained on CICIDS2017 benign traffic + synthetic normal baseline
- `Autoencoder`: 3-layer symmetric bottleneck (`input → 32 → 16 → 8 → 16 → 32 → input`), trained on normal-only feature snapshots, reconstruction error = anomaly signal

### 6.3 Threshold Decision

Threshold is **not hardcoded** — loaded from `backend/ml/THRESHOLD_DECISION.md` and the corresponding MLflow metric artifact. Target: **recall ≥ 0.90 at precision ≥ 0.75** on held-out CICIDS2017 attack days.

---

## 7. LLM Triage Client

### 7.1 File: `backend/llm/triage_client.py`

Uses the Anthropic Python SDK with `claude-sonnet-4-6` and structured output (tool use / forced schema):

```python
SYSTEM_PROMPT = """
You are a SOC analyst assistant. You will receive:
1. A normalized security event or cluster of related events
2. An anomaly score with top contributing features
3. A shortlist of candidate MITRE ATT&CK technique IDs

Your response MUST:
- Select ONE technique ID from the provided candidate list only. Never invent IDs.
- Not fabricate IOCs, CVE numbers, or asset names not present in the input.
- Phrase containment recommendations as drafts for analyst approval, never as executed actions.
- Return ONLY valid JSON matching the provided schema.
"""

RESPONSE_SCHEMA = {
    "technique_id": "string (from candidate list)",
    "technique_name": "string",
    "tactic": "string",
    "confidence": "float 0.0–1.0",
    "rationale": "string (analyst-readable, ≤200 words)",
    "severity": "critical|high|medium|low",
    "recommended_immediate_action": "string (draft phrasing)"
}
```

**Retry logic:** max 2 retries with exponential backoff on schema validation failure. After 2 failures, the alert is stored with `triage_status: "pending_manual"`.

**Batching:** alerts within the same `(source_ip, technique_category, 5-min window)` cluster are sent as a single LLM call with up to 30 representative events. This reduces LLM call volume by ~10× in real attack scenarios.

### 7.2 Cost Tracking

Every call logs to `llm_call_log` Postgres table:

```sql
CREATE TABLE llm_call_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    called_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    model TEXT NOT NULL,
    input_tokens INT NOT NULL,
    output_tokens INT NOT NULL,
    latency_ms INT NOT NULL,
    cluster_size INT NOT NULL,  -- how many alerts in this batch
    technique_result TEXT,
    cost_usd NUMERIC(10,6)
);
```

---

## 8. MITRE ATT&CK Mapping Engine

### 8.1 Corpus

`data/mitre/enterprise-attack-v15.1.json` — pinned STIX 2.1 bundle pulled from `https://github.com/mitre/cti`. Loaded at startup via `mitreattack.stix20.MitreAttackData`.

### 8.2 Two-Stage Mapping

**Stage 1 — Heuristic Candidate Generation** (`backend/mitre/rules.yaml`):

```yaml
rules:
  - name: brute_force_ssh
    conditions:
      event.action: ssh_login_failed
      event_count_1m: "> 10"
      distinct_users: "> 2"
    candidates: [T1110, T1110.001]

  - name: port_scan
    conditions:
      distinct_dest_ports_5m: "> 50"
      bytes_per_event: "< 200"
    candidates: [T1046]

  - name: lateral_movement_smb
    conditions:
      event.action: smb_connect
      dest_ip_fanout_5m: "> 5"
    candidates: [T1021.002]

  # ~15-20 total rules covering CICIDS2017 attack categories
```

**Stage 2 — LLM Re-ranking** (described in Section 7 above): LLM receives candidate list, returns the single best match with rationale.

### 8.3 Navigator Layer Export

`GET /api/navigator/layer.json` builds a MITRE ATT&CK Navigator-compatible layer:

```python
def build_navigator_layer(incidents: list[Incident]) -> dict:
    technique_counts = Counter(i.technique_id for i in incidents)
    return {
        "name": "SOC Triager — Current Week",
        "versions": {"attack": "15", "navigator": "5"},
        "domain": "enterprise-attack",
        "techniques": [
            {"techniqueID": tid, "score": count, "color": score_to_color(count)}
            for tid, count in technique_counts.items()
        ]
    }
```

---

## 9. Incident Correlation & Case Management

### 9.1 Correlation Logic

Alerts are clustered by `(source_ip, technique_id, 5-min window)`. If a matching open incident exists, the alert is appended. Otherwise, a new incident is created with an auto-generated title:

```python
def generate_incident_title(technique_name: str, target_host: str) -> str:
    tactic = lookup_tactic(technique_name)
    return f"{tactic} via {technique_name} — {target_host}"
    # e.g., "Credential Access via Brute Force: Password Guessing — prod-db-03"
```

### 9.2 Hash-Chained Ledger

`incident_ledger` is append-only. Each insert:

```python
def append_ledger_entry(incident_id, action, actor, payload):
    prev = db.query("SELECT hash FROM incident_ledger WHERE incident_id=$1 ORDER BY seq DESC LIMIT 1", incident_id)
    prev_hash = prev.hash if prev else "0" * 64
    entry_json = json.dumps({"action": action, "actor": actor, "payload": payload, "ts": utcnow()})
    new_hash = hashlib.sha256((prev_hash + entry_json).encode()).hexdigest()
    db.execute("INSERT INTO incident_ledger (...) VALUES (...)", new_hash, prev_hash, ...)
```

---

## 10. Artifact Generation Service

### 10.1 Markdown Incident Report (`backend/artifacts/report_generator.py`)

Uses a Jinja2 template (`templates/incident_report.md.j2`):

- Header: title, severity, technique, tactic, confidence, dates
- Timeline table: auto-generated from `incident.alerts` ordered by timestamp
- Entities section: all unique hosts, users, IPs with their roles (attacker/victim/pivot)
- Evidence section: up to 5 representative raw log lines (code-block formatted)
- MITRE section: technique description, LLM rationale
- Recommended actions: LLM output + template-driven standard SOP link

### 10.2 Mermaid Attack Graph (`backend/artifacts/attack_graph.py`)

Builds a Mermaid `graph LR` definition from incident entities and their interaction edges. Assigns colors by role. Returns the Mermaid source string (stored in the incident record and served via `GET /api/incidents/:id/graph.mmd`).

### 10.3 Containment Playbook (`backend/artifacts/playbook_templates/`)

Jinja2 templates, one per technique category:

- `brute_force.ansible.j2` — IP block + account lockout
- `lateral_movement.ansible.j2` — network segmentation ACL
- `ddos.ansible.j2` — rate limiting + null route
- `priv_esc.ansible.j2` — account suspend + session kill
- `exfil.ansible.j2` — egress firewall block

Template rendering populates variables from the incident's observed IOCs (source IPs, target hosts, ports). Output is stored in `incidents.playbook_draft` and never auto-executed.

---

## 11. Prometheus Metrics Exposed

Every service exposes `/metrics` (Prometheus text format):

| Metric | Service | Type | Labels |
|---|---|---|---|
| `events_ingested_total` | Faust worker | Counter | `source_type` |
| `events_normalized_total` | Faust worker | Counter | `source_type` |
| `alerts_generated_total` | Faust worker | Counter | `severity` |
| `anomaly_score_histogram` | Scoring API | Histogram | — |
| `scoring_latency_seconds` | Scoring API | Histogram | — |
| `llm_calls_total` | LLM client | Counter | `result` (success/retry/fail) |
| `llm_latency_seconds` | LLM client | Histogram | — |
| `llm_cost_usd_total` | LLM client | Counter | — |
| `incidents_created_total` | Incident API | Counter | `severity` |
| `pipeline_e2e_latency_seconds` | Incident API | Histogram | — |
| `websocket_connections_active` | Incident API | Gauge | — |

---

## 12. Observability

- **Structured logging** — all services use `structlog` with JSON output; every log line includes `service`, `trace_id`, `event_id` where applicable
- **Grafana** — dashboards for streaming throughput, ML score distribution, LLM cost/latency, incident creation rate
- **Alerting** — Prometheus `alertmanager` rules for: Faust consumer lag > 1000 events, LLM error rate > 10%, scoring latency p95 > 100 ms

---

## 13. Startup & Shutdown Sequence

```bash
# Start all services
docker compose up -d

# Health checks (automated in CI)
curl http://localhost:8000/health  # Incident API
curl http://localhost:8001/health  # Scoring API
rpk cluster info --brokers localhost:9092  # Redpanda

# Stop gracefully
docker compose down  # Faust agents flush in-flight messages before exit
```
