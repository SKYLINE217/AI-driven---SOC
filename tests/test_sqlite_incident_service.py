"""
Tests for the SQLite-backed incident service (backend.services.incident_service) and database layer.
"""

import os
import pytest
from pathlib import Path
from backend import database
from backend.services.incident_service import (
    create_incident,
    get_incident,
    list_incidents,
    update_status,
    verify_chain,
)


@pytest.fixture(autouse=True)
def isolated_test_db(tmp_path, monkeypatch):
    """Point DB_PATH to a temporary sqlite database for isolation."""
    db_file = tmp_path / "test_soc.db"
    monkeypatch.setattr(database, "DB_PATH", db_file)
    database.init_db()
    return db_file


def test_create_and_get_incident():
    cluster = {
        "entity": "192.168.1.50",
        "events": [
            {"source_type": "auth", "anomaly_score": 0.88},
            {"source_type": "auth", "anomaly_score": 0.92},
        ],
    }
    triage = {
        "technique_id": "T1110.001",
        "tactic": "Credential Access",
        "severity": "critical",
        "confidence": 0.92,
        "rationale": "High volume of failed authentications across SSH ports.",
    }

    incident = create_incident(cluster, triage)
    assert incident is not None
    assert incident["entity"] == "192.168.1.50"
    assert incident["severity"] == "critical"
    assert incident["status"] == "open"
    assert len(incident["alerts"]) == 2
    assert len(incident["ledger"]) >= 1

    fetched = get_incident(incident["id"])
    assert fetched is not None
    assert fetched["id"] == incident["id"]


def test_list_incidents_with_allowlist_filters():
    cluster1 = {"entity": "host-a", "events": []}
    triage1 = {"technique_id": "T1046", "tactic": "Discovery", "severity": "medium", "confidence": 0.7, "rationale": "scan"}
    inc1 = create_incident(cluster1, triage1)

    cluster2 = {"entity": "host-b", "events": []}
    triage2 = {"technique_id": "T1498", "tactic": "Impact", "severity": "critical", "confidence": 0.95, "rationale": "ddos"}
    inc2 = create_incident(cluster2, triage2)

    # Filter by severity
    critical_list = list_incidents(severity="critical")
    assert len(critical_list) == 1
    assert critical_list[0]["id"] == inc2["id"]

    # Filter by status
    open_list = list_incidents(status="open")
    assert len(open_list) == 2


def test_update_status_and_ledger_verification():
    cluster = {"entity": "10.0.0.12", "events": []}
    triage = {"technique_id": "T1021.002", "tactic": "Lateral Movement", "severity": "high", "confidence": 0.85, "rationale": "smb"}
    inc = create_incident(cluster, triage)

    updated = update_status(inc["id"], "investigating", actor="analyst_alice")
    assert updated["status"] == "investigating"

    updated = update_status(inc["id"], "resolved", actor="senior_bob")
    assert updated["status"] == "resolved"

    # Verify blockchain-style hash chain integrity
    chain_result = verify_chain(inc["id"])
    assert chain_result["valid"] is True
    assert len(chain_result["entries"]) == 3  # created + 2 status changes


def test_update_status_invalid_value():
    cluster = {"entity": "10.0.0.12", "events": []}
    triage = {"technique_id": "T1021", "tactic": "Lateral Movement", "severity": "low", "confidence": 0.5, "rationale": "test"}
    inc = create_incident(cluster, triage)

    with pytest.raises(ValueError, match="Invalid status"):
        update_status(inc["id"], "bogus_status")
