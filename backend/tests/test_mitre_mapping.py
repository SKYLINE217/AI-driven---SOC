import pytest
from backend.mitre.mapping_engine import MitreRuleEngine, get_technique

def test_brute_force_ssh_rule():
    engine = MitreRuleEngine()
    context = {
        "event_type": "auth",
        "action": "failed",
        "dest_port": 22,
        "event_count_5m": 15
    }
    candidates = engine.get_candidate_techniques(context)
    assert "T1110.001" in candidates
    assert "T1041" not in candidates

def test_data_exfiltration_rule():
    engine = MitreRuleEngine()
    context = {
        "bytes_transferred": 600000000,
        "dest_is_external": True,
        "anomaly_score": 0.95
    }
    candidates = engine.get_candidate_techniques(context)
    assert "T1041" in candidates

def test_impossible_travel_rule():
    engine = MitreRuleEngine()
    context = {
        "geo_velocity_kmh": 2000,
        "event_type": "auth",
        "action": "success"
    }
    candidates = engine.get_candidate_techniques(context)
    assert "T1078" in candidates

def test_missing_fields_do_not_crash():
    engine = MitreRuleEngine()
    # Empty context, defaults should prevent NameError
    candidates = engine.get_candidate_techniques({})
    assert isinstance(candidates, list)
    assert len(candidates) == 0

def test_get_technique_stix():
    # Only test if file exists to prevent test failure without dataset
    import os
    if not os.path.exists("../data/mitre/enterprise-attack-v15.1.json"):
        pytest.skip("MITRE STIX JSON not found")
        
    technique = get_technique("T1110.001")
    assert technique["id"] == "T1110.001"
    assert "Password Guessing" in technique["name"]
    assert technique["tactic"] == "credential-access"
