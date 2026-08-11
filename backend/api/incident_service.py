"""
Incident Service — in-memory store + WebSocket broadcaster.

Day 3: Uses in-memory dicts (thread-safe via asyncio).
Day 4: Swap for Postgres with SQLAlchemy (same interface preserved).

Responsibilities:
  1. Maintain canonical Alert and Incident stores.
  2. process_alert_cluster() → MITRE mapping + LLM triage → create/update incident → fan-out.
  3. Broadcast new alerts to all connected WebSocket clients via Redis Pub/Sub (stub → direct fan-out for Day 3).
  4. Seed mock data on startup so the UI is non-empty immediately.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from datetime import datetime, UTC
from typing import Any
import random

from backend.models import Severity, AlertStatus, TriageStatus
from backend.mitre.alert_clustering import cluster_events
from backend.mitre.mapping_engine import MitreRuleEngine, get_technique

rule_engine = MitreRuleEngine()

# ─── In-Memory Stores ────────────────────────────────────────────────────────

# alerts: id → alert dict
_alerts: dict[str, dict[str, Any]] = {}

# incidents: id → incident dict
_incidents: dict[str, dict[str, Any]] = {}

# incident_ledger: list of ledger entries (append-only)
_ledger: list[dict[str, Any]] = []

# WebSocket connections: set of asyncio queues, one per connected client
_ws_queues: set[asyncio.Queue] = set()


# ─── WebSocket Fan-out ───────────────────────────────────────────────────────

def register_ws_client(queue: asyncio.Queue) -> None:
    """Register a new WebSocket client connection."""
    _ws_queues.add(queue)


def unregister_ws_client(queue: asyncio.Queue) -> None:
    """Remove a disconnected WebSocket client."""
    _ws_queues.discard(queue)


async def _broadcast(message: dict[str, Any]) -> None:
    """Fan out a JSON-serializable message to all connected WS clients."""
    payload = json.dumps(message, default=str)
    dead: list[asyncio.Queue] = []
    for q in list(_ws_queues):
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        _ws_queues.discard(q)


# ─── Ledger Helper ───────────────────────────────────────────────────────────

def _append_ledger(incident_id: str, action: str, actor: str, payload: dict[str, Any]) -> dict[str, Any]:
    seq = len(_ledger)
    prev_hash = _ledger[-1]["hash"] if _ledger else "0" * 64
    entry_json = json.dumps(payload, sort_keys=True, default=str)
    entry_hash = hashlib.sha256((prev_hash + entry_json).encode()).hexdigest()
    entry = {
        "seq": seq,
        "incident_id": incident_id,
        "hash": entry_hash,
        "prev_hash": prev_hash,
        "timestamp": datetime.now(UTC).isoformat(),
        "action": action,
        "actor": actor,
        "payload": payload,
    }
    _ledger.append(entry)
    return entry


# ─── Core Processing ─────────────────────────────────────────────────────────

async def process_alert_cluster(
    cluster: dict[str, Any],
    anomaly_score: float,
    top_features: dict[str, Any],
) -> dict[str, Any]:
    """
    Run MITRE candidate generation + LLM triage for a cluster, create an alert+incident,
    and broadcast to WebSocket clients.

    Returns the created alert dict.
    """
    from backend.llm.triage_client import triage_event_cluster  # lazy import

    events = cluster.get("events", [])
    event_contexts = cluster.get("event_contexts", events)

    # 1. Get candidate techniques from rule engine
    merged_context: dict[str, Any] = {}
    for ctx in event_contexts:
        for k, v in ctx.items():
            if v and not merged_context.get(k):
                merged_context[k] = v
    merged_context["anomaly_score"] = anomaly_score
    candidates = rule_engine.get_candidate_techniques(merged_context)

    # 2. LLM triage (runs in a thread to not block the event loop)
    loop = asyncio.get_event_loop()
    triage = await loop.run_in_executor(
        None,
        triage_event_cluster,
        events,
        anomaly_score,
        top_features,
        candidates,
    )

    # 3. Enrich with MITRE STIX data
    mitre_info = get_technique(triage.technique_id)

    # 4. Create alert
    alert_id = str(uuid.uuid4())
    incident_id = f"inc_{uuid.uuid4().hex[:8]}"
    now = datetime.now(UTC).isoformat()
    entity = cluster.get("entity", "unknown")

    alert: dict[str, Any] = {
        "id": alert_id,
        "incident_id": incident_id,
        "severity": triage.severity,
        "timestamp": now,
        "entity": {"source_ip" if "." in entity else "host": entity},
        "technique_id": triage.technique_id,
        "technique_name": triage.technique_name or mitre_info.get("name", ""),
        "tactic": triage.tactic or mitre_info.get("tactic", ""),
        "anomaly_score": round(anomaly_score, 3),
        "score_history": [round(anomaly_score * r, 3) for r in [0.1, 0.2, 0.3, 0.5, 0.8, 1.0]],
        "status": "new",
        "assignee": None,
        "created_at": now,
    }
    _alerts[alert_id] = alert

    # 5. Create incident
    incident: dict[str, Any] = {
        "id": incident_id,
        "title": f"{triage.tactic} — {entity}",
        "severity": triage.severity,
        "status": "new",
        "technique_id": triage.technique_id,
        "technique_name": triage.technique_name or mitre_info.get("name", ""),
        "tactic": triage.tactic or mitre_info.get("tactic", ""),
        "confidence": triage.confidence,
        "llm_rationale": triage.rationale,
        "recommended_action": triage.recommended_immediate_action,
        "mitre_description": mitre_info.get("description", ""),
        "entities": [{"role": "attacker", "ip": entity if "." in entity else None, "host": entity if "." not in entity else None}],
        "alerts": [alert_id],
        "playbook_approved": False,
        "created_at": now,
        "updated_at": now,
    }
    _incidents[incident_id] = incident
    _append_ledger(incident_id, "INCIDENT_CREATED", "system", {"severity": triage.severity, "technique": triage.technique_id})

    # 6. Broadcast
    await _broadcast({"type": "new_alert", "alert": alert})

    return alert


# ─── CRUD API Helpers ─────────────────────────────────────────────────────────

def get_alerts(
    severity: str | None = None,
    status: str | None = None,
    entity_search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    items = list(_alerts.values())
    # Filter
    if severity:
        items = [a for a in items if a["severity"] == severity]
    if status:
        items = [a for a in items if a["status"] == status]
    if entity_search:
        s = entity_search.lower()
        items = [a for a in items if any(
            s in str(v).lower() for v in a.get("entity", {}).values()
        )]
    # Sort newest first
    items.sort(key=lambda a: a["created_at"], reverse=True)
    total = len(items)
    start = (page - 1) * page_size
    return {"total": total, "page": page, "page_size": page_size, "items": items[start: start + page_size]}


def get_alert(alert_id: str) -> dict[str, Any] | None:
    return _alerts.get(alert_id)


def update_alert_status(alert_id: str, new_status: str, actor: str) -> dict[str, Any] | None:
    alert = _alerts.get(alert_id)
    if not alert:
        return None
    alert["status"] = new_status
    incident_id = alert.get("incident_id")
    if incident_id and incident_id in _incidents:
        _incidents[incident_id]["status"] = new_status
        _incidents[incident_id]["updated_at"] = datetime.now(UTC).isoformat()
        _append_ledger(incident_id, f"STATUS_{new_status.upper()}", actor, {"status": new_status})
    return alert


def get_incidents(page: int = 1, page_size: int = 50) -> dict[str, Any]:
    items = sorted(_incidents.values(), key=lambda i: i["created_at"], reverse=True)
    total = len(items)
    start = (page - 1) * page_size
    return {"total": total, "page": page, "page_size": page_size, "items": items[start: start + page_size]}


def get_incident(incident_id: str) -> dict[str, Any] | None:
    return _incidents.get(incident_id)


def get_incident_ledger(incident_id: str) -> list[dict[str, Any]]:
    return [e for e in _ledger if e["incident_id"] == incident_id]


def approve_playbook(incident_id: str, actor: str) -> bool:
    incident = _incidents.get(incident_id)
    if not incident:
        return False
    incident["playbook_approved"] = True
    incident["playbook_approved_by"] = actor
    incident["updated_at"] = datetime.now(UTC).isoformat()
    _append_ledger(incident_id, "PLAYBOOK_APPROVED", actor, {"approved_by": actor})
    return True


# ─── Seed Mock Data ───────────────────────────────────────────────────────────

def seed_mock_data() -> None:
    """Seed the in-memory stores with realistic mock data for immediate UI display."""

    mock_alerts_data = [
        {
            "id": "a001",
            "incident_id": "inc_a001",
            "severity": "critical",
            "timestamp": "2026-08-11T06:12:00Z",
            "entity": {"source_ip": "203.0.113.44"},
            "technique_id": "T1110.001",
            "technique_name": "Brute Force: Password Guessing",
            "tactic": "Credential Access",
            "anomaly_score": 0.94,
            "score_history": [0.1, 0.15, 0.3, 0.55, 0.8, 0.94],
            "status": "new",
            "assignee": None,
            "created_at": "2026-08-11T06:12:00Z",
        },
        {
            "id": "a002",
            "incident_id": "inc_a002",
            "severity": "high",
            "timestamp": "2026-08-11T06:08:00Z",
            "entity": {"host": "prod-db-03"},
            "technique_id": "T1041",
            "technique_name": "Exfiltration Over C2 Channel",
            "tactic": "Exfiltration",
            "anomaly_score": 0.82,
            "score_history": [0.05, 0.05, 0.1, 0.3, 0.65, 0.82],
            "status": "escalated",
            "assignee": "analyst@example.com",
            "created_at": "2026-08-11T06:08:00Z",
        },
        {
            "id": "a003",
            "incident_id": "inc_a003",
            "severity": "high",
            "timestamp": "2026-08-11T05:55:00Z",
            "entity": {"source_ip": "10.0.2.15"},
            "technique_id": "T1046",
            "technique_name": "Network Service Discovery",
            "tactic": "Discovery",
            "anomaly_score": 0.78,
            "score_history": [0.2, 0.25, 0.35, 0.5, 0.7, 0.78],
            "status": "ack",
            "assignee": "senior@example.com",
            "created_at": "2026-08-11T05:55:00Z",
        },
        {
            "id": "a004",
            "incident_id": "inc_a004",
            "severity": "medium",
            "timestamp": "2026-08-11T05:30:00Z",
            "entity": {"user": "svc-backup"},
            "technique_id": "T1021.004",
            "technique_name": "Remote Services: SSH",
            "tactic": "Lateral Movement",
            "anomaly_score": 0.65,
            "score_history": [0.2, 0.2, 0.3, 0.4, 0.55, 0.65],
            "status": "closed",
            "assignee": "analyst@example.com",
            "created_at": "2026-08-11T05:30:00Z",
        },
        {
            "id": "a005",
            "incident_id": "inc_a005",
            "severity": "critical",
            "timestamp": "2026-08-11T04:00:00Z",
            "entity": {"source_ip": "198.51.100.7"},
            "technique_id": "T1498",
            "technique_name": "Network Denial of Service",
            "tactic": "Impact",
            "anomaly_score": 0.99,
            "score_history": [0.05, 0.15, 0.6, 0.9, 0.97, 0.99],
            "status": "new",
            "assignee": None,
            "created_at": "2026-08-11T04:00:00Z",
        },
        {
            "id": "a006",
            "incident_id": "inc_a006",
            "severity": "high",
            "timestamp": "2026-08-11T03:30:00Z",
            "entity": {"user": "admin"},
            "technique_id": "T1078",
            "technique_name": "Valid Accounts (Impossible Travel)",
            "tactic": "Initial Access",
            "anomaly_score": 0.88,
            "score_history": [0.1, 0.1, 0.2, 0.5, 0.75, 0.88],
            "status": "new",
            "assignee": None,
            "created_at": "2026-08-11T03:30:00Z",
        },
    ]

    mock_incidents_data = [
        {
            "id": "inc_a001",
            "title": "Brute-Force Credential Access — 203.0.113.44",
            "severity": "critical",
            "status": "new",
            "technique_id": "T1110.001",
            "technique_name": "Brute Force: Password Guessing",
            "tactic": "Credential Access",
            "confidence": 0.94,
            "llm_rationale": "17 failed SSH auth attempts from 203.0.113.44 against 4 distinct service accounts within 90 seconds. The consistent failure pattern with high frequency against port 22 is consistent with automated password guessing. Source IP geo-lookup indicates a commercial cloud provider exit node (ASN 48693) frequently associated with botnet activity.",
            "recommended_action": "Block source IP 203.0.113.44 at edge firewall. Force credential rotation for targeted accounts: root, svc-backup, ubuntu, ec2-user. Enable AWS GuardDuty SSH brute-force finding for this VPC.",
            "mitre_description": "Adversaries may use brute force techniques to gain access to accounts when passwords are unknown or when password hashes are obtained.",
            "entities": [
                {"role": "attacker", "ip": "203.0.113.44", "host": None, "user": None, "geo_country": "RU"},
                {"role": "victim", "ip": None, "host": "prod-db-03", "user": None, "geo_country": None},
            ],
            "alerts": ["a001"],
            "report_md": "## Incident Report\n\n### Timeline\n| Time | Event | Source |\n|---|---|---|\n| 06:12:00 | 17 failed SSH auths | 203.0.113.44 |\n| 06:12:34 | Successful login as root | 203.0.113.44 |\n\n### Entities\n- **Attacker IP**: 203.0.113.44 (RU)\n- **Victim Host**: prod-db-03\n\n### Evidence\n```\nAug 11 06:12:00 prod-db-03 sshd[4521]: Failed password for root from 203.0.113.44 port 54321 ssh2\nAug 11 06:12:01 prod-db-03 sshd[4521]: Failed password for svc-backup from 203.0.113.44 port 54322 ssh2\n...(15 more failures)...\nAug 11 06:12:34 prod-db-03 sshd[4555]: Accepted password for root from 203.0.113.44 port 54399 ssh2\n```\n\n### Recommended Action\nBlock 203.0.113.44 at edge firewall immediately and rotate the root password on prod-db-03.",
            "graph_mmd": "graph LR\n  A[\"Attacker\\n203.0.113.44\\nRU\"] -->|\"17× SSH brute force\"| B[\"prod-db-03\\n:22\"]\n  B -->|\"successful auth (root)\"| C[\"root shell\"]\n  style A fill:#ef4444,color:#fff\n  style B fill:#f97316,color:#fff\n  style C fill:#dc2626,color:#fff",
            "playbook_draft": "---\n# Containment Playbook: Brute-Force SSH (T1110.001)\n# DRAFT — Requires Approver authorization before execution\n# Generated: 2026-08-11T06:12:00Z\n# Incident: inc_a001\n---\n\n- name: Block attacker IP at edge firewall\n  hosts: firewall\n  tasks:\n    - name: Add deny rule for 203.0.113.44\n      iptables:\n        chain: INPUT\n        source: 203.0.113.44\n        jump: DROP\n        comment: \"SOC-AUTO: inc_a001 T1110.001\"\n\n- name: Force credential rotation\n  hosts: prod-db-03\n  tasks:\n    - name: Lock targeted accounts temporarily\n      user:\n        name: \"{{ item }}\"\n        password_lock: yes\n      loop: [root, svc-backup, ubuntu, ec2-user]",
            "playbook_approved": False,
            "created_at": "2026-08-11T06:12:00Z",
            "updated_at": "2026-08-11T06:12:00Z",
        },
        {
            "id": "inc_a002",
            "title": "Data Exfiltration — prod-db-03",
            "severity": "high",
            "status": "escalated",
            "technique_id": "T1041",
            "technique_name": "Exfiltration Over C2 Channel",
            "tactic": "Exfiltration",
            "confidence": 0.82,
            "llm_rationale": "Unusually large outbound data transfer (580 MB) from prod-db-03 to external IP 198.51.100.7 over port 443, occurring outside business hours. Bytes transferred is 40× the 30-day baseline for this host. The transfer occurred following the brute-force incident on the same host, suggesting post-compromise data staging and exfiltration.",
            "recommended_action": "Immediately block outbound traffic from prod-db-03 to 198.51.100.7. Capture a forensic memory image of prod-db-03. Identify and quarantine any processes with external connections. Review database query logs for bulk SELECT operations preceding the transfer.",
            "mitre_description": "Adversaries may steal data by exfiltrating it over an existing command and control channel.",
            "entities": [
                {"role": "victim", "ip": None, "host": "prod-db-03", "user": None, "geo_country": None},
                {"role": "attacker", "ip": "198.51.100.7", "host": None, "user": None, "geo_country": "CN"},
            ],
            "alerts": ["a002"],
            "report_md": "## Incident Report: Data Exfiltration\n\n### Summary\nLarge outbound data transfer detected from prod-db-03 post-compromise.\n\n### Timeline\n| Time | Event | Bytes |\n|---|---|---|\n| 06:05:00 | Outbound connection established | — |\n| 06:08:00 | Transfer complete | 580 MB |\n\n### Recommended Action\nFull network isolation of prod-db-03. Forensic investigation required.",
            "graph_mmd": "graph LR\n  A[\"prod-db-03\"] -->|\"580 MB HTTPS\"| B[\"198.51.100.7\\nCN\"]\n  style A fill:#f97316,color:#fff\n  style B fill:#ef4444,color:#fff",
            "playbook_draft": "---\n# Containment Playbook: Exfiltration Over C2 (T1041)\n# DRAFT — Requires Approver authorization\n---\n\n- name: Block exfil destination\n  hosts: firewall\n  tasks:\n    - name: Block outbound to 198.51.100.7\n      iptables:\n        chain: OUTPUT\n        destination: 198.51.100.7\n        jump: DROP",
            "playbook_approved": True,
            "playbook_approved_by": "approver@example.com",
            "created_at": "2026-08-11T06:08:00Z",
            "updated_at": "2026-08-11T06:15:00Z",
        },
    ]

    for a in mock_alerts_data:
        _alerts[a["id"]] = a

    for inc in mock_incidents_data:
        _incidents[inc["id"]] = inc

    # Seed ledger entries for inc_a001
    _append_ledger("inc_a001", "INCIDENT_CREATED", "system", {"severity": "critical", "technique": "T1110.001"})
    _append_ledger("inc_a001", "STATUS_ESCALATED", "analyst@example.com", {"status": "escalated"})
    _append_ledger("inc_a001", "STATUS_NEW", "system", {"note": "Reverted to new for investigation"})
    _append_ledger("inc_a002", "INCIDENT_CREATED", "system", {"severity": "high", "technique": "T1041"})
    _append_ledger("inc_a002", "PLAYBOOK_APPROVED", "approver@example.com", {"approved_by": "approver@example.com"})
