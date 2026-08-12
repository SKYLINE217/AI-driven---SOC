"""
SOC Triager — Centralised Prometheus Metrics Registry.

All pipeline services import from here to avoid duplicate metric registration.
Instruments:
  - Event ingestion (events_ingested_total)
  - Anomaly detection (anomalies_detected_total)
  - LLM calls (llm_calls_total, llm_latency_seconds, llm_cost_usd_total)
  - Incident lifecycle (incidents_created_total)
  - Pipeline lag (pipeline_lag_seconds gauge)
  - Auth failures (auth_failures_total)
  - Rate limit hits (rate_limit_hits_total)
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ── Ingestion ─────────────────────────────────────────────────────────────────

events_ingested_total = Counter(
    "soc_events_ingested_total",
    "Total raw events ingested by source type",
    ["source_type"],
)

# ── Anomaly Detection ─────────────────────────────────────────────────────────

anomalies_detected_total = Counter(
    "soc_anomalies_detected_total",
    "Total anomalous events detected by severity",
    ["severity"],
)

# ── LLM ──────────────────────────────────────────────────────────────────────

llm_calls_total = Counter(
    "soc_llm_calls_total",
    "Total LLM API calls by status",
    ["status"],  # success | timeout | circuit_open | injection_detected
)

llm_latency_seconds = Histogram(
    "soc_llm_latency_seconds",
    "LLM API call latency",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

llm_cost_usd_total = Counter(
    "soc_llm_cost_usd_total",
    "Cumulative LLM API cost in USD",
)

llm_circuit_open = Gauge(
    "soc_llm_circuit_open",
    "1 if LLM circuit breaker is open, 0 if closed",
)

# ── Incidents ─────────────────────────────────────────────────────────────────

incidents_created_total = Counter(
    "soc_incidents_created_total",
    "Total incidents created by severity",
    ["severity"],
)

# ── Pipeline ──────────────────────────────────────────────────────────────────

pipeline_lag_seconds = Gauge(
    "soc_pipeline_lag_seconds",
    "Consumer lag in seconds between event ingestion and incident creation",
)

# ── Security ──────────────────────────────────────────────────────────────────

auth_failures_total = Counter(
    "soc_auth_failures_total",
    "Total failed authentication attempts",
    ["reason"],  # invalid_credentials | expired_token | revoked_token
)

rate_limit_hits_total = Counter(
    "soc_rate_limit_hits_total",
    "Total requests rejected by rate limiter",
    ["endpoint"],
)
