import pytest
from mitre.mapping_engine import MitreRuleEngine, get_technique

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
    import os
    stix_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "mitre", "enterprise-attack-v15.1.json"))
    has_stix = os.path.exists(stix_path)
    try:
        from mitreattack.stix20 import MitreAttackData
        has_lib = True
    except Exception:
        has_lib = False
    if not (has_stix and has_lib):
        pytest.skip("MITRE STIX JSON or mitreattack lib not found; testing fallback path instead")

    technique = get_technique("T1110.001")
    assert technique["id"] == "T1110.001"
    assert "name" in technique and technique["name"]
    assert "tactic" in technique and technique["tactic"]


def test_get_technique_fallback_works():
    """Even without STIX data, get_technique must return a usable dict."""
    result = get_technique("T1078")
    assert isinstance(result, dict)
    assert result["id"] == "T1078"
    assert result["name"] and isinstance(result["name"], str)
    assert result["tactic"] and isinstance(result["tactic"], str)
    assert "description" in result

    unknown = get_technique("T9999")
    assert unknown["id"] == "T9999"
    assert unknown["name"]  # at minimum returns the ID as name
