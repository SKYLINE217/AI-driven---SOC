from collections import defaultdict
from typing import Any, Dict, List
from config import CLUSTER_WINDOW_SECS

_clusters: Dict[str, List] = defaultdict(list)


def _bucket(ts: float) -> int:
    return int(ts // CLUSTER_WINDOW_SECS)


def _key(entity: str, technique_id: str, ts: float) -> str:
    return f"{entity}:{technique_id}:{_bucket(ts)}"


def add_alert(entity: str, technique_id: str, event: Dict[str, Any]) -> None:
    ts = event.get("@timestamp_unix", 0.0)
    if not isinstance(ts, (int, float)):
        if hasattr(ts, "timestamp"):
            ts = ts.timestamp()
        else:
            ts = 0.0
    k = _key(entity, technique_id, float(ts))
    _clusters[k].append((float(ts), event))


def _entity_from_event(evt: Dict[str, Any]) -> str:
    source = evt.get("source", {}) or {}
    user = evt.get("user", {}) or {}
    return source.get("ip") or user.get("name") or "unknown"


def _event_ts(evt: Dict[str, Any]) -> float:
    ts = evt.get("@timestamp_unix")
    if isinstance(ts, (int, float)):
        return float(ts)
    ts_val = evt.get("timestamp")
    if isinstance(ts_val, (int, float)):
        return float(ts_val)
    if hasattr(ts_val, "timestamp"):
        return float(ts_val.timestamp())
    return 0.0


def cluster_alerts(
    scored_events: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    by_entity: Dict[str, List[Dict]] = defaultdict(list)
    for evt in scored_events:
        entity = _entity_from_event(evt)
        by_entity[entity].append(evt)

    clusters = []
    for entity, events in by_entity.items():
        if not events:
            continue
        max_evt = max(events, key=lambda e: float(e.get("anomaly_score", 0)))
        max_score = float(max_evt.get("anomaly_score", 0.0))
        clusters.append({
            "entity":       entity,
            "technique_id": "",
            "events":       events,
            "max_score":    max_score,
            "top_features": max_evt.get("top_features", []),
        })

    return clusters


def get_cluster(entity: str, technique_id: str, ts: float) -> List[Dict]:
    k = _key(entity, technique_id, float(ts))
    return [evt for _, evt in _clusters.get(k, [])]


def reset_state() -> None:
    _clusters.clear()


# ── Backward-compat shims for original test suite ──────────────────────────

def _entity_key(event: Dict[str, Any]) -> str:
    """Extract entity key from original event dict shape (no top_features)."""
    src = event.get("source", {})
    if isinstance(src, dict) and src.get("ip"):
        return src["ip"]
    host = event.get("host", {})
    if isinstance(host, dict) and host.get("name"):
        return host["name"]
    usr = event.get("user", {})
    if isinstance(usr, dict) and usr.get("name"):
        return usr["name"]
    return "unknown"


def _time_bucket(event: Dict[str, Any]) -> str:
    """5-minute bucket from an ISO '@timestamp' string (e.g. "06:10" for 06:13)."""
    import re
    ts_str = str(event.get("@timestamp", ""))
    m = re.search(r"(\d{2}):(\d{2}):(\d{2})", ts_str)
    if m:
        hh = int(m.group(1))
        mm = int(m.group(2))
        bucket_mm = (mm // 5) * 5
        return f"T{hh:02d}:{bucket_mm:02d}"
    return "T00:00"


def _rule_technique_for_context(ctx: Dict[str, Any]) -> str:
    """Best-effort technique ID from context dict; falls back to brute-force default."""
    try:
        from mitre.mapping_engine import MitreRuleEngine
        engine = MitreRuleEngine()
        candidates = engine.get_candidate_techniques(ctx or {})
        if candidates:
            return candidates[0]
    except Exception:
        pass
    if not ctx:
        return "T1110.001"
    if (ctx.get("dest_port") == 22
            or str(ctx.get("action")).lower() == "failed"
            or str(ctx.get("event_type")).lower() == "auth"):
        return "T1110.001"
    if ctx.get("bytes_transferred", 0) and float(ctx["bytes_transferred"]) >= 500_000_000:
        return "T1498"
    if ctx.get("dest_is_external") and float(ctx.get("bytes_transferred", 0)) > 0:
        return "T1041"
    if int(ctx.get("distinct_dest_ports", 0) or 0) >= 10:
        return "T1046"
    return "T1110.001"


def cluster_events(events: List[Dict[str, Any]],
                   contexts: List[Dict[str, Any]] | None) -> List[Dict[str, Any]]:
    """
    Original test-compatible clustering.

    Accepts events + parallel contexts list (or None). Groups events by
    (entity, technique_id, 5-min bucket) and returns clusters sorted by
    cluster_size descending.
    """
    from collections import defaultdict as _dd

    if not events:
        return []

    if contexts is None:
        contexts = list(events)
    contexts = list(contexts)
    while len(contexts) < len(events):
        contexts.append(contexts[-1] if contexts else {})

    technique_ids = [_rule_technique_for_context(ctx) for ctx in contexts]

    clusters_by_key: Dict[tuple, List[Dict[str, Any]]] = _dd(list)
    for i, evt in enumerate(events):
        entity = _entity_key(evt)
        tech = technique_ids[i] if i < len(technique_ids) else "T1110.001"
        bucket = _time_bucket(evt)
        key = (entity, tech, bucket)
        clusters_by_key[key].append(evt)

    result: List[Dict[str, Any]] = []
    for (entity, tech, bucket), evts in clusters_by_key.items():
        result.append({
            "cluster_key": bucket,
            "entity": entity,
            "technique_id": tech,
            "events": list(evts),
            "cluster_size": len(evts),
        })
    result.sort(key=lambda c: c["cluster_size"], reverse=True)
    return result

