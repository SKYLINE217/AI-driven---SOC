---
name: soc-triager-backend
description: Use this skill whenever the user is implementing, debugging, or asking about the SOC Triager backend — Docker Compose services, Redpanda topics, the Faust stream processor, the feature store (Redis + TimescaleDB), the ML Scoring Service, the LLM triage client, the MITRE ATT&CK mapping engine, incident correlation, the hash-chained ledger, artifact generation (reports/graphs/playbooks), Prometheus metrics, or backend startup/shutdown. Trigger this for any question involving `backend/`, FastAPI, Faust, Redpanda, Redis, TimescaleDB, MLflow, Isolation Forest, Autoencoder, or the `/score` endpoint. This is the implementation-level companion to `soc-triager-system-architecture` — use that skill for the high-level picture and this one for concrete file paths, code, and service configuration.
---

# SOC Triager — Backend Architecture & Implementation Guide

> Owned by: Engineer A (ML/data/pipeline pieces), Engineer B (platform/infra pieces). Runs entirely in Docker Compose on a backend VM — never on Vercel.

## Architecture overview

```
[Log Replay Producer] → [Redpanda] → [Stream Processor — Faust: parse → normalize (ECS) → enrich (GeoIP/ASN)]
   → writes → TimescaleDB (normalized_events)
   → [Feature Store Writer — Faust Agent] → Redis (hot) / TimescaleDB (cold)
   → [ML Scoring Service — FastAPI /score] Isolation Forest + Autoencoder ensemble
   → if score > threshold → [LLM Triage + MITRE Mapping] Claude Sonnet → structured JSON
   → [Incident Correlation — FastAPI] cluster alerts → create/update incidents → hash-chain ledger
   → [Artifact Generation] Markdown report, Mermaid graph, Ansible playbook (draft)
   → [FastAPI REST + WebSocket Gateway] ←── BFF on Vercel proxies here
```

## Service inventory

### Docker Compose services
| Service | Role |
|---|---|
| `redpanda` | Kafka-API streaming bus, single binary |
| `redis` | Hot feature store, WebSocket fan-out pub/sub |
| `postgres` | TimescaleDB — event store, feature cold store, incident DB |
| `mlflow` | Experiment tracking (SQLite backend, `/mlruns` volume) |
| `fluent-bit` | Log shipper (optional; Python replay producer used in sprint) |
| `faust-worker` | Stream processing: normalize, enrich, feature compute |
| `scoring-api` | FastAPI `/score` endpoint, ML model serving |
| `incident-api` | FastAPI — incidents, alerts, artifacts, WebSocket |
| `artifact-worker` | Async worker for report/graph/playbook generation |
| `prometheus` | Metrics scraping |
| `grafana` | Internal ops dashboard (frontend uses `/api/metrics` BFF instead) |

### Port map
| Service | Internal Port | External (VM) |
|---|---|---|
| Redpanda | 9092 (Kafka), 9644 (Admin) | 9092, 9644 |
| Redis | 6379 | 6379 (bind `127.0.0.1` in production) |
| Postgres/TimescaleDB | 5432 | 5432 (bind `127.0.0.1`) |
| MLflow UI | 5000 | 5000 |
| Scoring API | 8001 | 8001 (internal only) |
| Incident API | 8000 | 8000 (HTTPS via reverse proxy — **only externally exposed port**) |
| Prometheus | 9090 | 9090 (bind `127.0.0.1`) |
| Grafana | 3001 | 3001 |

A reverse proxy (Caddy or Nginx) handles TLS termination in front of port 8000.

## Streaming bus — Redpanda

### Topics
| Topic | Partitions | Retention | Publisher | Consumer |
|---|---|---|---|---|
| `raw.syslog` | 4 | 24 h | Replay producer / Fluent Bit | Faust worker |
| `raw.cloudtrail` | 4 | 24 h | Replay producer | Faust worker |
| `raw.auth` | 4 | 24 h | Replay producer | Faust worker |
| `raw.cicids` | 4 | 24 h | Replay producer | Faust worker |
| `normalized.events` | 8 | 7 d | Faust worker | Feature store agent, TimescaleDB sink |
| `alerts.raw` | 4 | 7 d | Scoring service (via Faust) | Incident correlation service |
| `incidents.updates` | 2 | 7 d | Incident API | WebSocket fan-out worker |

### Consumer groups
- `faust-normalizer-cg` — all `raw.*` topics; stateless, scale horizontally
- `faust-feature-cg` — `normalized.events`; stateful (windowed aggregations), one partition = one agent instance
- `alert-consumer-cg` — `alerts.raw`; incident correlation service

### Replay producer
`backend/ingestion/replay_producer.py` streams CICIDS2017 CSVs and synthetic logs at configurable speed:
```bash
python replay_producer.py --source cicids2017 \
  --file data/cicids2017/Wednesday-workingHours.pcap.IANA_labels.csv --speed 10
```
Injects controlled attack patterns (brute force at T+300s, lateral movement at T+600s) for deterministic demo scenarios.

## Stream processor — Faust (`backend/stream/faust_app.py`)

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

**Normalizers** (`backend/ingestion/normalizers/`), one per source: `syslog_normalizer.py` (RFC5424), `cloudtrail_normalizer.py` (AWS CloudTrail JSON → ECS), `auth_log_normalizer.py` (Linux `/var/log/auth.log`), `cicids_normalizer.py` (CICIDS2017 CSV → ECS flow events). All unit-tested in `backend/tests/test_normalizers.py`.

**GeoIP/ASN enrichment** — MaxMind GeoLite2 City + ASN databases (downloaded via `geoipupdate` on container startup):
```python
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

## Feature store

### Hot — Redis
Sliding-window aggregations as sorted sets/hashes, keyed by `entity_key = f"{host}:{user}:{source_ip}"`:

| Feature | Redis structure | Window | TTL |
|---|---|---|---|
| `event_count_1m` | ZADD | 1 min | 10 min |
| `event_count_5m` | ZADD | 5 min | 30 min |
| `event_count_1h` | ZADD | 1 h | 2 h |
| `failed_auth_ratio` | HSET (fail_count, total_count) | 5 min | 30 min |
| `distinct_dest_ports` | PFADD (HyperLogLog) | 5 min | 30 min |
| `dest_ip_fanout` | PFADD | 5 min | 30 min |
| `bytes_transferred` | INCRBY | 5 min | 30 min |

`feature_store.compute_windowed_features(event)` reads these and returns a `FeatureVector` Pydantic model.

### Cold — TimescaleDB
`feature_snapshots` hypertable: `(entity_key, window_end_ts, feature_json)`, 1-week chunks. Used by the autoencoder for historical-baseline training.

## ML scoring service (`backend/ml/scoring_service.py`, FastAPI)

`POST /score`:
```python
class ScoreRequest(BaseModel):
    entity_key: str
    features: FeatureVector
    event_id: str

class ScoreResponse(BaseModel):
    score: float          # 0.0–1.0, higher = more anomalous
    threshold: float
    is_anomaly: bool
    top_features: list[dict]
    model_version: str
    latency_ms: float
```
Models: `IsolationForest` (n_estimators=200, contamination='auto') and `Autoencoder` (3-layer symmetric bottleneck, `input → 32 → 16 → 8 → 16 → 32 → input`, trained on normal-only feature snapshots, reconstruction error = anomaly signal). Ensemble: `0.6×IF + 0.4×AE`.

**Threshold is not hardcoded** — loaded from `backend/ml/THRESHOLD_DECISION.md` and the matching MLflow metric artifact. Target: **recall ≥ 0.90 at precision ≥ 0.75** on held-out CICIDS2017 attack days.

## LLM triage client (`backend/llm/triage_client.py`)

Uses the Anthropic SDK with `claude-sonnet-4-6` and structured/schema-validated output:

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
```
Response fields: `technique_id`, `technique_name`, `tactic`, `confidence` (0-1), `rationale` (≤200 words), `severity` (`critical|high|medium|low`), `recommended_immediate_action` (draft phrasing only).

**Retry logic:** max 2 retries with exponential backoff on schema validation failure. After 2 failures → alert stored with `triage_status: "pending_manual"` (never silently accepted with invalid data).

**Batching:** alerts within the same `(source_ip, technique_category, 5-min window)` cluster go as a single LLM call with up to 30 representative events — reduces call volume ~10× in real attacks.

**Cost tracking** — every call logs to `llm_call_log`:
```sql
CREATE TABLE llm_call_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), called_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    model TEXT NOT NULL, input_tokens INT NOT NULL, output_tokens INT NOT NULL,
    latency_ms INT NOT NULL, cluster_size INT NOT NULL, technique_result TEXT, cost_usd NUMERIC(10,6)
);
```

## MITRE ATT&CK mapping engine

**Corpus:** `data/mitre/enterprise-attack-v15.1.json` — pinned STIX 2.1 bundle from `github.com/mitre/cti`. Loaded at startup via `mitreattack.stix20.MitreAttackData` (no external network call at runtime).

**Two-stage mapping:**
1. **Heuristic candidate generation** (`backend/mitre/rules.yaml`) — ~15-20 rules, e.g.:
   ```yaml
   - name: brute_force_ssh
     conditions: { event.action: ssh_login_failed, event_count_1m: "> 10", distinct_users: "> 2" }
     candidates: [T1110, T1110.001]
   - name: port_scan
     conditions: { distinct_dest_ports_5m: "> 50", bytes_per_event: "< 200" }
     candidates: [T1046]
   ```
   Full category set: brute force → T1110/T1110.001, port scan → T1046, DDoS → T1498, lateral movement (SMB/RDP) → T1021.x, privilege escalation → T1548.x, data exfiltration → T1041, impossible travel (geo-velocity) → T1078, process injection → T1055, suspicious process lineage → T1059.
2. **LLM re-ranking** — the triage client (above) picks the single best match from the candidate list with rationale.

**Navigator layer export** (`GET /api/navigator/layer.json`):
```python
def build_navigator_layer(incidents: list[Incident]) -> dict:
    technique_counts = Counter(i.technique_id for i in incidents)
    return {"name": "SOC Triager — Current Week", "versions": {"attack": "15", "navigator": "5"},
            "domain": "enterprise-attack",
            "techniques": [{"techniqueID": tid, "score": count, "color": score_to_color(count)}
                           for tid, count in technique_counts.items()]}
```

## Incident correlation & case management

**Correlation:** cluster alerts by `(source_ip, technique_id, 5-min window)`. Matching open incident → append. Otherwise → create new incident with auto-generated title, e.g. `"Credential Access via Brute Force: Password Guessing — prod-db-03"`.

**Hash-chained ledger** — append-only:
```python
def append_ledger_entry(incident_id, action, actor, payload):
    prev = db.query("SELECT hash FROM incident_ledger WHERE incident_id=$1 ORDER BY seq DESC LIMIT 1", incident_id)
    prev_hash = prev.hash if prev else "0" * 64
    entry_json = json.dumps({"action": action, "actor": actor, "payload": payload, "ts": utcnow()})
    new_hash = hashlib.sha256((prev_hash + entry_json).encode()).hexdigest()
    db.execute("INSERT INTO incident_ledger (...) VALUES (...)", new_hash, prev_hash, ...)
```

## Artifact generation service

- **Markdown incident report** (`backend/artifacts/report_generator.py`) — Jinja2 template (`templates/incident_report.md.j2`): header (title/severity/technique/tactic/confidence/dates), timeline table auto-generated from `incident.alerts`, entities section (host/user/IP + role), evidence section (≤5 raw log lines, code-block, **sanitized**), MITRE section, recommended actions.
- **Mermaid attack graph** (`backend/artifacts/attack_graph.py`) — builds a `graph LR` definition, colors nodes by role, stored on the incident and served via `GET /api/incidents/:id/graph.mmd`.
- **Containment playbook** (`backend/artifacts/playbook_templates/`) — one Jinja2 template per technique category: `brute_force.ansible.j2` (IP block + account lockout), `lateral_movement.ansible.j2` (network segmentation ACL), `ddos.ansible.j2` (rate limiting + null route), `priv_esc.ansible.j2` (account suspend + session kill), `exfil.ansible.j2` (egress firewall block). Variables come from observed IOCs. Output stored in `incidents.playbook_draft` and **never auto-executed**.

## Prometheus metrics exposed

Every service exposes `/metrics`: `events_ingested_total{source_type}`, `events_normalized_total{source_type}`, `alerts_generated_total{severity}`, `anomaly_score_histogram`, `scoring_latency_seconds`, `llm_calls_total{result}`, `llm_latency_seconds`, `llm_cost_usd_total`, `incidents_created_total{severity}`, `pipeline_e2e_latency_seconds`, `websocket_connections_active`.

## Observability

- **Structured logging** — `structlog`, JSON output, every line includes `service`, `trace_id`, `event_id` where applicable.
- **Grafana** dashboards: streaming throughput, ML score distribution, LLM cost/latency, incident creation rate.
- **Alertmanager rules:** Faust consumer lag > 1000 events, LLM error rate > 10%, scoring latency p95 > 100 ms.

## Startup & shutdown

```bash
docker compose up -d
curl http://localhost:8000/health   # Incident API
curl http://localhost:8001/health   # Scoring API
rpk cluster info --brokers localhost:9092
docker compose down   # Faust agents flush in-flight messages before exit
```
