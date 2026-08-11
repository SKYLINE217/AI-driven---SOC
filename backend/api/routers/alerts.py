"""Alerts router — GET /api/alerts, POST /api/alerts/{id}/status."""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from backend.api.auth_middleware import get_current_user, require_role
import backend.api.incident_service as svc

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class StatusUpdate(BaseModel):
    status: str  # new | ack | escalated | closed


@router.get("")
async def list_alerts(
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    entity_search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _user: dict = Depends(get_current_user),
):
    """Return paginated, filterable alert list."""
    return svc.get_alerts(
        severity=severity,
        status=status,
        entity_search=entity_search,
        page=page,
        page_size=page_size,
    )


@router.get("/{alert_id}")
async def get_alert(alert_id: str, _user: dict = Depends(get_current_user)):
    alert = svc.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.post("/{alert_id}/status")
async def update_alert_status(
    alert_id: str,
    body: StatusUpdate,
    user: dict = Depends(require_role("analyst")),
):
    """Acknowledge / escalate / close an alert. Minimum role: analyst."""
    valid_statuses = {"new", "ack", "escalated", "closed"}
    if body.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    alert = svc.update_alert_status(alert_id, body.status, actor=user.get("sub", "unknown"))
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert
