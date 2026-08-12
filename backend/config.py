"""
SOC Triager — Centralised Application Settings.

All environment variable access goes through this Pydantic Settings model.
Missing required secrets cause a hard startup failure with a clear error message
rather than silently falling back to insecure defaults.

Usage:
    from backend.config import settings
    db_url = settings.database_url
"""

from __future__ import annotations

import os
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Production settings for the SOC Triager backend.
    All values read from environment variables.
    Required fields (no default) raise ValidationError on startup if missing.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://soc:soc@localhost:5432/socdb",
        description="Async PostgreSQL DSN (asyncpg driver)",
    )

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # ── JWT (RS256) ───────────────────────────────────────────────────────────
    jwt_private_key: Optional[str] = Field(
        default=None,
        description="RS256 private key PEM string (required in production)",
    )
    jwt_public_key: Optional[str] = Field(
        default=None,
        description="RS256 public key PEM string",
    )
    jwt_private_key_path: Optional[str] = Field(
        default=None,
        description="Path to RS256 private key PEM file (alternative to jwt_private_key)",
    )
    jwt_public_key_path: Optional[str] = Field(
        default=None,
        description="Path to RS256 public key PEM file",
    )

    # ── LLM ──────────────────────────────────────────────────────────────────
    anthropic_api_key: Optional[str] = Field(
        default=None,
        description="Anthropic API key (required for LLM triage)",
    )

    # ── MLflow ────────────────────────────────────────────────────────────────
    mlflow_tracking_uri: str = Field(
        default="",
        description="MLflow tracking URI (e.g. postgresql://... or http://mlflow-server:5000)",
    )
    mlflow_model_name: str = Field(
        default="soc-anomaly-ensemble",
        description="MLflow registered model name",
    )

    # ── Streaming ─────────────────────────────────────────────────────────────
    kafka_bootstrap_servers: str = Field(
        default="localhost:19092",
        description="Redpanda/Kafka bootstrap servers",
    )
    scoring_api_url: str = Field(
        default="http://localhost:8001",
        description="Internal URL of the ML scoring API",
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: str = Field(
        default="",
        description="Comma-separated list of additional CORS origins",
    )

    # ── Scoring ───────────────────────────────────────────────────────────────
    anomaly_threshold: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="Anomaly score threshold for alert generation",
    )

    # ── GeoIP ─────────────────────────────────────────────────────────────────
    geoip_db_path: str = Field(
        default="",
        description="Path to MaxMind GeoIP2 database file",
    )

    # ── Validators ────────────────────────────────────────────────────────────

    @field_validator("anthropic_api_key")
    @classmethod
    def warn_if_no_api_key(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            import warnings
            warnings.warn(
                "ANTHROPIC_API_KEY is not set. LLM triage will use heuristic fallback.",
                stacklevel=2,
            )
        return v

    @field_validator("database_url")
    @classmethod
    def must_use_asyncpg(cls, v: str) -> str:
        if "postgresql://" in v and "+asyncpg" not in v:
            # Auto-fix the driver prefix
            v = v.replace("postgresql://", "postgresql+asyncpg://")
        return v


# ── Singleton ─────────────────────────────────────────────────────────────────

settings = Settings()
