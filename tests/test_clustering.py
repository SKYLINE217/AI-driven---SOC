"""
Unit tests for alert clustering logic.
"""

import pytest
from mitre.alert_clustering import cluster_events, _entity_key, _time_bucket


def test_cluster_by_entity_and_technique():
    """Events from same IP in the same 5-min bucket should cluster together."""
    events = [
        {"source": {"ip": "203.0.113.44"}, "@timestamp": "2026-08-11T06:12:00Z"},
        {"source": {"ip": "203.0.113.44"}, "@timestamp": "2026-08-11T06:13:00Z"},
        {"source": {"ip": "203.0.113.44"}, "@timestamp": "2026-08-11T06:14:00Z"},
    ]
    contexts = [
        {"event_type": "auth", "action": "failed", "dest_port": 22, "event_count_5m": 15},
        {"event_type": "auth", "action": "failed", "dest_port": 22, "event_count_5m": 15},
        {"event_type": "auth", "action": "failed", "dest_port": 22, "event_count_5m": 15},
    ]
    clusters = cluster_events(events, contexts)

    # All 3 events should be in one cluster
    assert len(clusters) == 1
    assert clusters[0]["cluster_size"] == 3
    assert clusters[0]["entity"] == "203.0.113.44"
    assert clusters[0]["technique_id"] == "T1110.001"


def test_cluster_different_entities_separate():
    """Events from different IPs should produce separate clusters."""
    events = [
        {"source": {"ip": "10.0.0.1"}, "@timestamp": "2026-08-11T06:10:00Z"},
        {"source": {"ip": "10.0.0.2"}, "@timestamp": "2026-08-11T06:10:00Z"},
    ]
    contexts = [
        {"bytes_transferred": 600000000, "dest_is_external": True, "anomaly_score": 0.9},
        {"distinct_dest_ports": 60, "dest_ip_fanout": 3},
    ]
    clusters = cluster_events(events, contexts)

    # Should be 2 separate clusters
    assert len(clusters) == 2


def test_cluster_sorted_by_size_desc():
    """Largest clusters should come first."""
    events = [
        # 3 events from 10.0.0.1
        {"source": {"ip": "10.0.0.1"}, "@timestamp": "2026-08-11T06:10:00Z"},
        {"source": {"ip": "10.0.0.1"}, "@timestamp": "2026-08-11T06:11:00Z"},
        {"source": {"ip": "10.0.0.1"}, "@timestamp": "2026-08-11T06:12:00Z"},
        # 1 event from 10.0.0.2
        {"source": {"ip": "10.0.0.2"}, "@timestamp": "2026-08-11T06:10:00Z"},
    ]
    contexts = [
        {"event_type": "auth", "action": "failed", "dest_port": 22, "event_count_5m": 15},
        {"event_type": "auth", "action": "failed", "dest_port": 22, "event_count_5m": 15},
        {"event_type": "auth", "action": "failed", "dest_port": 22, "event_count_5m": 15},
        {"event_type": "auth", "action": "failed", "dest_port": 22, "event_count_5m": 15},
    ]
    clusters = cluster_events(events, contexts)
    assert clusters[0]["cluster_size"] > clusters[1]["cluster_size"]


def test_entity_key_extraction_ip():
    event = {"source": {"ip": "1.2.3.4"}}
    assert _entity_key(event) == "1.2.3.4"


def test_entity_key_extraction_host():
    event = {"host": {"name": "prod-db-03"}}
    assert _entity_key(event) == "prod-db-03"


def test_entity_key_extraction_user():
    event = {"user": {"name": "svc-backup"}}
    assert _entity_key(event) == "svc-backup"


def test_entity_key_unknown():
    event = {}
    assert _entity_key(event) == "unknown"


def test_time_bucket_5min_floor():
    event = {"@timestamp": "2026-08-11T06:13:45Z"}
    bucket = _time_bucket(event)
    # 06:13 should floor to 06:10
    assert "06:10" in bucket


def test_cluster_empty_events():
    clusters = cluster_events([], [])
    assert clusters == []


def test_cluster_fallback_context_from_events():
    """If event_contexts is None, it should fall back to using events as context."""
    events = [{"source": {"ip": "10.0.0.1"}, "@timestamp": "2026-08-11T06:10:00Z"}]
    clusters = cluster_events(events, None)
    assert len(clusters) == 1
    assert clusters[0]["entity"] == "10.0.0.1"
