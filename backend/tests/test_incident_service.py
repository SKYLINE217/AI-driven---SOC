"""
Tests for the incident service — in-memory store, CRUD helpers, and ledger.
"""

import pytest
from backend.api.incident_service import (
    seed_mock_data,
    get_alerts,
    get_alert,
    get_incidents,
    get_incident,
    get_incident_ledger,
    update_alert_status,
    approve_playbook,
    _alerts,
    _incidents,
    _ledger,
)


@pytest.fixture(autouse=True)
def fresh_store():
    """Clear and re-seed store before each test."""
    _alerts.clear()
    _incidents.clear()
    _ledger.clear()
    seed_mock_data()


def test_seed_populates_alerts():
    result = get_alerts()
    assert result["total"] >= 4
    assert len(result["items"]) >= 4


def test_seed_populates_incidents():
    result = get_incidents()
    assert result["total"] >= 2


def test_get_alert_by_id():
    alerts = get_alerts()
    alert_id = alerts["items"][0]["id"]
    alert = get_alert(alert_id)
    assert alert is not None
    assert alert["id"] == alert_id


def test_get_alert_not_found():
    assert get_alert("nonexistent") is None


def test_filter_alerts_by_severity():
    result = get_alerts(severity="critical")
    assert all(a["severity"] == "critical" for a in result["items"])


def test_filter_alerts_by_status():
    result = get_alerts(status="new")
    assert all(a["status"] == "new" for a in result["items"])


def test_filter_alerts_by_entity_search():
    result = get_alerts(entity_search="prod-db")
    assert len(result["items"]) >= 1
    for a in result["items"]:
        entity_str = str(a.get("entity", {})).lower()
        assert "prod-db" in entity_str


def test_update_alert_status():
    alerts = get_alerts(status="new")
    alert_id = alerts["items"][0]["id"]
    updated = update_alert_status(alert_id, "ack", actor="analyst@test.com")
    assert updated["status"] == "ack"
    # Verify in store
    assert get_alert(alert_id)["status"] == "ack"


def test_update_alert_status_not_found():
    result = update_alert_status("nonexistent", "ack", actor="analyst@test.com")
    assert result is None


def test_incident_ledger_has_entries():
    entries = get_incident_ledger("inc_a001")
    assert len(entries) >= 1
    assert all(e["incident_id"] == "inc_a001" for e in entries)


def test_ledger_hash_chain_valid():
    """Verify that each ledger entry's hash covers the previous hash."""
    import hashlib, json
    entries = get_incident_ledger("inc_a001")
    for i, entry in enumerate(entries):
        if i == 0:
            assert entry["prev_hash"] == "0" * 64
        else:
            prev = entries[i - 1]
            assert entry["prev_hash"] == prev["hash"]

        # Re-derive hash to verify integrity
        entry_json = json.dumps(entry["payload"], sort_keys=True, default=str)
        expected_hash = hashlib.sha256((entry["prev_hash"] + entry_json).encode()).hexdigest()
        assert entry["hash"] == expected_hash


def test_approve_playbook():
    ok = approve_playbook("inc_a001", actor="approver@test.com")
    assert ok is True
    incident = get_incident("inc_a001")
    assert incident["playbook_approved"] is True
    assert incident["playbook_approved_by"] == "approver@test.com"


def test_approve_playbook_not_found():
    ok = approve_playbook("nonexistent", actor="approver@test.com")
    assert ok is False


def test_pagination():
    result = get_alerts(page=1, page_size=2)
    assert len(result["items"]) <= 2
    assert result["page"] == 1


def test_sorted_newest_first():
    result = get_alerts()
    timestamps = [a["created_at"] for a in result["items"]]
    assert timestamps == sorted(timestamps, reverse=True)
