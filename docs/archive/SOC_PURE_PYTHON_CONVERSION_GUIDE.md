# SOC Triager → Pure Python CLI Conversion Guide

This document is a complete, step-by-step blueprint for stripping the AI-driven SOC project
down to its core security functionality and running it as a self-contained Python CLI application,
with no React frontend, no FastAPI web server, no Anthropic/LLM dependency, and no Kubernetes.

---

## Table of Contents

1. [What You're Keeping vs. Removing](#1-what-youre-keeping-vs-removing)
2. [Target Architecture](#2-target-architecture)
3. [New Project Structure](#3-new-project-structure)
4. [Dependencies — Before and After](#4-dependencies--before-and-after)
5. [Phase 1 — Strip the LLM and AI Triage Layer](#5-phase-1--strip-the-llm-and-ai-triage-layer)
6. [Phase 2 — Replace FastAPI with a CLI Entry Point](#6-phase-2--replace-fastapi-with-a-cli-entry-point)
7. [Phase 3 — Replace Redis with In-Process State](#7-phase-3--replace-redis-with-in-process-state)
8. [Phase 4 — Replace PostgreSQL with SQLite](#8-phase-4--replace-postgresql-with-sqlite)
9. [Phase 5 — Replace Streaming (Redpanda/Faust) with File/Stdin Ingestion](#9-phase-5--replace-streaming-redpandafaust-with-filestdin-ingestion)
10. [Phase 6 — Keep the ML Detection Engine As-Is](#10-phase-6--keep-the-ml-detection-engine-as-is)
11. [Phase 7 — Keep MITRE ATT&CK Mapping (Heuristic Rules Only)](#11-phase-7--keep-mitre-attck-mapping-heuristic-rules-only)
12. [Phase 8 — Keep the Artifact Generators](#12-phase-8--keep-the-artifact-generators)
13. [Phase 9 — Wire Up the CLI](#13-phase-9--wire-up-the-cli)
14. [Phase 10 — Keep the Test Suite, Drop Frontend Tests](#14-phase-10--keep-the-test-suite-drop-frontend-tests)
15. [Module-by-Module Conversion Reference](#15-module-by-module-conversion-reference)
16. [Replacement Code Patterns](#16-replacement-code-patterns)
17. [Running the Application](#17-running-the-application)
18. [What You Lost and How to Partially Replace It](#18-what-you-lost-and-how-to-partially-replace-it)

---

## 1. What You're Keeping vs. Removing

### KEEP (core security functionality)

| Component | Location | Why Keep |
|---|---|---|
| Log normalizers (Syslog, CloudTrail, auth.log, CICIDS) | `backend/ingestion/normalizers/` | Core parsing logic |
| Synthetic log generators | `backend/ingestion/generators/` | Test data creation |
| ML ensemble (Isolation Forest + Autoencoder) | `backend/ml/` | Anomaly detection |
| Feature engineering | `backend/ml/feature_engineering.py` | Sliding window features |
| MITRE heuristic rules | `backend/mitre/rules.yaml` + `mapping_engine.py` | Technique mapping |
| Alert clustering | `backend/mitre/alert_clustering.py` | Event grouping |
| Artifact generators (Markdown report, Mermaid graph, Ansible playbook) | `backend/artifacts/` | Output generation |
| Input sanitizers | `backend/artifacts/sanitizers.py` | Security hygiene |
| Pydantic models / ECS schema | `backend/models.py` | Data validation |
| SHA-256 hash-chained ledger | Inside `incident_service.py` | Tamper-evident audit |
| JWT auth logic | `backend/api/auth_middleware.py` | Can repurpose for CLI sessions |
| Backend unit tests | `backend/tests/` | Quality assurance |

### REMOVE (no longer needed)

| Component | Reason |
|---|---|
| `backend/llm/` (entire folder) | Claude Sonnet / Anthropic SDK removed |
| `backend/api/` (entire folder) | FastAPI server replaced by CLI |
| `backend/stream/faust_app.py` | Faust/Kafka streaming replaced by file ingestion |
| `backend/ingestion/replay_producer.py` | No Redpanda broker |
| `backend/scoring_api/` | Merged into main process |
| `frontend/` (entire folder) | React UI replaced by terminal output |
| `infra/` (entire folder) | No Kubernetes |
| `docker-compose.yml` | No containerized services |
| `prometheus.yml` | No Prometheus metrics |
| `scaffold_helm.py` | No Helm charts |
| MLflow tracking | Optional — keep training scripts, remove tracking calls |
| Redis dependency | Replaced with in-process dicts |
| PostgreSQL / TimescaleDB | Replaced with SQLite |
| Redpanda message broker | Replaced with file/stdin |

---

## 2. Target Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    CLI ENTRY POINT                        │
│               soc_triager.py  (argparse)                  │
└──────────────┬───────────────────────────────────────────┘
               │
       ┌───────▼───────┐
       │  LOG INGESTOR  │  ← reads files, stdin, or synthetic generators
       │  (file-based)  │
       └───────┬───────┘
               │  NormalizedEvent (Pydantic)
       ┌───────▼───────────────────────┐
       │   FEATURE ENGINEERING         │
       │   (in-memory sliding windows) │
       └───────┬───────────────────────┘
               │  9-dim feature vector
       ┌───────▼───────────────────────┐
       │   ML ENSEMBLE                 │
       │   Isolation Forest + AE       │
       └───────┬───────────────────────┘
               │  anomaly score + top features
       ┌───────▼───────────────────────┐
       │   MITRE HEURISTIC MAPPER      │
       │   rules.yaml + mapping_engine │
       └───────┬───────────────────────┘
               │  candidate technique IDs
       ┌───────▼───────────────────────┐
       │   ALERT CLUSTERING            │
       │   5-min window, same entity   │
       └───────┬───────────────────────┘
               │  alert cluster
       ┌───────▼───────────────────────┐
       │   INCIDENT SERVICE            │
       │   SQLite + hash-chain ledger  │
       └───────┬───────────────────────┘
               │
       ┌───────▼───────────────────────┐
       │   ARTIFACT GENERATORS         │
       │   Markdown · Mermaid · Ansible│
       └───────┬───────────────────────┘
               │
       ┌───────▼───────────────────────┐
       │   TERMINAL OUTPUT / REPORTS   │
       │   (rich / colorama / stdout)  │
       └───────────────────────────────┘
```

Everything runs **in a single Python process** with no network services required.

---

## 3. New Project Structure

Delete the frontend, infra, and stream folders, then reorganize:

```
soc_triager_cli/
│
├── soc_triager.py              ← NEW: CLI entry point (argparse)
├── requirements.txt            ← TRIMMED: see Phase 4
├── config.py                   ← NEW: replaces .env / environment variables
├── database.py                 ← NEW: SQLite setup (replaces PostgreSQL)
│
├── ingestion/
│   ├── __init__.py
│   ├── normalizers/
│   │   ├── __init__.py         ← keep as-is
│   │   ├── syslog_normalizer.py    ← keep as-is
│   │   ├── cloudtrail_normalizer.py ← keep as-is
│   │   ├── auth_log_normalizer.py  ← keep as-is
│   │   └── cicids_normalizer.py    ← keep as-is
│   ├── generators/
│   │   ├── auth_log_generator.py   ← keep as-is
│   │   └── cloudtrail_generator.py ← keep as-is
│   └── file_ingestor.py        ← NEW: replaces replay_producer.py + faust_app.py
│
├── ml/
│   ├── __init__.py
│   ├── feature_engineering.py  ← MODIFIED: remove Redis, use in-memory dict
│   ├── autoencoder.py          ← keep as-is (PyTorch)
│   ├── train.py                ← MODIFIED: remove MLflow tracking calls
│   ├── evaluate.py             ← keep as-is
│   └── scorer.py               ← NEW: wraps both models into one call
│
├── mitre/
│   ├── __init__.py
│   ├── mapping_engine.py       ← keep as-is (remove Redpanda/Kafka imports if any)
│   ├── rules.yaml              ← keep as-is
│   └── alert_clustering.py     ← MODIFIED: use in-memory state instead of Redis
│
├── artifacts/
│   ├── __init__.py
│   ├── report_generator.py     ← keep as-is
│   ├── attack_graph.py         ← keep as-is
│   ├── playbook_renderer.py    ← keep as-is
│   ├── sanitizers.py           ← keep as-is
│   └── playbook_templates/     ← keep all 6 .yml.j2 files
│
├── services/
│   ├── __init__.py
│   └── incident_service.py     ← MODIFIED: SQLite instead of PostgreSQL, remove Redis pub/sub
│
├── models.py                   ← keep as-is (Pydantic ECS schema)
│
├── tests/
│   ├── test_normalizers.py     ← keep as-is
│   ├── test_clustering.py      ← keep as-is
│   ├── test_feature_engineering.py ← MODIFIED: mock in-memory store
│   ├── test_incident_service.py ← MODIFIED: SQLite fixtures
│   ├── test_llm_triage.py      ← DELETE (LLM removed)
│   ├── test_mitre_mapping.py   ← keep as-is
│   └── test_rbac.py            ← DELETE or repurpose (no JWT/HTTP)
│
└── data/
    ├── cicids2017/             ← training CSVs
    ├── mitre/enterprise-attack-v15.1.json
    └── models/                 ← trained .pkl and .pt files
```

---

## 4. Dependencies — Before and After

### Original `requirements.txt` (truncated)

```
fastapi==0.115.6
uvicorn==0.34.0
pydantic==2.10.4
anthropic==0.42.0          ← REMOVE
scikit-learn==1.6.1
torch==2.5.1
mlflow==2.19.0             ← REMOVE (or make optional)
faust-streaming==0.11.1    ← REMOVE
redis==5.2.1               ← REMOVE
psycopg2-binary            ← REMOVE
mitreattack-python==4.1.3
jinja2==3.1.5
pyjwt==2.10.1              ← REMOVE (no HTTP auth needed)
structlog                  ← keep or replace with logging
prometheus-client          ← REMOVE
pytest==8.3.4
pytest-asyncio             ← keep (some async tests)
pyyaml                     ← keep
```

### New `requirements.txt`

```txt
# Core data validation
pydantic==2.10.4

# ML
scikit-learn==1.6.1
torch==2.5.1
numpy
pandas

# MITRE ATT&CK
mitreattack-python==4.1.3

# Artifact generation
jinja2==3.1.5
pyyaml

# Database
# (sqlite3 is built into Python — no package needed)

# Terminal UI (choose one or both)
rich>=13.0          # colored tables, progress bars, panels
colorama            # fallback for Windows color

# Testing
pytest==8.3.4
pytest-asyncio

# Optional: keep if you want model experiment tracking
# mlflow==2.19.0
```

Install with:
```bash
pip install -r requirements.txt
```

---

## 5. Phase 1 — Strip the LLM and AI Triage Layer

### What to do

Delete the entire `backend/llm/` directory:
```bash
rm -rf backend/llm/
```

### What the LLM was doing

In `backend/llm/triage_client.py`, Claude Sonnet received a cluster of normalized events,
an anomaly score, top contributing features, and candidate MITRE technique IDs, then returned
a `TriageResult` with: `technique_id`, `technique_name`, `tactic`, `confidence`, `rationale`,
`severity`, and `recommended_immediate_action`.

### Replacement: deterministic triage function

Create `services/triage.py` with a rule-based replacement that produces the same
`TriageResult` shape using only what the heuristic engine already knows:

```python
# services/triage.py

from models import TriageResult  # your existing Pydantic model
from typing import List, Dict, Any

# Severity bands keyed on anomaly score
SEVERITY_BANDS = [
    (0.85, "critical"),
    (0.70, "high"),
    (0.50, "medium"),
    (0.00, "low"),
]

# Hard-coded recommended actions per tactic (extend as needed)
TACTIC_ACTIONS = {
    "Credential Access": "Block source IP at perimeter firewall and reset affected credentials.",
    "Discovery":         "Rate-limit or null-route scanning source; review exposed service inventory.",
    "Lateral Movement":  "Isolate pivot host from internal network segment; review shared credentials.",
    "Privilege Escalation": "Suspend affected account; audit sudo/setuid changes on host.",
    "Exfiltration":      "Block egress to destination IP/domain; capture packet trace for forensics.",
    "Impact":            "Activate DDoS mitigation (null-route or scrubbing service); notify upstream.",
    "Initial Access":    "Force re-authentication for affected accounts; review access logs.",
    "Defense Evasion":   "Collect memory image of affected process; quarantine host.",
    "Execution":         "Kill suspicious process tree; capture command history and file hashes.",
}

def deterministic_triage(
    events: List[Dict[str, Any]],
    anomaly_score: float,
    top_features: List[Dict[str, Any]],
    candidate_technique_ids: List[str],
    technique_name: str,
    tactic: str,
) -> TriageResult:
    """
    Rule-based replacement for Claude Sonnet triage.
    Returns the same TriageResult Pydantic model shape.
    """
    # Pick severity from score bands
    severity = "low"
    for threshold, label in SEVERITY_BANDS:
        if anomaly_score >= threshold:
            severity = label
            break

    # Confidence is a simple linear scale of the anomaly score
    confidence = round(min(anomaly_score * 1.1, 1.0), 3)

    # Pick the primary technique (first candidate from heuristic rules)
    technique_id = candidate_technique_ids[0] if candidate_technique_ids else "T0000"

    # Build a deterministic rationale from feature contributions
    feat_summary = ", ".join(
        f"{f['name']}={f.get('value', '?')}" for f in top_features[:3]
    )
    entity = events[0].get("source", {}).get("ip", "unknown") if events else "unknown"
    rationale = (
        f"Anomaly score {anomaly_score:.3f} triggered on entity {entity}. "
        f"Top contributing features: {feat_summary}. "
        f"Heuristic rules matched technique {technique_id} ({tactic})."
    )[:500]  # match the 500-char cap from the original Pydantic model

    action = TACTIC_ACTIONS.get(tactic, "Investigate host and isolate if confirmed malicious.")

    return TriageResult(
        technique_id=technique_id,
        technique_name=technique_name,
        tactic=tactic,
        confidence=confidence,
        rationale=rationale,
        severity=severity,
        recommended_immediate_action=action[:300],
    )
```

Anywhere the original code called `triage_event_cluster(...)` from `llm/triage_client.py`,
replace it with `deterministic_triage(...)` from `services/triage.py`. The call signature
is the same; only the implementation changes.

---

## 6. Phase 2 — Replace FastAPI with a CLI Entry Point

### What to do

Delete `backend/api/` entirely and create `soc_triager.py` in the project root:

```bash
rm -rf backend/api/
```

### New CLI structure (`soc_triager.py`)

```python
#!/usr/bin/env python3
"""
SOC Triager — Pure Python CLI
Usage: python soc_triager.py <command> [options]
"""
import argparse
import sys
from pathlib import Path

def cmd_ingest(args):
    """Ingest a log file and run detection."""
    from ingestion.file_ingestor import ingest_file
    from ml.scorer import score_events
    from mitre.mapping_engine import map_techniques
    from mitre.alert_clustering import cluster_alerts
    from services.incident_service import create_incident
    from services.triage import deterministic_triage
    from display import print_alert_table, print_incident_summary

    events = ingest_file(args.file, source_type=args.source)
    scored = score_events(events)
    anomalies = [s for s in scored if s["anomaly_score"] > args.threshold]

    print(f"\n[+] {len(events)} events ingested, {len(anomalies)} anomalies detected\n")

    clusters = cluster_alerts(anomalies)
    for cluster in clusters:
        techniques = map_techniques(cluster["events"], cluster["top_features"])
        triage = deterministic_triage(
            events=cluster["events"],
            anomaly_score=cluster["max_score"],
            top_features=cluster["top_features"],
            candidate_technique_ids=techniques["technique_ids"],
            technique_name=techniques["technique_name"],
            tactic=techniques["tactic"],
        )
        incident = create_incident(cluster, triage)
        print_incident_summary(incident)

        if args.artifacts:
            _generate_artifacts(incident, args.output_dir)

def cmd_train(args):
    """Train or retrain the ML models."""
    from ml.train import train_models
    train_models(data_dir=args.data_dir, output_dir=args.model_dir)

def cmd_evaluate(args):
    """Run evaluation on test data."""
    from ml.evaluate import run_evaluation
    run_evaluation(data_dir=args.data_dir, model_dir=args.model_dir)

def cmd_generate(args):
    """Generate synthetic log data for testing."""
    from ingestion.generators.auth_log_generator import generate_auth_log
    from ingestion.generators.cloudtrail_generator import generate_cloudtrail
    if args.type == "auth":
        generate_auth_log(output_path=args.output, n_events=args.count)
    elif args.type == "cloudtrail":
        generate_cloudtrail(output_path=args.output, n_events=args.count)

def cmd_list_incidents(args):
    """List all recorded incidents."""
    from services.incident_service import list_incidents
    from display import print_incident_table
    incidents = list_incidents(limit=args.limit)
    print_incident_table(incidents)

def cmd_show_incident(args):
    """Show details of a specific incident."""
    from services.incident_service import get_incident
    from display import print_incident_detail
    incident = get_incident(args.id)
    if not incident:
        print(f"Incident {args.id} not found.")
        sys.exit(1)
    print_incident_detail(incident)

def _generate_artifacts(incident, output_dir: str):
    from artifacts.report_generator import generate_report
    from artifacts.attack_graph import generate_mermaid_graph
    from artifacts.playbook_renderer import render_playbook
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / f"{incident['id']}_report.md"
    graph_path  = out / f"{incident['id']}_graph.mmd"
    playbook_path = out / f"{incident['id']}_playbook.yml"
    report_path.write_text(generate_report(incident))
    graph_path.write_text(generate_mermaid_graph(incident))
    playbook_path.write_text(render_playbook(incident))
    print(f"    → Artifacts written to {out}/")

def build_parser():
    parser = argparse.ArgumentParser(
        prog="soc_triager",
        description="SOC Triager — Pure Python security operations automation"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ingest
    p_ingest = sub.add_parser("ingest", help="Ingest and analyze a log file")
    p_ingest.add_argument("file", help="Path to log file")
    p_ingest.add_argument("--source", choices=["syslog","cloudtrail","auth","cicids"],
                          required=True, help="Log source type")
    p_ingest.add_argument("--threshold", type=float, default=0.40,
                          help="Anomaly score threshold (default 0.40)")
    p_ingest.add_argument("--artifacts", action="store_true",
                          help="Generate Markdown report, Mermaid graph, and Ansible playbook")
    p_ingest.add_argument("--output-dir", default="./output",
                          help="Directory for artifact output (default ./output)")
    p_ingest.set_defaults(func=cmd_ingest)

    # train
    p_train = sub.add_parser("train", help="Train ML models on CICIDS2017 data")
    p_train.add_argument("--data-dir", default="./data/cicids2017")
    p_train.add_argument("--model-dir", default="./data/models")
    p_train.set_defaults(func=cmd_train)

    # evaluate
    p_eval = sub.add_parser("evaluate", help="Evaluate trained models")
    p_eval.add_argument("--data-dir", default="./data/cicids2017")
    p_eval.add_argument("--model-dir", default="./data/models")
    p_eval.set_defaults(func=cmd_evaluate)

    # generate
    p_gen = sub.add_parser("generate", help="Generate synthetic log data")
    p_gen.add_argument("--type", choices=["auth","cloudtrail"], required=True)
    p_gen.add_argument("--output", default="./data/synthetic/output.log")
    p_gen.add_argument("--count", type=int, default=1000)
    p_gen.set_defaults(func=cmd_generate)

    # incidents
    p_list = sub.add_parser("incidents", help="List all recorded incidents")
    p_list.add_argument("--limit", type=int, default=20)
    p_list.set_defaults(func=cmd_list_incidents)

    # show
    p_show = sub.add_parser("show", help="Show a specific incident")
    p_show.add_argument("id", help="Incident ID")
    p_show.set_defaults(func=cmd_show_incident)

    return parser

if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
```

---

## 7. Phase 3 — Replace Redis with In-Process State

The original code used Redis sorted sets and HyperLogLog for sliding-window feature computation
and also for pub/sub event broadcasting. Neither is needed in a CLI application.

### File to modify: `ml/feature_engineering.py`

Replace every Redis call with a plain Python `collections.deque` or `dict`.

**Pattern: sliding window event count**

Original (Redis):
```python
pipe.zadd(key, {event_id: timestamp})
pipe.zremrangebyscore(key, 0, timestamp - window_secs)
count = pipe.zcount(key, timestamp - window_secs, timestamp)
```

Replacement (in-memory):
```python
from collections import deque
import time

_windows: dict[str, deque] = {}

def sliding_count(entity_key: str, event_id: str, timestamp: float, window_secs: int) -> int:
    if entity_key not in _windows:
        _windows[entity_key] = deque()
    dq = _windows[entity_key]
    dq.append((timestamp, event_id))
    cutoff = timestamp - window_secs
    while dq and dq[0][0] < cutoff:
        dq.popleft()
    return len(dq)
```

**Pattern: distinct value count (HyperLogLog → set)**

Original (Redis HyperLogLog):
```python
r.pfadd(f"ports:{entity}:{bucket}", dest_port)
count = r.pfcount(f"ports:{entity}:{bucket}")
```

Replacement:
```python
_port_sets: dict[str, set] = {}

def distinct_ports(entity_key: str, dest_port: int, bucket: str) -> int:
    k = f"{entity_key}:{bucket}"
    _port_sets.setdefault(k, set()).add(dest_port)
    return len(_port_sets[k])
```

**Pattern: byte counter**

Original (Redis INCR):
```python
r.incrby(f"bytes:{entity}:{bucket}", n_bytes)
total = r.get(f"bytes:{entity}:{bucket}")
```

Replacement:
```python
_byte_counters: dict[str, int] = {}

def add_bytes(entity_key: str, n_bytes: int, bucket: str) -> int:
    k = f"{entity_key}:{bucket}"
    _byte_counters[k] = _byte_counters.get(k, 0) + n_bytes
    return _byte_counters[k]
```

**Pattern: pub/sub (WebSocket broadcast)**

Remove entirely. The CLI just prints to stdout.

---

## 8. Phase 4 — Replace PostgreSQL with SQLite

Python's `sqlite3` module is in the standard library — no installation required.

### New file: `database.py`

```python
# database.py
import sqlite3
from pathlib import Path

DB_PATH = Path("./data/soc_triager.db")

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS incidents (
            id          TEXT PRIMARY KEY,
            entity      TEXT NOT NULL,
            technique   TEXT,
            tactic      TEXT,
            severity    TEXT,
            status      TEXT DEFAULT 'open',
            confidence  REAL,
            rationale   TEXT,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id           TEXT PRIMARY KEY,
            incident_id  TEXT REFERENCES incidents(id),
            entity       TEXT,
            anomaly_score REAL,
            status       TEXT DEFAULT 'new',
            severity     TEXT,
            source_type  TEXT,
            created_at   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ledger (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id  TEXT REFERENCES incidents(id),
            action       TEXT NOT NULL,
            actor        TEXT,
            previous_hash TEXT,
            this_hash    TEXT NOT NULL,
            timestamp    TEXT NOT NULL
        );
        """)
```

### Modify: `services/incident_service.py`

Replace all PostgreSQL (`psycopg2`) calls and Redis pub/sub calls with SQLite equivalents
using `database.get_connection()`. The hash-chain logic stays completely intact — it is pure
Python (SHA-256 over field values) and has no external dependencies.

**Imports to remove:**
```python
import psycopg2           # remove
import redis              # remove
from faust import ...     # remove
```

**Imports to add:**
```python
import sqlite3
from database import get_connection, init_db
```

---

## 9. Phase 5 — Replace Streaming (Redpanda/Faust) with File/Stdin Ingestion

The Faust/Redpanda pipeline consumed from Kafka topics. Replace this with a simple
synchronous file reader that feeds the same normalizers.

### New file: `ingestion/file_ingestor.py`

```python
# ingestion/file_ingestor.py
import sys
import json
from pathlib import Path
from typing import List, Dict, Any

from ingestion.normalizers import get_normalizer

def ingest_file(path: str, source_type: str) -> List[Dict[str, Any]]:
    """
    Read a log file line-by-line and normalize each line.
    Supports: syslog, cloudtrail (JSON-lines), auth, cicids (CSV).
    """
    normalizer = get_normalizer(source_type)
    events = []
    filepath = Path(path)

    if source_type == "cicids":
        # CICIDS is CSV — pass the whole file path
        return normalizer.normalize_file(filepath)

    with filepath.open("r", errors="replace") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                if source_type == "cloudtrail":
                    raw = json.loads(line)
                    event = normalizer.normalize(raw)
                else:
                    event = normalizer.normalize(line)
                if event:
                    events.append(event.model_dump())
            except Exception as exc:
                print(f"  [warn] line {line_no} skipped: {exc}", file=sys.stderr)

    return events

def ingest_stdin(source_type: str) -> List[Dict[str, Any]]:
    """Read from stdin (pipe mode)."""
    normalizer = get_normalizer(source_type)
    events = []
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            event = normalizer.normalize(line)
            if event:
                events.append(event.model_dump())
        except Exception:
            pass
    return events
```

Delete `backend/ingestion/replay_producer.py` and `backend/stream/faust_app.py`.

---

## 10. Phase 6 — Keep the ML Detection Engine As-Is

The ML code in `backend/ml/` is pure Python with scikit-learn and PyTorch.
It has no dependency on Redis, FastAPI, Redpanda, or the LLM. Keep all files verbatim.

**Only change:** remove MLflow tracking calls from `train.py` if you want zero external services.

Find and remove or comment out these patterns in `train.py`:
```python
import mlflow                    # remove / comment
mlflow.set_tracking_uri(...)     # remove
mlflow.start_run()               # remove
mlflow.log_param(...)            # remove
mlflow.log_metric(...)           # remove
mlflow.sklearn.log_model(...)    # remove
mlflow.pytorch.log_model(...)    # remove
```

The trained models are saved as `.pkl` (Isolation Forest) and `.pt` (Autoencoder) files.
Keep those save/load calls exactly as they are.

### New file: `ml/scorer.py`

Wrap both models into one callable so the CLI doesn't need to know the ensemble weights:

```python
# ml/scorer.py
import pickle
import numpy as np
import torch
from pathlib import Path
from typing import List, Dict, Any

from ml.feature_engineering import extract_features
from ml.autoencoder import Autoencoder

MODEL_DIR = Path("./data/models")

_if_model = None
_ae_model  = None

def _load_models():
    global _if_model, _ae_model
    if _if_model is None:
        with open(MODEL_DIR / "isolation_forest.pkl", "rb") as f:
            _if_model = pickle.load(f)
    if _ae_model is None:
        ae = Autoencoder(input_dim=9)
        ae.load_state_dict(torch.load(MODEL_DIR / "autoencoder.pt", map_location="cpu"))
        ae.eval()
        _ae_model = ae

def score_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Add anomaly_score and top_features to each event dict.
    Returns the same list with those fields appended.
    """
    _load_models()
    results = []
    for event in events:
        features = extract_features(event)          # returns np.ndarray shape (9,)
        vec = features.reshape(1, -1)

        # Isolation Forest score (higher = more anomalous, normalized 0-1)
        raw_if = -_if_model.score_samples(vec)[0]
        if_score = float(np.clip((raw_if + 0.5) / 1.5, 0, 1))

        # Autoencoder reconstruction error (percentile vs benign baseline)
        with torch.no_grad():
            tensor = torch.FloatTensor(vec)
            recon  = _ae_model(tensor)
            mse    = float(torch.nn.functional.mse_loss(recon, tensor).item())
        ae_score = float(np.clip(mse / 0.5, 0, 1))  # 0.5 = rough benign p95 threshold

        ensemble = 0.6 * if_score + 0.4 * ae_score

        # Top-3 contributing features (simple absolute deviation from median)
        feature_names = [
            "event_count_1m","event_count_5m","event_count_1h",
            "failed_auth_ratio","distinct_dest_ports","dest_ip_fanout",
            "bytes_transferred","tod_zscore","geo_velocity_kmh"
        ]
        contributions = list(zip(feature_names, np.abs(features - 0.5)))
        top3 = sorted(contributions, key=lambda x: x[1], reverse=True)[:3]

        result = dict(event)
        result["anomaly_score"] = round(ensemble, 4)
        result["top_features"]  = [{"name": n, "value": round(float(v), 4)} for n, v in top3]
        results.append(result)

    return results
```

---

## 11. Phase 7 — Keep MITRE ATT&CK Mapping (Heuristic Rules Only)

`backend/mitre/mapping_engine.py` and `backend/mitre/rules.yaml` are pure Python + YAML.
Keep them exactly as they are. The heuristic rules run independently of the LLM.

`backend/mitre/alert_clustering.py` uses Redis for time-bucketing. Apply the same
in-memory replacement pattern from Phase 3:

Replace:
```python
r = redis.from_url(settings.REDIS_URL)
r.zadd(cluster_key, {alert_id: timestamp})
cluster_ids = r.zrangebyscore(cluster_key, min_ts, max_ts)
```

With:
```python
from collections import defaultdict
_clusters: dict[str, list] = defaultdict(list)

def add_to_cluster(entity: str, technique: str, alert: dict, timestamp: float):
    bucket = int(timestamp // 300)   # 5-minute buckets, same as original
    key = f"{entity}:{technique}:{bucket}"
    _clusters[key].append((timestamp, alert))

def get_cluster(entity: str, technique: str, timestamp: float) -> list:
    bucket = int(timestamp // 300)
    key = f"{entity}:{technique}:{bucket}"
    return [a for _, a in _clusters[key]]
```

---

## 12. Phase 8 — Keep the Artifact Generators

All three generators in `backend/artifacts/` use only Jinja2 and standard Python.
Keep them verbatim. No changes needed.

Files to copy directly:
- `artifacts/report_generator.py`
- `artifacts/attack_graph.py`
- `artifacts/playbook_renderer.py`
- `artifacts/sanitizers.py`
- `artifacts/playbook_templates/*.yml.j2` (all 6 templates)

---

## 13. Phase 9 — Wire Up the CLI

Create a terminal display module to replace the React dashboard:

### New file: `display.py`

```python
# display.py — terminal output using 'rich' for colored tables
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

console = Console()

SEVERITY_COLORS = {
    "critical": "bold red",
    "high":     "red",
    "medium":   "yellow",
    "low":      "green",
}

def print_alert_table(alerts: list):
    table = Table(title="🚨 Detected Anomalies", show_lines=True)
    table.add_column("Entity",  style="cyan")
    table.add_column("Score",   justify="right")
    table.add_column("Severity",justify="center")
    table.add_column("Source",  style="dim")
    table.add_column("Time",    style="dim")
    for a in alerts:
        sev = a.get("severity", "low")
        table.add_row(
            a.get("source_ip", "?"),
            f"{a['anomaly_score']:.3f}",
            Text(sev.upper(), style=SEVERITY_COLORS.get(sev, "white")),
            a.get("source_type", "?"),
            a.get("timestamp", "?")[:19],
        )
    console.print(table)

def print_incident_summary(incident: dict):
    sev = incident.get("severity", "low")
    color = SEVERITY_COLORS.get(sev, "white")
    panel = Panel(
        f"[bold]Entity:[/bold]     {incident.get('entity', '?')}\n"
        f"[bold]Technique:[/bold]  {incident.get('technique', '?')}\n"
        f"[bold]Tactic:[/bold]     {incident.get('tactic', '?')}\n"
        f"[bold]Confidence:[/bold] {incident.get('confidence', 0):.0%}\n"
        f"[bold]Rationale:[/bold]  {incident.get('rationale', '')[:120]}",
        title=f"[{color}]Incident {incident['id']} — {sev.upper()}[/{color}]",
        border_style=color,
    )
    console.print(panel)

def print_incident_table(incidents: list):
    table = Table(title="📋 Incidents", show_lines=True)
    table.add_column("ID",        style="cyan", no_wrap=True)
    table.add_column("Entity",    style="white")
    table.add_column("Technique", style="dim")
    table.add_column("Severity",  justify="center")
    table.add_column("Status",    justify="center")
    table.add_column("Created",   style="dim")
    for i in incidents:
        sev = i.get("severity", "low")
        table.add_row(
            i["id"][:8],
            i.get("entity", "?"),
            i.get("technique", "?"),
            Text(sev.upper(), style=SEVERITY_COLORS.get(sev, "white")),
            i.get("status", "open"),
            i.get("created_at", "?")[:19],
        )
    console.print(table)

def print_incident_detail(incident: dict):
    print_incident_summary(incident)
    if incident.get("ledger"):
        console.print("\n[bold]Audit Ledger:[/bold]")
        for entry in incident["ledger"]:
            console.print(
                f"  [{entry['timestamp'][:19]}] {entry['action']} "
                f"(hash: {entry['this_hash'][:12]}...)"
            )
```

---

## 14. Phase 10 — Keep the Test Suite, Drop Frontend Tests

### Tests to keep (with minor modifications)

| File | Action |
|---|---|
| `test_normalizers.py` | Keep as-is, no changes |
| `test_clustering.py` | Update Redis mocks → in-memory mocks |
| `test_feature_engineering.py` | Update Redis mocks → in-memory mocks |
| `test_incident_service.py` | Update to use SQLite in-memory (`":memory:"`) |
| `test_mitre_mapping.py` | Keep as-is |

### Tests to delete

```bash
rm backend/tests/test_llm_triage.py   # LLM removed
rm backend/tests/test_rbac.py         # HTTP/JWT auth removed
```

### SQLite test fixture pattern

```python
# In conftest.py or at top of test_incident_service.py
import pytest
import sqlite3
from database import init_db, get_connection
import database

@pytest.fixture(autouse=True)
def use_test_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_PATH", test_db)
    init_db()
    yield
    # tmp_path cleaned up automatically
```

### Redis mock pattern for clustering tests

```python
# At top of test_clustering.py
import pytest
from unittest.mock import patch

@pytest.fixture(autouse=True)
def clear_in_memory_state():
    """Reset in-memory dicts between tests."""
    from mitre import alert_clustering
    alert_clustering._clusters.clear()
    yield
    alert_clustering._clusters.clear()
```

---

## 15. Module-by-Module Conversion Reference

Quick-reference table for every file in the original backend:

| Original File | Action | Notes |
|---|---|---|
| `api/main.py` | **DELETE** | Replaced by `soc_triager.py` CLI |
| `api/auth_middleware.py` | **DELETE** | No HTTP auth needed |
| `api/incident_service.py` | **MOVE + MODIFY** | Move to `services/`, swap DB |
| `api/routers/auth.py` | **DELETE** | |
| `api/routers/alerts.py` | **DELETE** | Alerts displayed in terminal |
| `api/routers/incidents.py` | **DELETE** | |
| `api/routers/metrics.py` | **DELETE** | |
| `api/routers/navigator.py` | **DELETE** | |
| `api/routers/playbooks.py` | **DELETE** | |
| `api/routers/websocket.py` | **DELETE** | No WebSocket |
| `artifacts/report_generator.py` | **KEEP** | No changes |
| `artifacts/attack_graph.py` | **KEEP** | No changes |
| `artifacts/playbook_renderer.py` | **KEEP** | No changes |
| `artifacts/sanitizers.py` | **KEEP** | No changes |
| `artifacts/playbook_templates/*.j2` | **KEEP** | No changes |
| `ingestion/normalizers/*.py` | **KEEP** | No changes |
| `ingestion/generators/*.py` | **KEEP** | No changes |
| `ingestion/replay_producer.py` | **DELETE** | Replaced by `file_ingestor.py` |
| `llm/triage_client.py` | **DELETE** | Replaced by `services/triage.py` |
| `llm/prompts/` | **DELETE** | |
| `mitre/mapping_engine.py` | **KEEP** | No changes |
| `mitre/rules.yaml` | **KEEP** | No changes |
| `mitre/alert_clustering.py` | **MODIFY** | Redis → in-memory dict |
| `ml/feature_engineering.py` | **MODIFY** | Redis → in-memory dict |
| `ml/autoencoder.py` | **KEEP** | No changes |
| `ml/train.py` | **MODIFY** | Remove MLflow calls |
| `ml/evaluate.py` | **KEEP** | No changes |
| `ml/register_models.py` | **DELETE** | No MLflow |
| `ml/FEATURE_COLUMNS.md` | **KEEP** | Documentation |
| `ml/THRESHOLD_DECISION.md` | **KEEP** | Documentation |
| `models.py` | **KEEP** | No changes |
| `scoring_api/main.py` | **DELETE** | Merged into `ml/scorer.py` |
| `stream/faust_app.py` | **DELETE** | Replaced by `file_ingestor.py` |
| `migrations/001_initial.sql` | **KEEP AS REFERENCE** | Translate to SQLite in `database.py` |
| `tests/test_normalizers.py` | **KEEP** | No changes |
| `tests/test_clustering.py` | **MODIFY** | Update Redis mocks |
| `tests/test_feature_engineering.py` | **MODIFY** | Update Redis mocks |
| `tests/test_incident_service.py` | **MODIFY** | SQLite fixtures |
| `tests/test_llm_triage.py` | **DELETE** | |
| `tests/test_mitre_mapping.py` | **KEEP** | No changes |
| `tests/test_rbac.py` | **DELETE** | |
| `docker-compose.yml` | **DELETE** | |
| `prometheus.yml` | **DELETE** | |

---

## 16. Replacement Code Patterns

### Pattern: anywhere `settings.REDIS_URL` or `redis.from_url(...)` appears

```python
# BEFORE
import redis
r = redis.from_url(settings.REDIS_URL)
r.zadd(key, {item: score})

# AFTER
from collections import deque, defaultdict
# Use the in-memory helpers shown in Phase 3
```

### Pattern: anywhere `settings.ANTHROPIC_API_KEY` or `anthropic.Anthropic()` appears

```python
# BEFORE
from anthropic import Anthropic
client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
message = client.messages.create(...)

# AFTER
from services.triage import deterministic_triage
result = deterministic_triage(...)
```

### Pattern: anywhere `mlflow` is imported

```python
# BEFORE
import mlflow
with mlflow.start_run():
    mlflow.log_param("n_estimators", 200)

# AFTER — just remove; save models directly to disk instead
import pickle
with open("data/models/isolation_forest.pkl", "wb") as f:
    pickle.dump(model, f)
```

### Pattern: anywhere `psycopg2` is imported

```python
# BEFORE
import psycopg2
conn = psycopg2.connect(settings.POSTGRES_DSN)

# AFTER
from database import get_connection
conn = get_connection()  # returns sqlite3.Connection
```

### Pattern: `from api.auth_middleware import require_role`

```python
# BEFORE
@router.post("/incidents/{id}/approve")
@require_role("approver")
async def approve_incident(id: str, ...):

# AFTER — in CLI, just check a config flag or --role argument
def cmd_approve(args):
    if args.role != "approver":
        print("Error: approval requires --role approver")
        sys.exit(1)
    ...
```

---

## 17. Running the Application

### First-time setup

```bash
# 1. Clone and enter the project
git clone https://github.com/SKYLINE217/AI-driven---SOC.git
cd AI-driven---SOC

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows PowerShell

# 3. Install trimmed dependencies
pip install -r requirements.txt

# 4. Download MITRE ATT&CK STIX bundle (if you want technique detail lookup)
mkdir -p data/mitre
# Place enterprise-attack-v15.1.json at data/mitre/

# 5. Train models (needs CICIDS2017 dataset in data/cicids2017/)
python soc_triager.py train

# 6. Initialize the SQLite database
python -c "from database import init_db; init_db(); print('DB ready')"
```

### Typical usage

```bash
# Generate synthetic auth log to test with
python soc_triager.py generate --type auth --output ./data/synthetic/auth.log --count 5000

# Analyze it and write artifacts to ./output/
python soc_triager.py ingest ./data/synthetic/auth.log \
    --source auth \
    --threshold 0.40 \
    --artifacts \
    --output-dir ./output

# List all detected incidents
python soc_triager.py incidents

# Show full detail of incident abc123
python soc_triager.py show abc123

# Analyze a real CloudTrail JSON-lines export
python soc_triager.py ingest ./cloudtrail.json --source cloudtrail --artifacts

# Pipe logs from stdin
cat /var/log/auth.log | python soc_triager.py ingest /dev/stdin --source auth
```

### Running tests

```bash
pytest tests/ -v
pytest tests/ --cov=. --cov-report=term-missing
```

---

## 18. What You Lost and How to Partially Replace It

| Lost Feature | Simple CLI Replacement |
|---|---|
| Real-time WebSocket alert feed | `watch -n 5 python soc_triager.py incidents --limit 5` |
| React dashboard | `rich` tables and panels in terminal (already in `display.py`) |
| MITRE Navigator heatmap | Export `layer.json` to a file; open in the official Navigator web app offline |
| LLM rationale (Claude) | Deterministic rationale from `services/triage.py` (see Phase 1) |
| Prometheus metrics | Write a `--stats` CLI command that prints throughput counters |
| Multi-user RBAC | `--role [analyst\|senior_analyst\|approver]` flag on commands |
| Redis sliding windows | In-memory deques (lose persistence across runs; acceptable for CLI use) |
| Kafka replay at speed | `--replay-speed N` flag in `file_ingestor.py` using `time.sleep` |
| Vercel BFF | Not needed; CLI calls internal functions directly |
| Hash-chained ledger | Fully preserved — pure Python SHA-256, no infrastructure change |
| Artifact generation | Fully preserved — Jinja2 + YAML, no infrastructure change |
| ML ensemble detection | Fully preserved — scikit-learn + PyTorch, no infrastructure change |

---

*Guide prepared for converting SKYLINE217/AI-driven---SOC to a standalone Python CLI.  
All core security functionality (ML detection, MITRE mapping, artifact generation, hash-chained audit trail) is preserved.*
