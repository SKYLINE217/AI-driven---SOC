"""
Alert Clustering — groups raw anomaly events for batched LLM triage calls.

Design goals (from the plan §8):
- Cluster near-duplicate anomalies (same source IP/technique/time window) before calling
  the LLM once per cluster, not once per event.
- Returns clusters ready for triage_event_cluster().

Clustering key: (entity_key, technique_id, time_bucket_5min)
  entity_key = first non-null of: source_ip, host, user
  technique_id = first candidate technique from MitreRuleEngine (or "UNKNOWN")
  time_bucket_5min = floor(event timestamp to nearest 5 minutes)
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, UTC
from typing import Any

from backend.mitre.mapping_engine import MitreRuleEngine

_rule_engine = MitreRuleEngine()


def _entity_key(event: dict[str, Any]) -> str:
    """Derive a canonical entity key from an event dict."""
    source = event.get("source", {}) or {}
    host = event.get("host", {}) or {}
    user = event.get("user", {}) or {}

    ip = source.get("ip") or event.get("source_ip") or event.get("src_ip")
    hostname = host.get("name") or event.get("host_name") or event.get("host")
    username = user.get("name") or event.get("user") or event.get("username")

    return ip or hostname or username or "unknown"


def _time_bucket(event: dict[str, Any]) -> str:
    """Floor timestamp to the nearest 5-minute bucket (ISO string)."""
    raw_ts = event.get("@timestamp") or event.get("timestamp") or datetime.now(UTC).isoformat()
    try:
        if isinstance(raw_ts, str):
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        else:
            ts = raw_ts
        # Floor to 5-minute boundary
        bucket_minute = (ts.minute // 5) * 5
        return ts.replace(minute=bucket_minute, second=0, microsecond=0).isoformat()
    except (ValueError, TypeError):
        return "unknown"


def _primary_technique(event_context: dict[str, Any]) -> str:
    """Get the first candidate technique ID for an event context (or UNKNOWN)."""
    candidates = _rule_engine.get_candidate_techniques(event_context)
    return candidates[0] if candidates else "UNKNOWN"


def cluster_events(
    events: list[dict[str, Any]],
    event_contexts: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Group a list of anomaly events into clusters for batched LLM triage.

    Args:
        events: List of ECS-normalized event dicts (from the pipeline).
        event_contexts: Optional list of feature/context dicts matching events by index.
                        If not provided, context is built from the events themselves.

    Returns:
        List of cluster dicts, each with:
            - cluster_key: tuple string (entity, technique, bucket)
            - entity: str
            - technique_id: str (primary candidate)
            - time_bucket: str
            - events: list of matching event dicts
            - event_contexts: list of matching context dicts
            - cluster_size: int
    """
    if event_contexts is None:
        event_contexts = events  # Fall back to using event dicts as context

    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"events": [], "event_contexts": []}
    )

    for event, ctx in zip(events, event_contexts):
        entity = _entity_key(event)
        technique = _primary_technique(ctx)
        bucket = _time_bucket(event)
        key = f"{entity}|{technique}|{bucket}"

        buckets[key]["events"].append(event)
        buckets[key]["event_contexts"].append(ctx)

    clusters = []
    for key, data in buckets.items():
        parts = key.split("|", 2)
        entity = parts[0] if len(parts) > 0 else "unknown"
        technique = parts[1] if len(parts) > 1 else "UNKNOWN"
        bucket = parts[2] if len(parts) > 2 else "unknown"

        clusters.append(
            {
                "cluster_key": key,
                "entity": entity,
                "technique_id": technique,
                "time_bucket": bucket,
                "events": data["events"],
                "event_contexts": data["event_contexts"],
                "cluster_size": len(data["events"]),
            }
        )

    # Sort by cluster size descending (largest clusters = most interesting)
    return sorted(clusters, key=lambda c: c["cluster_size"], reverse=True)
