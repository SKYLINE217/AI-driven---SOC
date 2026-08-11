"""
SOC Triager — Pydantic Models (ECS-Inspired Event Schema)

This module defines the canonical data models used throughout the pipeline.
These models are the contract between Engineer A (backend/ML) and Engineer B (frontend/platform).
Changes to field names MUST be coordinated between both engineers.

Schema follows Elastic Common Schema (ECS) conventions where applicable.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


# ─── Enums ────────────────────────────────────────────────────────────────────

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


class EntityRole(str, Enum):
    ATTACKER = "attacker"
    VICTIM = "victim"
    PIVOT = "pivot"
    CONTEXT = "context"


class UserRole(str, Enum):
    ANALYST = "analyst"
    SENIOR_ANALYST = "senior_analyst"
    APPROVER = "approver"


class TriageStatus(str, Enum):
    COMPLETED = "completed"
    PENDING = "pending_manual"
    FAILED = "failed"


# ─── ECS Sub-Models ──────────────────────────────────────────────────────────

class EventInfo(BaseModel):
    """ECS event.* fields — describes what happened."""
    kind: str = "event"
    category: list[str] = Field(default_factory=list)
    action: str = ""
    outcome: str = ""  # "success", "failure", "unknown"


class GeoInfo(BaseModel):
    """ECS source.geo / destination.geo fields."""
    country_iso_code: Optional[str] = None
    city_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ASInfo(BaseModel):
    """ECS source.as / destination.as fields."""
    number: Optional[int] = None
    organization_name: Optional[str] = None


class SourceInfo(BaseModel):
    """ECS source.* fields — describes the event origin."""
    ip: Optional[str] = None
    port: Optional[int] = None
    geo: GeoInfo = Field(default_factory=GeoInfo)
    as_info: ASInfo = Field(default_factory=ASInfo, alias="as")

    model_config = {"populate_by_name": True}


class DestinationInfo(BaseModel):
    """ECS destination.* fields."""
    ip: Optional[str] = None
    port: Optional[int] = None
    host: Optional[str] = None


class UserInfo(BaseModel):
    """ECS user.* fields."""
    name: Optional[str] = None
    id: Optional[str] = None
    domain: Optional[str] = None


class HostInfo(BaseModel):
    """ECS host.* fields."""
    name: Optional[str] = None
    os_family: Optional[str] = None
    ip: Optional[str] = None


class LogInfo(BaseModel):
    """ECS log.* fields — metadata about the original log source."""
    source_type: str = ""  # "syslog", "cloudtrail", "auth_log", "cicids"
    raw: str = ""  # Original log line, preserved for forensics (capped at 1000 chars)

    @field_validator("raw")
    @classmethod
    def cap_raw_length(cls, v: str) -> str:
        return v[:1000] if len(v) > 1000 else v


class RelatedInfo(BaseModel):
    """ECS related.* fields — chain-of-custody hashes."""
    hash: Optional[str] = None


# ─── Core Normalized Event ───────────────────────────────────────────────────

class NormalizedEvent(BaseModel):
    """
    The canonical ECS-inspired normalized event.

    Every raw log from any source (syslog, CloudTrail, auth.log, CICIDS2017)
    is transformed into this shape by a source-specific normalizer.
    This is the single schema that the entire pipeline operates on after ingestion.
    """
    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime
    event: EventInfo = Field(default_factory=EventInfo)
    source: SourceInfo = Field(default_factory=SourceInfo)
    destination: DestinationInfo = Field(default_factory=DestinationInfo)
    user: UserInfo = Field(default_factory=UserInfo)
    host: HostInfo = Field(default_factory=HostInfo)
    log: LogInfo = Field(default_factory=LogInfo)
    related: RelatedInfo = Field(default_factory=RelatedInfo)

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat() + "Z"}}

    def compute_chain_hash(self) -> str:
        """Compute SHA-256 hash of the event for chain-of-custody."""
        payload = self.model_dump_json(exclude={"related"})
        return f"sha256:{hashlib.sha256(payload.encode()).hexdigest()}"


# ─── Feature Vector ─────────────────────────────────────────────────────────

class FeatureVector(BaseModel):
    """
    Windowed feature vector computed per entity (host:user:source_ip).
    Used as input to the ML anomaly detection ensemble.
    """
    entity_key: str  # "host:user:source_ip"
    timestamp: datetime

    # Sliding window counts
    event_count_1m: float = 0.0
    event_count_5m: float = 0.0
    event_count_1h: float = 0.0

    # Authentication metrics
    failed_auth_ratio: float = 0.0  # failed / total in 5-min window

    # Network behavior
    distinct_dest_ports: float = 0.0  # HyperLogLog count, 5-min
    dest_ip_fanout: float = 0.0  # HyperLogLog count, 5-min (lateral movement signal)
    bytes_transferred: float = 0.0  # 5-min window

    # Temporal & spatial
    tod_zscore: float = 0.0  # time-of-day deviation from historical baseline
    geo_velocity_kmh: float = 0.0  # impossible travel indicator

    def to_array(self) -> list[float]:
        """Convert to ordered float array for ML model input."""
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

    @classmethod
    def feature_names(cls) -> list[str]:
        """Return ordered feature names matching to_array() order."""
        return [
            "event_count_1m",
            "event_count_5m",
            "event_count_1h",
            "failed_auth_ratio",
            "distinct_dest_ports",
            "dest_ip_fanout",
            "bytes_transferred",
            "tod_zscore",
            "geo_velocity_kmh",
        ]


# ─── Scoring ────────────────────────────────────────────────────────────────

class FeatureContribution(BaseModel):
    """A single feature's contribution to an anomaly score."""
    name: str
    contribution: float


class ScoreRequest(BaseModel):
    """Request body for POST /score (internal scoring API)."""
    entity_key: str
    features: FeatureVector
    event_id: str


class ScoreResponse(BaseModel):
    """Response from the scoring API."""
    score: float = Field(ge=0.0, le=1.0)
    threshold: float
    is_anomaly: bool
    top_features: list[FeatureContribution] = Field(default_factory=list)
    model_version: str = ""
    latency_ms: float = 0.0


# ─── LLM Triage ─────────────────────────────────────────────────────────────

class TriageResult(BaseModel):
    """
    Structured output from the LLM triage call.
    The technique_id MUST be from the candidate list — never hallucinated.
    """
    technique_id: str
    technique_name: str
    tactic: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(max_length=500)
    severity: Severity
    recommended_immediate_action: str = Field(max_length=300)


# ─── Incident ───────────────────────────────────────────────────────────────

class Entity(BaseModel):
    """An entity involved in an incident."""
    role: EntityRole
    ip: Optional[str] = None
    host: Optional[str] = None
    user: Optional[str] = None
    geo_country: Optional[str] = None


class LedgerEntry(BaseModel):
    """A single entry in the append-only, hash-chained incident ledger."""
    seq: int
    incident_id: UUID
    hash: str
    prev_hash: str
    timestamp: datetime
    action: str  # INCIDENT_CREATED, STATUS_ESCALATED, PLAYBOOK_APPROVED, etc.
    actor: str  # user email or "system"
    payload: dict[str, Any] = Field(default_factory=dict)

    @staticmethod
    def compute_hash(prev_hash: str, payload: dict[str, Any]) -> str:
        """Compute SHA-256 for the hash chain."""
        entry_json = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256((prev_hash + entry_json).encode()).hexdigest()


class LLMCallLog(BaseModel):
    """Record of a single LLM API call for cost/latency tracking."""
    id: UUID = Field(default_factory=uuid4)
    called_at: datetime = Field(default_factory=datetime.utcnow)
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cluster_size: int
    technique_result: Optional[str] = None
    cost_usd: float = 0.0
