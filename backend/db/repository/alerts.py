"""
SOC Triager — Alerts Repository.

Async CRUD operations for the alerts table.
Translates between AlertORM (SQLAlchemy) and dict-based API responses
to preserve the existing service interface during the migration.
"""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.orm_models import AlertORM


# ── Helpers ───────────────────────────────────────────────────────────────────

def _orm_to_dict(alert: AlertORM) -> dict[str, Any]:
    """Convert AlertORM to the dict shape used by the existing API layer."""
    return {
        "id": alert.id,
        "incident_id": alert.incident_id,
        "severity": alert.severity,
        "timestamp": alert.timestamp.isoformat() if alert.timestamp else None,
        "source_ip": alert.source_ip,
        "destination_host": alert.destination_host,
        "user_name": alert.user_name,
        "technique_id": alert.technique_id,
        "tactic": alert.tactic,
        "anomaly_score": float(alert.anomaly_score) if alert.anomaly_score is not None else 0.0,
        "top_features": alert.top_features or [],
        "status": alert.status,
        "assignee": alert.assignee,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
    }


# ── Read ──────────────────────────────────────────────────────────────────────

async def get_alerts(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 50,
    status: Optional[str] = None,
    severity: Optional[str] = None,
) -> dict[str, Any]:
    """Paginated alert list with optional filters. Mirrors existing svc.get_alerts() interface."""
    query = select(AlertORM).order_by(AlertORM.created_at.desc())
    count_query = select(func.count(AlertORM.id))

    if status:
        query = query.where(AlertORM.status == status)
        count_query = count_query.where(AlertORM.status == status)
    if severity:
        query = query.where(AlertORM.severity == severity)
        count_query = count_query.where(AlertORM.severity == severity)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    alerts = result.scalars().all()

    return {
        "items": [_orm_to_dict(a) for a in alerts],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def get_alert_by_id(db: AsyncSession, alert_id: str) -> Optional[dict[str, Any]]:
    """Fetch a single alert by ID."""
    result = await db.execute(select(AlertORM).where(AlertORM.id == alert_id))
    alert = result.scalar_one_or_none()
    return _orm_to_dict(alert) if alert else None


# ── Write ─────────────────────────────────────────────────────────────────────

async def create_alert(db: AsyncSession, alert_data: dict[str, Any]) -> dict[str, Any]:
    """Insert a new alert row. Uses ON CONFLICT DO NOTHING via alert_data['id'] if provided."""
    alert_id = alert_data.get("id") or str(uuid4())

    timestamp_raw = alert_data.get("timestamp", datetime.now(UTC).isoformat())
    if isinstance(timestamp_raw, str):
        timestamp = datetime.fromisoformat(timestamp_raw.replace("Z", "+00:00"))
    else:
        timestamp = timestamp_raw

    alert = AlertORM(
        id=alert_id,
        incident_id=alert_data.get("incident_id"),
        severity=alert_data.get("severity", "medium"),
        timestamp=timestamp,
        source_ip=alert_data.get("source_ip"),
        destination_host=alert_data.get("destination_host"),
        user_name=alert_data.get("user_name"),
        technique_id=alert_data.get("technique_id", "T0000"),
        tactic=alert_data.get("tactic", "unknown"),
        anomaly_score=alert_data.get("anomaly_score", 0.0),
        top_features=alert_data.get("top_features"),
        status=alert_data.get("status", "new"),
        assignee=alert_data.get("assignee"),
    )
    db.add(alert)
    await db.flush()
    return _orm_to_dict(alert)


async def update_alert_status(
    db: AsyncSession, alert_id: str, new_status: str, assignee: Optional[str] = None
) -> Optional[dict[str, Any]]:
    """Update alert status and optionally assignee."""
    values: dict[str, Any] = {"status": new_status}
    if assignee is not None:
        values["assignee"] = assignee

    await db.execute(
        update(AlertORM).where(AlertORM.id == alert_id).values(**values)
    )
    return await get_alert_by_id(db, alert_id)


async def link_alert_to_incident(
    db: AsyncSession, alert_id: str, incident_id: str
) -> None:
    """Associate an alert with an incident."""
    await db.execute(
        update(AlertORM)
        .where(AlertORM.id == alert_id)
        .values(incident_id=incident_id)
    )
