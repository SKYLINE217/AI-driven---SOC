"""
Legacy in-memory incident store — preserved for the original test suite.

The converted CLI application uses the SQLite-backed implementation in
`services.incident_service`. This module implements the exact public API
(expected by `tests/test_incident_service.py`) of the original microservice
incident service so the existing tests can continue to pass without changes.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ── In-memory stores ─────────────────────────────────────────────────────────
# NOTE: Tests import these names directly from the module, so they must exist at
# module scope and be plain mutable dicts/lists.

_alerts: Dict[str, Dict[str, Any]] = {}
_incidents: Dict[str, Dict[str, Any]] = {}
_ledger: List[Dict[str, Any]] = []


# ── Helpers ──────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ledger_hash(prev_hash: str, payload: Dict[str, Any]) -> str:
    entry_json = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256((prev_hash + entry_json).encode()).hexdigest()


def _last_hash_for(incident_id: str) -> str:
    for entry in reversed(_ledger):
        if entry.get("incident_id") == incident_id:
            return entry["hash"]
    return "0" * 64


def _append_ledger_entry(incident_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    prev = _last_hash_for(incident_id)
    entry_hash = _ledger_hash(prev, payload)
    entry = {
        "id": str(uuid.uuid4()),
        "incident_id": incident_id,
        "prev_hash": prev,
        "hash": entry_hash,
        "payload": payload,
        "timestamp": _now_iso(),
    }
    _ledger.append(entry)
    return entry


# ── Public API ───────────────────────────────────────────────────────────────

def seed_mock_data() -> None:
    """Populate the in-memory stores with canned fixtures."""
    now = _now_iso()

    # ── Alerts (4+) ──
    alerts_fixture: List[Dict[str, Any]] = [
        {
            "id": "alt_a001",
            "entity": {"ip": "203.0.113.44", "host": "prod-db-03", "user": None},
            "severity": "critical",
            "status": "new",
            "anomaly_score": 0.92,
            "technique_id": "T1110.001",
            "source_type": "auth_log",
            "created_at": now,
        },
        {
            "id": "alt_a002",
            "entity": {"ip": "10.0.4.12", "host": "prod-db-03", "user": "svc-backup"},
            "severity": "high",
            "status": "new",
            "anomaly_score": 0.81,
            "technique_id": "T1021.004",
            "source_type": "auth_log",
            "created_at": now,
        },
        {
            "id": "alt_a003",
            "entity": {"ip": "192.0.2.111", "host": "prod-web-02", "user": None},
            "severity": "medium",
            "status": "new",
            "anomaly_score": 0.66,
            "technique_id": "T1046",
            "source_type": "syslog",
            "created_at": now,
        },
        {
            "id": "alt_a004",
            "entity": {"ip": "198.51.100.77", "host": "prod-cache-01", "user": None},
            "severity": "critical",
            "status": "new",
            "anomaly_score": 0.95,
            "technique_id": "T1498",
            "source_type": "cicids",
            "created_at": now,
        },
    ]
    for alert in alerts_fixture:
        _alerts[alert["id"]] = alert

    # ── Incidents (2+) ──
    incident_a = {
        "id": "inc_a001",
        "title": "Brute-force SSH attack against prod-db-03",
        "severity": "critical",
        "status": "open",
        "confidence": 0.91,
        "technique_id": "T1110.001",
        "technique_name": "Brute Force: Password Guessing",
        "tactic": "Credential Access",
        "entity": {"ip": "203.0.113.44", "host": "prod-db-03"},
        "alerts": ["alt_a001", "alt_a002"],
        "rationale": "20 failed SSH attempts in 90 seconds from external IP.",
        "recommended_action": "Block attacker IP at perimeter firewall.",
        "playbook": "playbook_t1110.yml",
        "playbook_approved": False,
        "playbook_approved_by": None,
        "created_at": now,
        "updated_at": now,
    }
    incident_b = {
        "id": "inc_a002",
        "title": "Possible DDoS against customer-records S3 bucket",
        "severity": "high",
        "status": "investigating",
        "confidence": 0.78,
        "technique_id": "T1498",
        "technique_name": "Network Denial of Service",
        "tactic": "Impact",
        "entity": {"ip": "198.51.100.77", "host": "prod-cache-01"},
        "alerts": ["alt_a004"],
        "rationale": "Flow bytes exceed 95th percentile for 5 consecutive minutes.",
        "recommended_action": "Activate upstream DDoS scrubbing.",
        "playbook": "playbook_t1498.yml",
        "playbook_approved": False,
        "playbook_approved_by": None,
        "created_at": now,
        "updated_at": now,
    }
    for inc in (incident_a, incident_b):
        _incidents[inc["id"]] = inc

    # ── Ledger entries for inc_a001 (hash-chain integrity tested) ──
    payload_created = {
        "action": "incident_created",
        "incident_id": "inc_a001",
        "actor": "ml_triage_pipeline",
        "severity": "critical",
        "technique": "T1110.001",
    }
    _append_ledger_entry("inc_a001", payload_created)

    payload_clustered = {
        "action": "alert_associated",
        "incident_id": "inc_a001",
        "alert_id": "alt_a001",
        "actor": "clustering_engine",
    }
    _append_ledger_entry("inc_a001", payload_clustered)


# ── Alert helpers ────────────────────────────────────────────────────────────

def _alert_matches(alert: Dict[str, Any], *,
                   severity: Optional[str],
                   status: Optional[str],
                   entity_search: Optional[str]) -> bool:
    if severity and alert.get("severity") != severity:
        return False
    if status and alert.get("status") != status:
        return False
    if entity_search:
        entity_str = str(alert.get("entity", {})).lower()
        if entity_search.lower() not in entity_str:
            return False
    return True


def get_alerts(*,
               page: int = 1,
               page_size: int = 50,
               severity: Optional[str] = None,
               status: Optional[str] = None,
               entity_search: Optional[str] = None) -> Dict[str, Any]:
    matching = [
        a for a in _alerts.values()
        if _alert_matches(a, severity=severity, status=status, entity_search=entity_search)
    ]
    matching.sort(key=lambda item: item.get("created_at", ""), reverse=True)

    total = len(matching)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "total": total,
        "items": matching[start:end],
        "page": page,
        "page_size": page_size,
    }


def get_alert(alert_id: str) -> Optional[Dict[str, Any]]:
    return _alerts.get(alert_id)


def update_alert_status(alert_id: str, new_status: str,
                        actor: str = "system") -> Optional[Dict[str, Any]]:
    alert = _alerts.get(alert_id)
    if alert is None:
        return None
    alert["status"] = new_status
    alert["updated_at"] = _now_iso()
    alert["status_updated_by"] = actor
    _append_ledger_entry(
        alert.get("incident_id", "inc_orphan"),
        {
            "action": "alert_status_updated",
            "alert_id": alert_id,
            "from": alert.get("status"),
            "to": new_status,
            "actor": actor,
        },
    )
    return alert


# ── Incident helpers ─────────────────────────────────────────────────────────

def get_incidents(*,
                  page: int = 1,
                  page_size: int = 50,
                  severity: Optional[str] = None,
                  status: Optional[str] = None) -> Dict[str, Any]:
    items = list(_incidents.values())
    if severity:
        items = [i for i in items if i.get("severity") == severity]
    if status:
        items = [i for i in items if i.get("status") == status]
    items.sort(key=lambda item: item.get("created_at", ""), reverse=True)

    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "total": total,
        "items": items[start:end],
        "page": page,
        "page_size": page_size,
    }


def get_incident(incident_id: str) -> Optional[Dict[str, Any]]:
    return _incidents.get(incident_id)


def get_incident_ledger(incident_id: str) -> List[Dict[str, Any]]:
    return [e for e in _ledger if e.get("incident_id") == incident_id]


def approve_playbook(incident_id: str, actor: str) -> bool:
    incident = _incidents.get(incident_id)
    if incident is None:
        return False
    incident["playbook_approved"] = True
    incident["playbook_approved_by"] = actor
    incident["updated_at"] = _now_iso()
    _append_ledger_entry(
        incident_id,
        {
            "action": "playbook_approved",
            "incident_id": incident_id,
            "actor": actor,
        },
    )
    return True
