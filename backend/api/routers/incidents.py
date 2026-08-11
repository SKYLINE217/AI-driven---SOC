"""Incidents router — full mock data with all 5 tabs' data shapes"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from backend.api.deps import get_current_claims, require_role

router = APIRouter()

# ── Mock incident store ───────────────────────────────────────────────────────

MOCK_INCIDENTS = {
    "inc-101": {
        "id": "inc-101",
        "title": "Brute Force Attack — Credential Access",
        "severity": "critical",
        "status": "new",
        "technique_id": "T1110",
        "technique_name": "Brute Force: Password Guessing",
        "tactic": "Credential Access",
        "confidence": 0.95,
        "llm_rationale": (
            "The event cluster shows 847 failed authentication attempts from IP 192.168.1.50 "
            "against DC-01 within a 5-minute window. The time-of-day Z-score (3.2) indicates "
            "this activity occurred outside normal business hours. The failed_auth_ratio of 0.94 "
            "is consistent with automated brute force tooling (Hydra, Medusa pattern). "
            "Confidence: 95% — MITRE ATT&CK T1110.001."
        ),
        "recommended_action": "Block source IP at edge firewall; lock targeted accounts; escalate to Senior Analyst.",
        "report_md": """# Incident Report: Brute Force Attack

## Summary
A sustained brute force attack was detected targeting domain controller DC-01.

## Key Indicators
| IOC | Value |
|-----|-------|
| Source IP | 192.168.1.50 |
| Target Host | DC-01 |
| Target User | admin |
| Duration | 5 min |
| Failed Auths | 847 |

## Timeline
1. **09:14:22** — First failed login attempt
2. **09:14:45** — Alert threshold crossed (50 failures/min)
3. **09:15:01** — Faust agent triggers anomaly score: 0.95
4. **09:15:03** — LLM triage classifies as T1110.001

## Recommended Containment
Execute playbook `T1110-ip-block-account-lockout.yml`
""",
        "graph_mmd": """graph LR
    A[192.168.1.50<br/>Attacker IP] -->|847 failed auth attempts| B[DC-01<br/>Domain Controller]
    B -->|Account targeted| C[admin]
    B -->|Account targeted| D[svc_backup]
    style A fill:#ff4444,color:#fff
    style B fill:#ff8800,color:#fff
    style C fill:#ffcc00,color:#000
    style D fill:#ffcc00,color:#000
""",
        "playbook_draft": """---
- name: T1110 Brute Force Containment — IP Block + Account Lockout
  hosts: edge-firewalls
  become: yes
  vars:
    attacker_ip: "{{ source_ip | default('192.168.1.50') }}"
    target_accounts: "{{ target_users | default(['admin', 'svc_backup']) }}"
  tasks:
    - name: Block attacker IP at perimeter firewall
      iptables:
        chain: INPUT
        source: "{{ attacker_ip }}"
        jump: DROP
        comment: "SOC Triager auto-containment — T1110"
      notify: Save iptables

    - name: Lock targeted user accounts
      user:
        name: "{{ item }}"
        password_lock: yes
      loop: "{{ target_accounts }}"
      register: account_lock_result

    - name: Log containment action to SIEM
      uri:
        url: "http://siem.internal/api/events"
        method: POST
        body_format: json
        body:
          event: "containment_executed"
          technique: "T1110"
          actor: "soc-triager"
          timestamp: "{{ ansible_date_time.iso8601 }}"

  handlers:
    - name: Save iptables
      command: iptables-save > /etc/iptables/rules.v4
""",
        "playbook_approved": False,
        "playbook_approved_by": None,
        "playbook_approved_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
}

MOCK_LEDGERS: dict[str, list[dict]] = {
    "inc-101": [
        {
            "seq": 1,
            "hash": "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
            "prev_hash": "0" * 64,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "incident_created",
            "actor": "system",
            "payload": {"source": "faust-correlation"},
        },
        {
            "seq": 2,
            "hash": "b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef1234567a",
            "prev_hash": "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "llm_triage_complete",
            "actor": "system",
            "payload": {"model": "claude-3-5-sonnet", "latency_ms": 2340},
        },
    ]
}


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("")
async def list_incidents(_claims: dict = Depends(get_current_claims)):
    return {
        "total": len(MOCK_INCIDENTS),
        "page": 1,
        "limit": 50,
        "incidents": list(MOCK_INCIDENTS.values()),
    }


@router.get("/{incident_id}")
async def get_incident(
    incident_id: str, _claims: dict = Depends(get_current_claims)
):
    if incident_id not in MOCK_INCIDENTS:
        raise HTTPException(status_code=404, detail="Incident not found")
    return MOCK_INCIDENTS[incident_id]


@router.get("/{incident_id}/timeline")
async def get_timeline(
    incident_id: str, _claims: dict = Depends(get_current_claims)
):
    return {
        "incident_id": incident_id,
        "events": [
            {"t": datetime.now(timezone.utc).isoformat(), "type": "alert", "summary": "First alert"},
            {"t": datetime.now(timezone.utc).isoformat(), "type": "score", "summary": "Anomaly score: 0.95"},
            {"t": datetime.now(timezone.utc).isoformat(), "type": "triage", "summary": "LLM classified T1110"},
        ],
    }


@router.get("/{incident_id}/ledger")
async def get_ledger(
    incident_id: str, _claims: dict = Depends(get_current_claims)
):
    return {
        "incident_id": incident_id,
        "entries": MOCK_LEDGERS.get(incident_id, []),
    }


@router.get("/{incident_id}/report.md")
async def get_report(
    incident_id: str, _claims: dict = Depends(get_current_claims)
):
    from fastapi.responses import PlainTextResponse
    inc = MOCK_INCIDENTS.get(incident_id)
    if not inc:
        raise HTTPException(status_code=404)
    return PlainTextResponse(inc.get("report_md", "# No report yet"))


@router.get("/{incident_id}/graph.mmd")
async def get_graph(
    incident_id: str, _claims: dict = Depends(get_current_claims)
):
    from fastapi.responses import PlainTextResponse
    inc = MOCK_INCIDENTS.get(incident_id)
    if not inc:
        raise HTTPException(status_code=404)
    return PlainTextResponse(inc.get("graph_mmd", "graph LR\n  A --> B"))


@router.get("/{incident_id}/playbook")
async def get_playbook(
    incident_id: str, _claims: dict = Depends(get_current_claims)
):
    from fastapi.responses import PlainTextResponse
    inc = MOCK_INCIDENTS.get(incident_id)
    if not inc:
        raise HTTPException(status_code=404)
    return PlainTextResponse(inc.get("playbook_draft", "# No playbook yet"))


class StatusRequest(BaseModel):
    status: str
    note: Optional[str] = None


@router.post("/{incident_id}/status")
async def update_status(
    incident_id: str,
    body: StatusRequest,
    _claims: dict = Depends(get_current_claims),
):
    if incident_id not in MOCK_INCIDENTS:
        raise HTTPException(status_code=404)
    MOCK_INCIDENTS[incident_id]["status"] = body.status
    MOCK_INCIDENTS[incident_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
    return MOCK_INCIDENTS[incident_id]


class ApproveRequest(BaseModel):
    note: str


@router.post("/{incident_id}/approve")
async def approve_playbook(
    incident_id: str,
    body: ApproveRequest,
    claims: dict = Depends(require_role("approver")),
):
    if incident_id not in MOCK_INCIDENTS:
        raise HTTPException(status_code=404)

    inc = MOCK_INCIDENTS[incident_id]
    inc["playbook_approved"] = True
    inc["playbook_approved_by"] = claims.get("sub")
    inc["playbook_approved_at"] = datetime.now(timezone.utc).isoformat()

    # Append ledger entry
    ledger = MOCK_LEDGERS.setdefault(incident_id, [])
    prev_hash = ledger[-1]["hash"] if ledger else "0" * 64
    import hashlib, json as _json
    payload = {"approver": claims.get("sub"), "note": body.note}
    new_hash = hashlib.sha256(f"{prev_hash}{_json.dumps(payload)}".encode()).hexdigest()
    ledger.append({
        "seq": len(ledger) + 1,
        "hash": new_hash,
        "prev_hash": prev_hash,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": "playbook_approved",
        "actor": claims.get("sub"),
        "payload": payload,
    })

    return {
        "incident_id": incident_id,
        "approved": True,
        "approved_by": claims.get("sub"),
        "ledger_seq": len(ledger),
    }
