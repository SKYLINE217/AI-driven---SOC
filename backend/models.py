"""
SOC Triager — Shared Pydantic Models
ECS-based event schema, feature vectors, scoring responses.
These are the contracts between Engineer A (normalizers/ML) and Engineer B (Faust/API).
"""

from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ── Enums ───────────────────────────────────────────────────────────────────

class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertStatus(str, Enum):
    NEW = "new"
    ACK = "ack"
    ESCALATED = "escalated"
    CLOSED = "closed"


class Role(str, Enum):
    ANALYST = "analyst"
    SENIOR_ANALYST = "senior_analyst"
    APPROVER = "approver"


# ── ECS Event Schema ────────────────────────────────────────────────────────

class EventInfo(BaseModel):
    kind: str = "event"
    category: list[str] = ["process"]
    action: str = "unknown"
    outcome: str = "unknown"


class SourceInfo(BaseModel):
    ip: Optional[str] = None
    port: Optional[int] = None
    geo_country: Optional[str] = None


class DestinationInfo(BaseModel):
    ip: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None


class HostInfo(BaseModel):
    name: Optional[str] = None
    os: Optional[str] = None


class UserInfo(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None


class LogInfo(BaseModel):
    source_type: str
    raw: str = Field(max_length=1000)


class NormalizedEvent(BaseModel):
    """ECS-normalized event — the universal format for the SOC pipeline."""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event: EventInfo = Field(default_factory=EventInfo)
    source: SourceInfo = Field(default_factory=SourceInfo)
    destination: DestinationInfo = Field(default_factory=DestinationInfo)
    host: HostInfo = Field(default_factory=HostInfo)
    user: UserInfo = Field(default_factory=UserInfo)
    log: LogInfo

    model_config = {"extra": "forbid"}


# ── Feature Vector ──────────────────────────────────────────────────────────

class FeatureVector(BaseModel):
    """Windowed features computed per entity for ML scoring."""
    entity_key: str
    event_count_1m: float = 0.0
    event_count_5m: float = 0.0
    event_count_1h: float = 0.0
    failed_auth_ratio: float = 0.0
    distinct_dest_ports: float = 0.0
    dest_ip_fanout: float = 0.0
    bytes_transferred: float = 0.0
    tod_zscore: float = 0.0
    geo_velocity_kmh: float = 0.0

    def to_array(self) -> list[float]:
        return [
            self.event_count_1m,
            self.event_count_5m,
            self.event_count_1h,
            self.failed_auth_ratio,
            self.distinct_dest_ports,
            self.dest_ip_fanout,
            self.bytes_transferred,
            self.tod_zscore,
            self.geo_velocity_kmh,
        ]


# ── Scoring ─────────────────────────────────────────────────────────────────

class ScoreRequest(BaseModel):
    features: FeatureVector


class FeatureContribution(BaseModel):
    name: str
    contribution: float


class ScoreResponse(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    threshold: float
    is_anomaly: bool
    top_features: list[FeatureContribution]
    model_version: str
    latency_ms: float


# ── LLM Triage ──────────────────────────────────────────────────────────────

class TriageResult(BaseModel):
    technique_id: str
    technique_name: str
    tactic: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(max_length=500)
    severity: Severity
    recommended_immediate_action: str = Field(max_length=300)


# ── API Schemas ─────────────────────────────────────────────────────────────

class StatusUpdateRequest(BaseModel):
    status: AlertStatus
    note: Optional[str] = Field(None, max_length=1000)

    model_config = {"extra": "forbid"}


class ApproveRequest(BaseModel):
    note: str = Field(min_length=1, max_length=1000)

    model_config = {"extra": "forbid"}
