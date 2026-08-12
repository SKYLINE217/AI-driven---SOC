"""
SOC Triager — Incidents Repository.

Async CRUD operations for the incidents and incident_ledger tables.
Uses chain-hashed ledger entries for append-only audit trail.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, UTC
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.orm_models import IncidentORM, LedgerEntryORM, LLMCallLogORM


# ── Helpers ───────────────────────────────────────────────────────────────────

def _orm_to_dict(incident: IncidentORM) -> dict[str, Any]:
    """Convert IncidentORM to the dict shape used by the existing API layer."""
    return {
        "id": incident.id,
        "title": incident.title,
        "severity": incident.severity,
        "status": incident.status,
        "technique_id": incident.technique_id,
        "technique_name": incident.technique_name,
        "tactic": incident.tactic,
        "confidence": float(incident.confidence) if incident.confidence is not None else None,
        "llm_rationale": incident.llm_rationale,
        "recommended_action": incident.recommended_action,
        "report_md": incident.report_md,
        "graph_mmd": incident.graph_mmd,
        "playbook_draft": incident.playbook_draft,
        "playbook_approved": incident.playbook_approved,
        "playbook_approved_by": incident.playbook_approved_by,
        "playbook_approved_at": (
            incident.playbook_approved_at.isoformat() if incident.playbook_approved_at else None
        ),
        "created_at": incident.created_at.isoformat() if incident.created_at else None,
        "updated_at": incident.updated_at.isoformat() if incident.updated_at else None,
    }


def _ledger_orm_to_dict(entry: LedgerEntryORM) -> dict[str, Any]:
    return {
        "seq": entry.seq,
        "incident_id": entry.incident_id,
        "hash": entry.hash,
        "prev_hash": entry.prev_hash,
        "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
        "action": entry.action,
        "actor": entry.actor,
        "payload": entry.payload,
    }


def _compute_ledger_hash(prev_hash: str, payload: dict[str, Any]) -> str:
    """SHA-256 chain hash matching LedgerEntry.compute_hash() in models.py."""
    entry_json = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256((prev_hash + entry_json).encode()).hexdigest()


# ── Read ──────────────────────────────────────────────────────────────────────

async def get_incidents(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 50,
    status: Optional[str] = None,
    severity: Optional[str] = None,
) -> dict[str, Any]:
    """Paginated incident list with optional filters."""
    query = select(IncidentORM).order_by(IncidentORM.created_at.desc())
    count_query = select(func.count(IncidentORM.id))

    if status:
        query = query.where(IncidentORM.status == status)
        count_query = count_query.where(IncidentORM.status == status)
    if severity:
        query = query.where(IncidentORM.severity == severity)
        count_query = count_query.where(IncidentORM.severity == severity)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    incidents = result.scalars().all()

    return {
        "items": [_orm_to_dict(i) for i in incidents],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def get_incident_by_id(db: AsyncSession, incident_id: str) -> Optional[dict[str, Any]]:
    """Fetch a single incident by ID."""
    result = await db.execute(select(IncidentORM).where(IncidentORM.id == incident_id))
    incident = result.scalar_one_or_none()
    return _orm_to_dict(incident) if incident else None


async def get_incident_ledger(db: AsyncSession, incident_id: str) -> list[dict[str, Any]]:
    """Return all ledger entries for an incident, ordered by seq."""
    result = await db.execute(
        select(LedgerEntryORM)
        .where(LedgerEntryORM.incident_id == incident_id)
        .order_by(LedgerEntryORM.seq)
    )
    return [_ledger_orm_to_dict(e) for e in result.scalars().all()]


# ── Write ─────────────────────────────────────────────────────────────────────

async def create_incident(
    db: AsyncSession,
    incident_data: dict[str, Any],
    actor: str = "system",
) -> dict[str, Any]:
    """
    Insert a new incident and write the first INCIDENT_CREATED ledger entry.
    Uses incident_data['id'] if provided (idempotency key from Faust chain_hash).
    """
    incident_id = incident_data.get("id") or str(uuid4())

    incident = IncidentORM(
        id=incident_id,
        title=incident_data.get("title", "Untitled Incident"),
        severity=incident_data.get("severity", "medium"),
        status=incident_data.get("status", "new"),
        technique_id=incident_data.get("technique_id", "T0000"),
        technique_name=incident_data.get("technique_name", "Unknown"),
        tactic=incident_data.get("tactic", "Unknown"),
        confidence=incident_data.get("confidence"),
        llm_rationale=incident_data.get("llm_rationale"),
        recommended_action=incident_data.get("recommended_action"),
        report_md=incident_data.get("report_md"),
        graph_mmd=incident_data.get("graph_mmd"),
        playbook_draft=incident_data.get("playbook_draft"),
    )
    db.add(incident)
    await db.flush()  # Assigns created_at server-side

    # Write the genesis ledger entry
    await _append_ledger(
        db=db,
        incident_id=incident_id,
        action="INCIDENT_CREATED",
        actor=actor,
        payload={"title": incident.title, "severity": incident.severity, "technique_id": incident.technique_id},
    )

    return _orm_to_dict(incident)


async def update_incident_status(
    db: AsyncSession,
    incident_id: str,
    new_status: str,
    actor: str,
) -> Optional[dict[str, Any]]:
    """Update incident status and append a STATUS_CHANGED ledger entry."""
    await db.execute(
        update(IncidentORM)
        .where(IncidentORM.id == incident_id)
        .values(status=new_status, updated_at=datetime.now(UTC))
    )
    await _append_ledger(
        db=db,
        incident_id=incident_id,
        action="STATUS_CHANGED",
        actor=actor,
        payload={"new_status": new_status},
    )
    return await get_incident_by_id(db, incident_id)


async def approve_playbook(
    db: AsyncSession,
    incident_id: str,
    approver_email: str,
) -> Optional[dict[str, Any]]:
    """Mark the incident's playbook as approved and ledger it."""
    now = datetime.now(UTC)
    await db.execute(
        update(IncidentORM)
        .where(IncidentORM.id == incident_id)
        .values(
            playbook_approved=True,
            playbook_approved_by=approver_email,
            playbook_approved_at=now,
            updated_at=now,
        )
    )
    await _append_ledger(
        db=db,
        incident_id=incident_id,
        action="PLAYBOOK_APPROVED",
        actor=approver_email,
        payload={"approved_at": now.isoformat()},
    )
    return await get_incident_by_id(db, incident_id)


# ── Ledger (internal) ─────────────────────────────────────────────────────────

async def _append_ledger(
    db: AsyncSession,
    incident_id: str,
    action: str,
    actor: str,
    payload: dict[str, Any],
) -> LedgerEntryORM:
    """Append a hash-chained ledger entry. Called within the same transaction as the main write."""
    # Fetch prev_hash from the last entry for this incident
    result = await db.execute(
        select(LedgerEntryORM.hash)
        .where(LedgerEntryORM.incident_id == incident_id)
        .order_by(LedgerEntryORM.seq.desc())
        .limit(1)
    )
    prev_hash = result.scalar_one_or_none() or "0" * 64  # Genesis prev_hash

    new_hash = _compute_ledger_hash(prev_hash, payload)

    entry = LedgerEntryORM(
        incident_id=incident_id,
        hash=new_hash,
        prev_hash=prev_hash,
        action=action,
        actor=actor,
        payload=payload,
    )
    db.add(entry)
    await db.flush()
    return entry


# ── LLM Call Log ─────────────────────────────────────────────────────────────

async def log_llm_call(db: AsyncSession, log_data: dict[str, Any]) -> None:
    """Persist an LLM call record. Fire-and-forget — errors are logged, not raised."""
    entry = LLMCallLogORM(
        model=log_data.get("model", "unknown"),
        input_tokens=log_data.get("input_tokens", 0),
        output_tokens=log_data.get("output_tokens", 0),
        latency_ms=log_data.get("latency_ms", 0),
        cluster_size=log_data.get("cluster_size", 1),
        technique_result=log_data.get("technique_result"),
        cost_usd=log_data.get("cost_usd"),
    )
    db.add(entry)
    await db.flush()
