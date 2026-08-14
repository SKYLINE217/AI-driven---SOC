# SOC Triager — Pure Python Conversion: Continuation Guide

This document is the direct continuation of `SOC_PURE_PYTHON_CONVERSION_GUIDE.md`.
It supplies every file that was described but not fully written in that guide, plus a
step-by-step ordered execution checklist you can follow top-to-bottom to complete the
conversion in a single sitting.

---

## Table of Contents

19. [Missing File: `config.py`](#19-missing-file-configpy)
20. [Missing File: `ingestion/normalizers/__init__.py`](#20-missing-file-ingestionnormalizersinitpy)
21. [Missing File: `services/incident_service.py` (full SQLite rewrite)](#21-missing-file-servicesincident_servicepy-full-sqlite-rewrite)
22. [Missing File: `services/__init__.py`](#22-missing-file-servicesinitpy)
23. [Missing File: `ingestion/__init__.py`](#23-missing-file-ingestioninitpy)
24. [Missing File: `ml/__init__.py` and `mitre/__init__.py`](#24-missing-file-mlinitpy-and-mitreinitpy)
25. [Patched: `ml/feature_engineering.py` — full in-memory version](#25-patched-mlfeature_engineeringpy--full-in-memory-version)
26. [Patched: `mitre/alert_clustering.py` — full in-memory version](#26-patched-mitrealert_clusteringpy--full-in-memory-version)
27. [Patched: `ml/train.py` — MLflow removed](#27-patched-mltrainpy--mlflow-removed)
28. [Test Fixtures: `tests/conftest.py`](#28-test-fixtures-testsconftestpy)
29. [Ordered Execution Checklist](#29-ordered-execution-checklist)
30. [Common Errors and Fixes](#30-common-errors-and-fixes)

---

## 19. Missing File: `config.py`

This replaces all `settings.*` references that originally came from a `.env` file loaded
by `pydantic-settings`. In the CLI version there are no secrets to protect, so a plain
module-level config is sufficient.

```python
# config.py
"""
Central configuration for SOC Triager CLI.
Edit values here or override with environment variables.
All env-var overrides follow the pattern:  SOC_<KEY>=value
"""
import os
from pathlib import Path

# ── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
DATA_DIR   = Path(os.getenv("SOC_DATA_DIR",   str(BASE_DIR / "data")))
MODEL_DIR  = Path(os.getenv("SOC_MODEL_DIR",  str(DATA_DIR / "models")))
OUTPUT_DIR = Path(os.getenv("SOC_OUTPUT_DIR", str(BASE_DIR / "output")))
DB_PATH    = Path(os.getenv("SOC_DB_PATH",    str(DATA_DIR / "soc_triager.db")))
MITRE_STIX = Path(os.getenv("SOC_MITRE_STIX", str(DATA_DIR / "mitre" /
                             "enterprise-attack-v15.1.json")))

# ── ML thresholds ────────────────────────────────────────────────────────────
# Default anomaly score threshold for raising an alert (0–1 scale).
# Override with:  python soc_triager.py ingest ... --threshold 0.45
DEFAULT_THRESHOLD   = float(os.getenv("SOC_THRESHOLD",   "0.40"))

# Ensemble weights (must sum to 1.0)
IF_WEIGHT           = float(os.getenv("SOC_IF_WEIGHT",   "0.60"))   # Isolation Forest
AE_WEIGHT           = float(os.getenv("SOC_AE_WEIGHT",   "0.40"))   # Autoencoder
AE_BENIGN_P95       = float(os.getenv("SOC_AE_P95",      "0.50"))   # normalising denominator

# ── Feature engineering windows ─────────────────────────────────────────────
WINDOW_1M  = 60       # seconds
WINDOW_5M  = 300
WINDOW_1H  = 3600

# ── Alert clustering ────────────────────────────────────────────────────────
CLUSTER_WINDOW_SECS = int(os.getenv("SOC_CLUSTER_WINDOW", "300"))   # 5 minutes

# ── Logging ─────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("SOC_LOG_LEVEL", "WARNING")

# ── Misc ─────────────────────────────────────────────────────────────────────
# Analyst role used by --role flag on CLI commands that write to the ledger.
DEFAULT_ACTOR = os.getenv("SOC_ACTOR", "analyst")
```

Usage inside any module:

```python
from config import MODEL_DIR, DEFAULT_THRESHOLD
```

---

## 20. Missing File: `ingestion/normalizers/__init__.py`

`file_ingestor.py` calls `get_normalizer(source_type)` but the original project never
exposed a factory function. Add this `__init__.py` to `ingestion/normalizers/`:

```python
# ingestion/normalizers/__init__.py
"""
Factory that returns the correct normalizer for a given source-type string.
All normalizers must expose a  .normalize(raw)  method that returns a
NormalizedEvent Pydantic model (or None if the line should be skipped).

CICIDS normalizers additionally expose .normalize_file(path) → list[dict]
because the format is CSV, not line-oriented.
"""
from ingestion.normalizers.syslog_normalizer      import SyslogNormalizer
from ingestion.normalizers.cloudtrail_normalizer  import CloudTrailNormalizer
from ingestion.normalizers.auth_log_normalizer    import AuthLogNormalizer
from ingestion.normalizers.cicids_normalizer      import CICIDSNormalizer

_REGISTRY = {
    "syslog":      SyslogNormalizer,
    "cloudtrail":  CloudTrailNormalizer,
    "auth":        AuthLogNormalizer,
    "cicids":      CICIDSNormalizer,
}

def get_normalizer(source_type: str):
    """
    Return an instantiated normalizer for *source_type*.

    Raises ValueError for unknown source types so the CLI can surface a
    clear error message before touching any files.
    """
    key = source_type.lower()
    if key not in _REGISTRY:
        raise ValueError(
            f"Unknown source type '{source_type}'. "
            f"Valid choices: {', '.join(_REGISTRY)}"
        )
    return _REGISTRY[key]()

__all__ = ["get_normalizer"]
```

---

## 21. Missing File: `services/incident_service.py` (full SQLite rewrite)

The original `api/incident_service.py` used `psycopg2` (PostgreSQL) and Redis pub/sub.
Below is the full replacement using only `sqlite3` from the standard library.
The SHA-256 hash-chain logic is carried over verbatim.

```python
# services/incident_service.py
"""
Incident persistence layer — SQLite backend.
All write operations append a tamper-evident ledger entry (SHA-256 hash chain).
"""
import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import database   # provides get_connection(), DB_PATH


# ── helpers ──────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_hash(previous_hash: Optional[str], incident_id: str,
                  action: str, actor: str, timestamp: str) -> str:
    """SHA-256 over the concatenation of ledger fields — identical to original."""
    payload = f"{previous_hash or ''}{incident_id}{action}{actor}{timestamp}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _last_hash(conn: sqlite3.Connection, incident_id: str) -> Optional[str]:
    row = conn.execute(
        "SELECT this_hash FROM ledger WHERE incident_id = ? "
        "ORDER BY id DESC LIMIT 1",
        (incident_id,)
    ).fetchone()
    return row["this_hash"] if row else None


def _append_ledger(conn: sqlite3.Connection, incident_id: str,
                   action: str, actor: str) -> str:
    ts = _now()
    prev = _last_hash(conn, incident_id)
    this_hash = _compute_hash(prev, incident_id, action, actor, ts)
    conn.execute(
        "INSERT INTO ledger (incident_id, action, actor, previous_hash, this_hash, timestamp) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (incident_id, action, actor, prev, this_hash, ts)
    )
    return this_hash


# ── public API ───────────────────────────────────────────────────────────────

def create_incident(cluster: Dict[str, Any], triage) -> Dict[str, Any]:
    """
    Persist a new incident from an alert cluster + triage result.

    Parameters
    ----------
    cluster  : dict returned by alert_clustering.cluster_alerts()
               must have keys: events, max_score, entity
    triage   : TriageResult Pydantic model (or dict with same keys)

    Returns
    -------
    dict  — the row as stored, including the generated id.
    """
    database.init_db()   # no-op if tables already exist

    if hasattr(triage, "model_dump"):
        t = triage.model_dump()
    else:
        t = dict(triage)

    incident_id  = str(uuid.uuid4())
    entity       = cluster.get("entity", "unknown")
    now          = _now()

    with database.get_connection() as conn:
        conn.execute(
            """INSERT INTO incidents
               (id, entity, technique, tactic, severity, status,
                confidence, rationale, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?, ?)""",
            (
                incident_id, entity,
                t.get("technique_id"),   t.get("tactic"),
                t.get("severity"),
                t.get("confidence"),     t.get("rationale"),
                now, now,
            )
        )

        # Persist individual alerts that make up this cluster
        for evt in cluster.get("events", []):
            alert_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO alerts
                   (id, incident_id, entity, anomaly_score, status,
                    severity, source_type, created_at)
                   VALUES (?, ?, ?, ?, 'new', ?, ?, ?)""",
                (
                    alert_id, incident_id, entity,
                    evt.get("anomaly_score", 0.0),
                    t.get("severity"),
                    evt.get("source_type", "unknown"),
                    now,
                )
            )

        _append_ledger(conn, incident_id, "created", "system")

    return get_incident(incident_id)


def get_incident(incident_id: str) -> Optional[Dict[str, Any]]:
    """Return a fully-hydrated incident dict including its ledger, or None."""
    database.init_db()
    with database.get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM incidents WHERE id = ?", (incident_id,)
        ).fetchone()
        if not row:
            return None

        incident = dict(row)

        # Attach alerts
        alerts = conn.execute(
            "SELECT * FROM alerts WHERE incident_id = ? ORDER BY created_at",
            (incident_id,)
        ).fetchall()
        incident["alerts"] = [dict(a) for a in alerts]

        # Attach ledger
        ledger = conn.execute(
            "SELECT * FROM ledger WHERE incident_id = ? ORDER BY id",
            (incident_id,)
        ).fetchall()
        incident["ledger"] = [dict(e) for e in ledger]

    return incident


def list_incidents(
    limit: int = 20,
    status: Optional[str] = None,
    severity: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return incidents ordered newest-first, optionally filtered."""
    database.init_db()
    clauses, params = [], []
    if status:
        clauses.append("status = ?");   params.append(status)
    if severity:
        clauses.append("severity = ?"); params.append(severity)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)

    with database.get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM incidents {where} ORDER BY created_at DESC LIMIT ?",
            params
        ).fetchall()

    return [dict(r) for r in rows]


def update_status(incident_id: str, new_status: str,
                  actor: str = "analyst") -> Optional[Dict[str, Any]]:
    """
    Update incident status and write a ledger entry.
    Valid statuses: open, investigating, resolved, false_positive
    """
    valid = {"open", "investigating", "resolved", "false_positive"}
    if new_status not in valid:
        raise ValueError(f"Invalid status '{new_status}'. Choose from {valid}")

    database.init_db()
    now = _now()
    with database.get_connection() as conn:
        updated = conn.execute(
            "UPDATE incidents SET status = ?, updated_at = ? WHERE id = ?",
            (new_status, now, incident_id)
        ).rowcount
        if not updated:
            return None
        action = f"status_changed_to_{new_status}"
        _append_ledger(conn, incident_id, action, actor)

    return get_incident(incident_id)


def verify_chain(incident_id: str) -> Dict[str, Any]:
    """
    Walk the ledger for an incident and verify every hash link.
    Returns a dict with 'valid' (bool) and 'entries' (list of verification results).
    """
    database.init_db()
    with database.get_connection() as conn:
        entries = conn.execute(
            "SELECT * FROM ledger WHERE incident_id = ? ORDER BY id",
            (incident_id,)
        ).fetchall()

    results = []
    prev_hash = None
    all_valid = True

    for entry in entries:
        expected = _compute_hash(
            prev_hash,
            incident_id,
            entry["action"],
            entry["actor"],
            entry["timestamp"],
        )
        ok = entry["this_hash"] == expected
        all_valid = all_valid and ok
        results.append({
            "id":        entry["id"],
            "action":    entry["action"],
            "timestamp": entry["timestamp"],
            "hash":      entry["this_hash"][:16] + "...",
            "valid":     ok,
        })
        prev_hash = entry["this_hash"]

    return {"incident_id": incident_id, "valid": all_valid, "entries": results}
```

---

## 22. Missing File: `services/__init__.py`

```python
# services/__init__.py
# intentionally empty — marks this directory as a Python package
```

---

## 23. Missing File: `ingestion/__init__.py`

```python
# ingestion/__init__.py
# intentionally empty — marks this directory as a Python package
```

---

## 24. Missing File: `ml/__init__.py` and `mitre/__init__.py`

Both are identical — just empty package markers:

```python
# ml/__init__.py
# mitre/__init__.py
# intentionally empty
```

---

## 25. Patched: `ml/feature_engineering.py` — full in-memory version

Below is the **complete file** with every Redis call replaced by the in-memory helpers
shown in Phase 3 of the main guide. Copy this over the original.

```python
# ml/feature_engineering.py
"""
Sliding-window feature extraction — in-memory implementation.
Replaces the original Redis-backed version.

Features extracted (9 total, matching FEATURE_COLUMNS.md):
  0  event_count_1m       — events from this entity in last 60 s
  1  event_count_5m       — events from this entity in last 300 s
  2  event_count_1h       — events from this entity in last 3600 s
  3  failed_auth_ratio    — fraction of recent events that are failed auths
  4  distinct_dest_ports  — distinct destination ports in last 5 min
  5  dest_ip_fanout       — distinct destination IPs in last 5 min
  6  bytes_transferred    — bytes sent by entity in last 5 min
  7  tod_zscore           — time-of-day z-score (how unusual is this hour?)
  8  geo_velocity_kmh     — km/h implied by last two source-IP geolocations
"""

import math
import time
from collections import deque, defaultdict
from typing import Any, Dict, Tuple

import numpy as np

from config import WINDOW_1M, WINDOW_5M, WINDOW_1H

# ── In-memory state ───────────────────────────────────────────────────────────
# Keyed by entity string (source IP / username).

_event_times:   Dict[str, deque] = defaultdict(deque)   # (ts, event_id) pairs
_fail_times:    Dict[str, deque] = defaultdict(deque)   # failed-auth timestamps
_dest_ports:    Dict[str, set]   = defaultdict(set)     # per 5-min bucket
_dest_ips:      Dict[str, set]   = defaultdict(set)     # per 5-min bucket
_byte_totals:   Dict[str, int]   = defaultdict(int)     # per 5-min bucket
_last_geo:      Dict[str, Tuple[float, float, float]] = {}  # entity → (lat, lon, ts)

# Historical hour-of-day event counts for z-score (updated at runtime).
_hourly_counts: np.ndarray = np.ones(24)  # initialised to 1 to avoid div-by-zero


def _bucket_key(entity: str, ts: float) -> str:
    """5-minute bucket key."""
    return f"{entity}:{int(ts // 300)}"


def _trim_deque(dq: deque, cutoff: float):
    while dq and dq[0][0] < cutoff:
        dq.popleft()


def _sliding_count(dq: deque, ts: float, window: int) -> int:
    _trim_deque(dq, ts - window)
    return len(dq)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def extract_features(event: Dict[str, Any]) -> np.ndarray:
    """
    Given one normalised event dict, update in-memory state and return
    a float32 numpy array of shape (9,) ready for the ML models.
    """
    ts     = event.get("@timestamp_unix", time.time())
    entity = (event.get("source", {}).get("ip")
              or event.get("user", {}).get("name")
              or "unknown")
    is_fail = int(event.get("event", {}).get("outcome") == "failure")
    dport   = event.get("destination", {}).get("port", 0)
    dip     = event.get("destination", {}).get("ip", "")
    nbytes  = event.get("network", {}).get("bytes", 0) or 0
    lat     = event.get("source", {}).get("geo", {}).get("location", {}).get("lat", None)
    lon     = event.get("source", {}).get("geo", {}).get("location", {}).get("lon", None)

    # ── Update sliding windows ────────────────────────────────────────────────
    event_id = event.get("event", {}).get("id", str(ts))

    et = _event_times[entity]
    et.append((ts, event_id))

    if is_fail:
        _fail_times[entity].append((ts, event_id))

    bkey = _bucket_key(entity, ts)
    if dport:
        _dest_ports[bkey].add(dport)
    if dip:
        _dest_ips[bkey].add(dip)
    _byte_totals[bkey] = _byte_totals.get(bkey, 0) + nbytes

    # ── Compute features ─────────────────────────────────────────────────────
    cnt_1m = _sliding_count(_event_times[entity], ts, WINDOW_1M)
    cnt_5m = _sliding_count(_event_times[entity], ts, WINDOW_5M)
    cnt_1h = _sliding_count(_event_times[entity], ts, WINDOW_1H)

    fail_dq = _fail_times[entity]
    _trim_deque(fail_dq, ts - WINDOW_5M)
    fail_ratio = len(fail_dq) / max(cnt_5m, 1)

    distinct_ports = len(_dest_ports.get(bkey, set()))
    dest_fanout    = len(_dest_ips.get(bkey, set()))
    byte_total     = _byte_totals.get(bkey, 0)

    # Time-of-day z-score
    hour = int(time.gmtime(ts).tm_hour)
    _hourly_counts[hour] += 1
    mean_h = _hourly_counts.mean()
    std_h  = _hourly_counts.std() or 1.0
    tod_z  = (_hourly_counts[hour] - mean_h) / std_h

    # Geo velocity
    geo_vel = 0.0
    if lat is not None and lon is not None:
        if entity in _last_geo:
            plat, plon, pts = _last_geo[entity]
            dt = max(ts - pts, 1.0)
            dist = _haversine_km(plat, plon, float(lat), float(lon))
            geo_vel = (dist / dt) * 3600   # km/h
        _last_geo[entity] = (float(lat), float(lon), ts)

    return np.array([
        float(cnt_1m),
        float(cnt_5m),
        float(cnt_1h),
        float(fail_ratio),
        float(distinct_ports),
        float(dest_fanout),
        float(nbytes),
        float(tod_z),
        float(geo_vel),
    ], dtype=np.float32)


def reset_state():
    """Clear all in-memory accumulators. Call between test runs."""
    _event_times.clear()
    _fail_times.clear()
    _dest_ports.clear()
    _dest_ips.clear()
    _byte_totals.clear()
    _last_geo.clear()
    _hourly_counts[:] = 1.0
```

---

## 26. Patched: `mitre/alert_clustering.py` — full in-memory version

```python
# mitre/alert_clustering.py
"""
Alert clustering — in-memory implementation.
Groups anomalous events by (entity, technique, 5-min bucket).
Replaces the original Redis sorted-set implementation.
"""
from collections import defaultdict
from typing import Any, Dict, List

from config import CLUSTER_WINDOW_SECS

# ── In-memory store ───────────────────────────────────────────────────────────
# key: "entity:technique_id:bucket"  →  list of (timestamp, event_dict)
_clusters: Dict[str, List] = defaultdict(list)


def _bucket(ts: float) -> int:
    return int(ts // CLUSTER_WINDOW_SECS)


def _key(entity: str, technique_id: str, ts: float) -> str:
    return f"{entity}:{technique_id}:{_bucket(ts)}"


def add_alert(entity: str, technique_id: str, event: Dict[str, Any]) -> None:
    """Add one scored event to the appropriate cluster bucket."""
    ts = event.get("@timestamp_unix", 0.0)
    k  = _key(entity, technique_id, ts)
    _clusters[k].append((ts, event))


def cluster_alerts(
    scored_events: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Convenience wrapper used by the CLI ingest command.

    Takes the flat list of scored events (output of ml.scorer.score_events),
    groups them, and returns a list of cluster dicts ready for triage.

    Each cluster dict has:
        entity       : str
        technique_id : str  (placeholder — mapping_engine fills this properly)
        events       : list[dict]
        max_score    : float
        top_features : list[dict]  (from the highest-scoring event)
    """
    # Group by entity first (technique mapping hasn't run yet at this stage)
    by_entity: Dict[str, List[Dict]] = defaultdict(list)
    for evt in scored_events:
        entity = (evt.get("source", {}).get("ip")
                  or evt.get("user", {}).get("name")
                  or "unknown")
        by_entity[entity].append(evt)

    clusters = []
    for entity, events in by_entity.items():
        if not events:
            continue
        max_evt   = max(events, key=lambda e: e.get("anomaly_score", 0))
        max_score = max_evt.get("anomaly_score", 0.0)
        clusters.append({
            "entity":       entity,
            "technique_id": "",          # filled by mapping_engine later
            "events":       events,
            "max_score":    max_score,
            "top_features": max_evt.get("top_features", []),
        })

    return clusters


def get_cluster(entity: str, technique_id: str, ts: float) -> List[Dict]:
    """Return all events in the 5-min bucket for (entity, technique)."""
    k = _key(entity, technique_id, ts)
    return [evt for _, evt in _clusters.get(k, [])]


def reset_state() -> None:
    """Clear all clusters. Call between test runs."""
    _clusters.clear()
```

---

## 27. Patched: `ml/train.py` — MLflow removed

Only the lines that call `mlflow` need to be deleted. Below is a drop-in template
showing the skeleton with those calls stripped. Replace your actual model-building
logic where the `# ... your training code ...` comments appear.

```python
# ml/train.py
"""
Train Isolation Forest + Autoencoder on CICIDS2017 dataset.
MLflow tracking removed — models saved directly to disk as .pkl / .pt files.
"""
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from ml.autoencoder import Autoencoder
from config import MODEL_DIR


def train_models(data_dir: str = "./data/cicids2017",
                 output_dir: str = str(MODEL_DIR)) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print("[*] Loading CICIDS2017 data...")
    # ... your existing data-loading and feature-extraction code ...
    # X_train, y_train = load_and_prepare(data_dir)

    # ── Isolation Forest ─────────────────────────────────────────────────────
    print("[*] Training Isolation Forest...")
    if_model = IsolationForest(n_estimators=200, contamination=0.05,
                               random_state=42, n_jobs=-1)
    # if_model.fit(X_train)

    # Save directly — no MLflow
    with open(out / "isolation_forest.pkl", "wb") as f:
        pickle.dump(if_model, f)
    print(f"    → saved {out}/isolation_forest.pkl")

    # ── Autoencoder ──────────────────────────────────────────────────────────
    print("[*] Training Autoencoder...")
    ae = Autoencoder(input_dim=9)
    optimiser = torch.optim.Adam(ae.parameters(), lr=1e-3)
    criterion = nn.MSELoss()

    # ... your training loop ...
    # for epoch in range(50):
    #     loss = criterion(ae(X_tensor), X_tensor)
    #     optimiser.zero_grad(); loss.backward(); optimiser.step()

    torch.save(ae.state_dict(), out / "autoencoder.pt")
    print(f"    → saved {out}/autoencoder.pt")

    print("[+] Training complete.")
```

**Lines to find and delete in your actual `train.py`:**

```
import mlflow
import mlflow.sklearn
import mlflow.pytorch

mlflow.set_tracking_uri(...)
mlflow.set_experiment(...)
with mlflow.start_run():
mlflow.log_param(...)
mlflow.log_metric(...)
mlflow.log_artifact(...)
mlflow.sklearn.log_model(...)
mlflow.pytorch.log_model(...)
```

None of these have functional replacements — just delete them. Model files are already
being written to disk with `pickle.dump` / `torch.save` in the original code; those
lines stay exactly as they are.

---

## 28. Test Fixtures: `tests/conftest.py`

Create this file at `tests/conftest.py`. It handles the SQLite and in-memory resets
for all test files automatically via `autouse=True`.

```python
# tests/conftest.py
"""
Shared pytest fixtures for the SOC Triager CLI test suite.
Handles:
  - SQLite in-memory database for incident_service tests
  - In-memory state resets for feature_engineering and alert_clustering
"""
import pytest
import database
from pathlib import Path


# ── SQLite fixture ────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """
    Point database.DB_PATH at a fresh temp file for every test.
    Automatically used by ALL tests (autouse=True).
    """
    test_db = tmp_path / "test_soc.db"
    monkeypatch.setattr(database, "DB_PATH", test_db)
    database.init_db()
    yield
    # tmp_path cleanup is handled by pytest


# ── In-memory state resets ────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_feature_state():
    """Clear feature engineering accumulators before and after each test."""
    from ml.feature_engineering import reset_state
    reset_state()
    yield
    reset_state()


@pytest.fixture(autouse=True)
def reset_cluster_state():
    """Clear alert clustering state before and after each test."""
    from mitre.alert_clustering import reset_state
    reset_state()
    yield
    reset_state()


# ── Sample data helpers ───────────────────────────────────────────────────────

@pytest.fixture
def sample_event():
    """A minimal normalized event dict for use in unit tests."""
    return {
        "@timestamp_unix": 1_700_000_000.0,
        "source": {"ip": "10.0.0.1", "geo": {"location": {"lat": 28.6, "lon": 77.2}}},
        "destination": {"ip": "8.8.8.8", "port": 443},
        "user": {"name": "testuser"},
        "event": {"id": "evt-001", "outcome": "success"},
        "network": {"bytes": 1024},
        "source_type": "syslog",
    }


@pytest.fixture
def sample_failed_auth_event(sample_event):
    evt = dict(sample_event)
    evt["event"] = {"id": "evt-002", "outcome": "failure"}
    return evt


@pytest.fixture
def sample_cluster(sample_event):
    """A minimal cluster dict as returned by cluster_alerts()."""
    return {
        "entity":       "10.0.0.1",
        "technique_id": "T1078",
        "events":       [sample_event],
        "max_score":    0.72,
        "top_features": [{"name": "failed_auth_ratio", "value": 0.80}],
    }


@pytest.fixture
def sample_triage_result():
    """A minimal TriageResult dict for tests that don't need real triage."""
    return {
        "technique_id":              "T1078",
        "technique_name":            "Valid Accounts",
        "tactic":                    "Credential Access",
        "confidence":                0.79,
        "rationale":                 "Test rationale.",
        "severity":                  "high",
        "recommended_immediate_action": "Block IP and reset credentials.",
    }
```

---

## 29. Ordered Execution Checklist

Follow these steps exactly in order. Each step references the section of this guide
or the main guide that provides the code.

### Step 1 — Clone and scaffold

```bash
git clone https://github.com/SKYLINE217/AI-driven---SOC.git
cd AI-driven---SOC
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### Step 2 — Delete what you will not need

```bash
# Infrastructure / containers
rm -f docker-compose.yml prometheus.yml scaffold_helm.py
rm -rf infra/

# Frontend
rm -rf frontend/

# Streaming layer
rm -f backend/stream/faust_app.py
rmdir backend/stream 2>/dev/null || true
rm -f backend/ingestion/replay_producer.py

# FastAPI layer
rm -rf backend/api/

# LLM layer
rm -rf backend/llm/

# Scoring microservice (merged into ml/scorer.py)
rm -rf backend/scoring_api/

# Dead tests
rm -f backend/tests/test_llm_triage.py
rm -f backend/tests/test_rbac.py
```

### Step 3 — Flatten the directory structure

The original code lived under `backend/`. Move everything up one level:

```bash
# From inside AI-driven---SOC/
cp -r backend/ingestion  ./ingestion
cp -r backend/ml         ./ml
cp -r backend/mitre      ./mitre
cp -r backend/artifacts  ./artifacts
cp -r backend/models.py  ./models.py
mkdir -p services
cp    backend/tests      ./tests  -r

# Remove the now-redundant backend/ folder
rm -rf backend/
```

> If your repo does NOT have a `backend/` wrapper and files are already at the top
> level, skip this step.

### Step 4 — Install trimmed dependencies

Replace `requirements.txt` with the new version from **Section 4** of the main guide,
then install:

```bash
pip install -r requirements.txt
```

### Step 5 — Add new files

Create each of these files using the code from this document and the main guide:

| File | Source |
|---|---|
| `config.py` | Section 19 of this document |
| `database.py` | Section 8 (Phase 4) of main guide |
| `ingestion/__init__.py` | Section 23 of this document |
| `ingestion/normalizers/__init__.py` | Section 20 of this document |
| `ingestion/file_ingestor.py` | Section 9 (Phase 5) of main guide |
| `ml/__init__.py` | Section 24 of this document |
| `ml/scorer.py` | Section 10 (Phase 6) of main guide |
| `ml/feature_engineering.py` | Section 25 of this document (full replace) |
| `mitre/__init__.py` | Section 24 of this document |
| `mitre/alert_clustering.py` | Section 26 of this document (full replace) |
| `services/__init__.py` | Section 22 of this document |
| `services/incident_service.py` | Section 21 of this document (full replace) |
| `services/triage.py` | Section 5 (Phase 1) of main guide |
| `display.py` | Section 13 (Phase 9) of main guide |
| `soc_triager.py` | Section 6 (Phase 2) of main guide |
| `tests/conftest.py` | Section 28 of this document |

### Step 6 — Patch existing files

**`ml/train.py`** — delete all MLflow lines (see Section 27).

**Any file that contains `from api.auth_middleware import ...`** — remove the import
and the decorator; see the replacement pattern in Section 16 of the main guide.

**Any file that contains `from faust import ...`** or `import faust` — remove those
imports entirely; they were only in `stream/faust_app.py` which is already deleted.

Quick grep to catch any stragglers:

```bash
grep -r "import mlflow"    . --include="*.py"
grep -r "import redis"     . --include="*.py"
grep -r "import psycopg2"  . --include="*.py"
grep -r "import faust"     . --include="*.py"
grep -r "import anthropic" . --include="*.py"
```

Each hit should return zero results after patching. Fix any that remain.

### Step 7 — Initialize the database and verify imports

```bash
python -c "
import database
database.init_db()
print('DB init: OK')

from ingestion.normalizers import get_normalizer
n = get_normalizer('auth')
print('Normalizer factory: OK')

from services.incident_service import list_incidents
print('Incident service: OK', list_incidents())

from ml.scorer import score_events
print('Scorer import: OK')
"
```

All four lines should print without errors before you proceed.

### Step 8 — Train the models

You need the CICIDS2017 dataset. Download `Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv`
and the other day-files from the official UNB link, place them in `data/cicids2017/`, then:

```bash
python soc_triager.py train
```

Expected output: two files appear at `data/models/isolation_forest.pkl` and
`data/models/autoencoder.pt`.

### Step 9 — Smoke-test with synthetic data

```bash
# Generate 2 000 synthetic auth log events
python soc_triager.py generate --type auth --output ./data/synthetic/test.log --count 2000

# Ingest, detect, cluster, and write artifacts
python soc_triager.py ingest ./data/synthetic/test.log \
    --source auth \
    --threshold 0.35 \
    --artifacts \
    --output-dir ./output

# List what was recorded
python soc_triager.py incidents
```

If the `ingest` command prints the anomaly count and at least one incident panel,
the conversion is complete.

### Step 10 — Run the test suite

```bash
pytest tests/ -v
```

Expected: all tests that previously tested normalizers, MITRE mapping, clustering,
and incident service pass. The two deleted test files (`test_llm_triage.py`,
`test_rbac.py`) are gone and therefore not collected.

---

## 30. Common Errors and Fixes

| Error message | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'redis'` | An old import wasn't deleted | `grep -r "import redis" . --include="*.py"` and remove all hits |
| `ModuleNotFoundError: No module named 'anthropic'` | Old llm import remaining | `grep -r "import anthropic" . --include="*.py"` and remove |
| `ModuleNotFoundError: No module named 'faust'` | Faust import surviving somewhere | `grep -r "import faust" . --include="*.py"` and remove |
| `FileNotFoundError: isolation_forest.pkl` | Models not trained yet | Run `python soc_triager.py train` first |
| `FileNotFoundError: autoencoder.pt` | Same as above | Same fix |
| `sqlite3.OperationalError: no such table: incidents` | `init_db()` never called | Add `database.init_db()` at the top of `soc_triager.py` main block |
| `ValueError: Unknown source type 'X'` | Wrong `--source` flag | Valid choices: `syslog`, `cloudtrail`, `auth`, `cicids` |
| `ImportError: cannot import name 'get_normalizer'` | `ingestion/normalizers/__init__.py` missing | Create it from Section 20 |
| `AttributeError: 'dict' object has no attribute 'model_dump'` | A normalizer returns a dict instead of a Pydantic model | Wrap the return: `NormalizedEvent(**raw_dict)` |
| Tests fail with `sqlite3.OperationalError: unable to open database file` | `isolated_db` fixture not running | Check `tests/conftest.py` exists and has `autouse=True` |
| `torch.nn.modules.module.ModuleAttributeError` loading the autoencoder | `Autoencoder` class definition changed between training and loading | Retrain: `python soc_triager.py train` |
| `rich` import error on Windows (colors broken) | Terminal doesn't support ANSI | Add `console = Console(force_terminal=True)` in `display.py` |

---

*Continuation guide for SKYLINE217/AI-driven---SOC → Pure Python CLI conversion.
This document is designed to be read alongside `SOC_PURE_PYTHON_CONVERSION_GUIDE.md`.*
