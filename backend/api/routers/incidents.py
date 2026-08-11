"""Incidents router — full incident lifecycle endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.api.auth_middleware import get_current_user, require_role
import backend.api.incident_service as svc

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


class StatusUpdate(BaseModel):
    status: str


@router.get("")
async def list_incidents(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _user: dict = Depends(get_current_user),
):
    return svc.get_incidents(page=page, page_size=page_size)


@router.get("/{incident_id}")
async def get_incident(incident_id: str, _user: dict = Depends(get_current_user)):
    incident = svc.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.get("/{incident_id}/ledger")
async def get_ledger(incident_id: str, _user: dict = Depends(get_current_user)):
    """Return the append-only hash-chained audit ledger for an incident."""
    incident = svc.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return svc.get_incident_ledger(incident_id)


@router.post("/{incident_id}/status")
async def update_incident_status(
    incident_id: str,
    body: StatusUpdate,
    user: dict = Depends(require_role("analyst")),
):
    """Update incident status. Minimum role: analyst."""
    incident = svc.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    valid_statuses = {"new", "ack", "escalated", "closed"}
    if body.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {valid_statuses}")
    incident["status"] = body.status
    from datetime import datetime, UTC
    incident["updated_at"] = datetime.now(UTC).isoformat()
    return incident


@router.post("/{incident_id}/approve")
async def approve_playbook(
    incident_id: str,
    user: dict = Depends(require_role("approver")),
):
    """
    Approve the containment playbook for ops execution.
    RBAC: Approver role required (enforced server-side — UI also disables the button
    for Analysts/Senior Analysts, but this endpoint is the real security control).
    """
    ok = svc.approve_playbook(incident_id, actor=user.get("sub", "unknown"))
    if not ok:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"approved": True, "incident_id": incident_id, "approved_by": user.get("sub")}


@router.get("/{incident_id}/report.md", response_class=None)
async def get_report(incident_id: str, _user: dict = Depends(get_current_user)):
    """Return the generated Markdown incident report."""
    from fastapi.responses import PlainTextResponse
    incident = svc.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return PlainTextResponse(incident.get("report_md", "# No report generated yet."), media_type="text/markdown")


@router.get("/{incident_id}/graph.mmd", response_class=None)
async def get_graph(incident_id: str, _user: dict = Depends(get_current_user)):
    """Return the Mermaid attack graph definition."""
    from fastapi.responses import PlainTextResponse
    incident = svc.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return PlainTextResponse(incident.get("graph_mmd", "graph LR\n  A --> B"), media_type="text/plain")


@router.get("/{incident_id}/playbook")
async def get_playbook(incident_id: str, _user: dict = Depends(get_current_user)):
    """Return the Ansible/firewall containment playbook draft."""
    incident = svc.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {
        "incident_id": incident_id,
        "playbook_draft": incident.get("playbook_draft", "# No playbook generated."),
        "playbook_approved": incident.get("playbook_approved", False),
        "playbook_approved_by": incident.get("playbook_approved_by"),
    }
