"""
Shared pytest fixtures for the SOC Triager CLI test suite.
Handles:
  - SQLite in-memory database for incident_service tests
  - In-memory state resets for feature_engineering and alert_clustering
"""
import pytest
from backend import database
from pathlib import Path


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """
    Point database.DB_PATH at a fresh temp file for every test.
    Automatically used by ALL tests (autouse=True).
    """
    test_db = tmp_path / "test_soc.db"
    monkeypatch.setattr(database, "DB_PATH", test_db)
    database.init_db()
    yield


@pytest.fixture(autouse=True)
def reset_feature_state():
    """Clear feature engineering accumulators before and after each test."""
    try:
        from ml.feature_engineering import reset_state
        reset_state()
    except Exception:
        pass
    yield
    try:
        from ml.feature_engineering import reset_state
        reset_state()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def reset_cluster_state():
    """Clear alert clustering state before and after each test."""
    try:
        from mitre.alert_clustering import reset_state
        reset_state()
    except Exception:
        pass
    yield
    try:
        from mitre.alert_clustering import reset_state
        reset_state()
    except Exception:
        pass


@pytest.fixture
def sample_event():
    """A minimal normalized event dict for use in unit tests."""
    return {
        "@timestamp_unix": 1_700_000_000.0,
        "source": {"ip": "10.0.0.1", "geo": {"location": {"lat": 28.6, "lon": 77.2}}},
        "destination": {"ip": "8.8.8.8", "port": 443},
        "user": {"name": "testuser"},
        "event": {"id": "evt-001", "outcome": "success"},
        "network": {"bytes": 1024},
        "source_type": "syslog",
    }


@pytest.fixture
def sample_failed_auth_event(sample_event):
    evt = dict(sample_event)
    evt["event"] = {"id": "evt-002", "outcome": "failure"}
    return evt


@pytest.fixture
def sample_cluster(sample_event):
    """A minimal cluster dict as returned by cluster_alerts()."""
    return {
        "entity": "10.0.0.1",
        "technique_id": "T1078",
        "events": [sample_event],
        "max_score": 0.72,
        "top_features": [{"name": "failed_auth_ratio", "value": 0.80}],
    }


@pytest.fixture
def sample_triage_result():
    """A minimal TriageResult dict for tests that don't need real triage."""
    return {
        "technique_id": "T1078",
        "technique_name": "Valid Accounts",
        "tactic": "Credential Access",
        "confidence": 0.79,
        "rationale": "Test rationale.",
        "severity": "high",
        "recommended_immediate_action": "Block IP and reset credentials.",
    }

