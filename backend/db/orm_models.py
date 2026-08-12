"""
SOC Triager — SQLAlchemy ORM Models.

Maps the schema from migrations/001_initial.sql to Python classes.
These are the persistence layer models — separate from the Pydantic API models
in backend/models.py. The repository layer translates between the two.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, TIMESTAMPTZ, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.db.engine import Base


# ── Users ─────────────────────────────────────────────────────────────────────

class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(
        String,
        nullable=False,
        # CHECK constraint mirrors the SQL schema
    )
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=func.now(), nullable=False)


# ── Incidents ─────────────────────────────────────────────────────────────────

class IncidentORM(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="new")
    technique_id: Mapped[str] = mapped_column(String(20), nullable=False)
    technique_name: Mapped[str] = mapped_column(Text, nullable=False)
    tactic: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    llm_rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommended_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    report_md: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    graph_mmd: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    playbook_draft: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    playbook_approved: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    playbook_approved_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    playbook_approved_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMPTZ, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    alerts: Mapped[list[AlertORM]] = relationship("AlertORM", back_populates="incident", lazy="select")
    ledger_entries: Mapped[list[LedgerEntryORM]] = relationship(
        "LedgerEntryORM", back_populates="incident", lazy="select"
    )

    __table_args__ = (
        Index("ix_incidents_status_severity_created", "status", "severity", "created_at"),
        Index("ix_incidents_technique_id", "technique_id"),
    )


# ── Alerts ────────────────────────────────────────────────────────────────────

class AlertORM(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    incident_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("incidents.id"), nullable=True, index=True
    )
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    source_ip: Mapped[Optional[str]] = mapped_column(INET, nullable=True)
    destination_host: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    technique_id: Mapped[str] = mapped_column(String(20), nullable=False)
    tactic: Mapped[str] = mapped_column(Text, nullable=False)
    anomaly_score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    top_features: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="new")
    assignee: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=func.now(), nullable=False)

    incident: Mapped[Optional[IncidentORM]] = relationship("IncidentORM", back_populates="alerts")

    __table_args__ = (
        Index("ix_alerts_status_severity_created", "status", "severity", "created_at"),
        Index("ix_alerts_source_ip_created", "source_ip", "created_at"),
        Index("ix_alerts_technique_id", "technique_id"),
    )


# ── Incident Ledger ──────────────────────────────────────────────────────────

class LedgerEntryORM(Base):
    __tablename__ = "incident_ledger"

    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("incidents.id"), nullable=False, index=True
    )
    hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    prev_hash: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=func.now(), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    incident: Mapped[IncidentORM] = relationship("IncidentORM", back_populates="ledger_entries")


# ── LLM Call Log ─────────────────────────────────────────────────────────────

class LLMCallLogORM(Base):
    __tablename__ = "llm_call_log"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    called_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=func.now(), nullable=False, index=True)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    cluster_size: Mapped[int] = mapped_column(Integer, nullable=False)
    technique_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cost_usd: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
