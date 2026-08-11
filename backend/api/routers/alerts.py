"""Alerts router — GET /alerts, POST /alerts/bulk-ack, POST /alerts/bulk-assign"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Query, Depends
from pydantic import BaseModel

from backend.api.deps import get_current_claims

router = APIRouter()


# ── Mock data ─────────────────────────────────────────────────────────────────

def _mock_alerts(count: int = 20) -> list[dict]:
    techniques = [
        ("T1110", "Brute Force: Password Guessing", "Credential Access", "critical"),
        ("T1059", "Command and Scripting Interpreter", "Execution", "high"),
        ("T1190", "Exploit Public-Facing Application", "Initial Access", "high"),
        ("T1021", "Remote Services", "Lateral Movement", "medium"),
        ("T1041", "Exfiltration Over C2 Channel", "Exfiltration", "critical"),
    ]
    statuses = ["new", "ack", "escalated", "closed"]
    ips = ["192.168.1.50", "10.0.0.15", "172.16.0.22", "203.0.113.44"]
    hosts = ["DC-01", "DB-01", "WEB-01", "MAIL-02", "FILE-03"]
    users = ["admin", "svc_backup", "jdoe", "svc_account", "root"]

    alerts = []
    for i in range(count):
        technique_id, technique_name, tactic, severity = techniques[i % len(techniques)]
        alerts.append({
            "id": str(uuid.uuid4()),
            "incident_id": f"inc-{100 + i}",
            "severity": severity,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "entity": {
                "host": hosts[i % len(hosts)],
                "user": users[i % len(users)],
                "source_ip": ips[i % len(ips)],
            },
            "technique_id": technique_id,
            "technique_name": technique_name,
            "tactic": tactic,
            "anomaly_score": round(0.5 + (i % 5) * 0.1, 2),
            "score_history": [0.1, 0.2, round(0.5 + (i % 5) * 0.1, 2)],
            "top_features": [
                {"name": "failed_auth_ratio", "contribution": 0.5},
                {"name": "event_count_1m", "contribution": 0.3},
            ],
            "status": statuses[i % len(statuses)],
            "assignee": "analyst@example.com" if i % 3 == 1 else None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    return alerts


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("")
async def get_alerts(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    severity: Optional[str] = None,
    status: Optional[str] = None,
    technique: Optional[str] = None,
    entity: Optional[str] = None,
    _claims: dict = Depends(get_current_claims),
):
    alerts = _mock_alerts(50)

    # Apply filters
    if severity:
        svs = severity.split(",")
        alerts = [a for a in alerts if a["severity"] in svs]
    if status:
        sts = status.split(",")
        alerts = [a for a in alerts if a["status"] in sts]
    if technique:
        techs = technique.split(",")
        alerts = [a for a in alerts if a["technique_id"] in techs]
    if entity:
        alerts = [
            a for a in alerts
            if entity.lower() in str(a["entity"]).lower()
        ]

    total = len(alerts)
    start = (page - 1) * limit
    return {"total": total, "page": page, "limit": limit, "alerts": alerts[start:start + limit]}


class BulkRequest(BaseModel):
    alert_ids: list[str]


@router.post("/bulk-ack")
async def bulk_ack(body: BulkRequest, _claims: dict = Depends(get_current_claims)):
    return {"acknowledged": len(body.alert_ids), "alert_ids": body.alert_ids}


@router.post("/bulk-assign")
async def bulk_assign(body: BulkRequest, _claims: dict = Depends(get_current_claims)):
    return {"assigned": len(body.alert_ids), "assignee": _claims.get("sub")}
