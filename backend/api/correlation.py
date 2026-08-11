"""
Incident Correlation Service
Consumes alerts.raw from Redpanda → clusters by (source_ip, technique_category, 5-min window)
→ creates/updates Incidents → triggers LLM triage → writes ledger → publishes to WS
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

# Try imports — graceful fallback if not installed
try:
    from kafka import KafkaConsumer  # type: ignore
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False

try:
    import redis.asyncio as aioredis  # type: ignore
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# In-memory incident store for dev (replace with Postgres in Day 4)
_incidents: dict[str, dict[str, Any]] = {}
# Cluster key → incident_id mapping
_clusters: dict[str, str] = {}


def _cluster_key(alert: dict[str, Any]) -> str:
    """Group alerts by (source_ip, technique_category, 5-min bucket)."""
    ts = alert.get("timestamp", datetime.now(timezone.utc).isoformat())
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        dt = datetime.now(timezone.utc)
    # 5-minute bucket
    bucket = dt.replace(second=0, microsecond=0, minute=(dt.minute // 5) * 5)
    source_ip = alert.get("source_ip", "unknown")
    technique = alert.get("technique_id", "T0000")[:5]  # T1110 prefix
    return f"{source_ip}|{technique}|{bucket.isoformat()}"


def _hash_chain(prev_hash: str, payload: dict[str, Any]) -> str:
    """Compute SHA-256 hash for ledger entry."""
    content = f"{prev_hash}{json.dumps(payload, sort_keys=True)}"
    return hashlib.sha256(content.encode()).hexdigest()


async def _publish_to_ws(redis_client: Any, alert: dict[str, Any]) -> None:
    """Publish a new alert event to the WebSocket channel via Redis Pub/Sub."""
    message = json.dumps({"type": "new_alert", "payload": alert})
    if redis_client:
        await redis_client.publish("ws:alerts:broadcast", message)


def _build_incident(alert: dict[str, Any], cluster_key: str) -> dict[str, Any]:
    """Create a new incident from the first alert in a cluster."""
    score = alert.get("anomaly_score", 0.5)
    if score >= 0.9:
        severity = "critical"
    elif score >= 0.75:
        severity = "high"
    elif score >= 0.6:
        severity = "medium"
    else:
        severity = "low"

    return {
        "id": str(uuid.uuid4()),
        "title": f"{alert.get('tactic', 'Unknown')} — {alert.get('technique_id', 'T????')}",
        "severity": severity,
        "status": "new",
        "technique_id": alert.get("technique_id", "T0000"),
        "technique_name": f"Technique {alert.get('technique_id', 'T0000')}",
        "tactic": alert.get("tactic", "Unknown"),
        "confidence": score,
        "llm_rationale": None,  # Filled in by LLM triage async
        "recommended_action": "Investigate immediately",
        "report_md": None,
        "graph_mmd": None,
        "playbook_draft": None,
        "playbook_approved": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "alerts": [alert],
        "ledger": [],
        "_cluster_key": cluster_key,
    }


def _append_ledger(incident: dict[str, Any], action: str, actor: str, payload: dict[str, Any]) -> None:
    """Append a hash-chained ledger entry to the incident."""
    prev_hash = incident["ledger"][-1]["hash"] if incident["ledger"] else "0" * 64
    entry_payload = {"action": action, "actor": actor, "payload": payload}
    new_hash = _hash_chain(prev_hash, entry_payload)
    incident["ledger"].append({
        "seq": len(incident["ledger"]) + 1,
        "hash": new_hash,
        "prev_hash": prev_hash,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "actor": actor,
        "payload": payload,
    })


async def correlate_alert(alert: dict[str, Any], redis_client: Any = None) -> dict[str, Any]:
    """
    Main correlation logic:
    1. Compute cluster key
    2. Find or create incident
    3. Append alert + ledger entry
    4. Publish to WebSocket
    Returns the incident.
    """
    key = _cluster_key(alert)

    if key in _clusters and _clusters[key] in _incidents:
        # Append to existing incident
        incident_id = _clusters[key]
        incident = _incidents[incident_id]
        incident["alerts"].append(alert)
        incident["updated_at"] = datetime.now(timezone.utc).isoformat()
        _append_ledger(incident, "alert_correlated", "system", {"alert_id": alert.get("alert_id")})
        print(f"[Correlation] Appended alert to incident {incident_id[:8]}")
    else:
        # Create new incident
        incident = _build_incident(alert, key)
        incident_id = incident["id"]
        _incidents[incident_id] = incident
        _clusters[key] = incident_id
        _append_ledger(incident, "incident_created", "system", {"alert_id": alert.get("alert_id")})
        print(f"[Correlation] Created incident {incident_id[:8]} for cluster {key[:40]}")

    # Publish alert to WebSocket clients
    await _publish_to_ws(redis_client, {**alert, "incident_id": incident["id"]})

    return incident


# ── Kafka Consumer Loop ──────────────────────────────────────────────────────

async def run_correlation_loop() -> None:
    """
    Continuously consume alerts.raw from Redpanda and correlate them.
    Run this as a background task alongside the FastAPI server.
    """
    redis_client = None
    if REDIS_AVAILABLE:
        redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)

    if not KAFKA_AVAILABLE:
        print("[Correlation] kafka-python not available — running in stub mode")
        # In stub mode, just stay alive
        while True:
            await asyncio.sleep(60)
        return

    print("[Correlation] Starting Kafka consumer for alerts.raw")
    consumer = KafkaConsumer(
        "alerts.raw",
        bootstrap_servers=KAFKA_BOOTSTRAP,
        auto_offset_reset="latest",
        group_id="soc-correlation",
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
    )

    try:
        for msg in consumer:
            alert = msg.value
            await correlate_alert(alert, redis_client)
    except Exception as e:
        print(f"[Correlation] Consumer error: {e}")
    finally:
        consumer.close()
        if redis_client:
            await redis_client.aclose()
