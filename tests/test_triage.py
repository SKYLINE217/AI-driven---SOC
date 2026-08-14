"""
Tests for triage logic.
"""
from backend.services.triage import deterministic_triage
from backend.models import Severity

def test_deterministic_triage():
    events = [{"source": {"ip": "10.0.0.5"}}]
    top_features = [{"name": "event_count_1m", "value": 15.0}]
    
    triage = deterministic_triage(
        events=events,
        anomaly_score=0.9,
        top_features=top_features,
        candidate_technique_ids=["T1110.001"],
        technique_name="Brute Force",
        tactic="Credential Access",
    )
    
    assert triage.severity == Severity.CRITICAL
    assert triage.technique_id == "T1110.001"
    assert triage.technique_name == "Brute Force"
    assert triage.tactic == "Credential Access"
    assert "10.0.0.5" in triage.rationale
    assert "event_count_1m=15.0" in triage.rationale
    assert "reset affected credentials" in triage.recommended_immediate_action

def test_deterministic_triage_low_severity():
    triage = deterministic_triage(
        events=[],
        anomaly_score=0.4,
        top_features=[],
        candidate_technique_ids=[],
        technique_name="Unknown",
        tactic="Unknown",
    )
    assert triage.severity == Severity.LOW
    assert triage.technique_id == "T0000"
    assert "Investigate host" in triage.recommended_immediate_action
