import pytest
import os
from unittest.mock import patch, MagicMock
from backend.llm.triage_client import triage_event_cluster, TriageResult

def test_triage_result_validation():
    # Valid data
    data = {
        "technique_id": "T1110.001",
        "technique_name": "Password Guessing",
        "tactic": "Credential Access",
        "confidence": 0.85,
        "rationale": "High volume of failed auth events",
        "severity": "high",
        "recommended_immediate_action": "Block IP"
    }
    result = TriageResult(**data)
    assert result.technique_id == "T1110.001"
    
    # Invalid confidence (should be <= 1.0)
    data["confidence"] = 1.5
    with pytest.raises(ValueError):
        TriageResult(**data)

@patch("backend.llm.triage_client.client.messages.create")
def test_triage_event_cluster_mocked(mock_create):
    # Mock LLM response
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text='''{
        "technique_id": "T1110.001",
        "technique_name": "Password Guessing",
        "tactic": "Credential Access",
        "confidence": 0.95,
        "rationale": "Test rationale",
        "severity": "critical",
        "recommended_immediate_action": "Block"
    }''')]
    mock_create.return_value = mock_message

    events = [{"event_type": "auth", "action": "failed"}]
    top_features = {"event_count_5m": 25}
    candidates = ["T1110.001", "T1041"]
    
    result = triage_event_cluster(events, 0.9, top_features, candidates)
    
    assert result.technique_id == "T1110.001"
    assert result.severity == "critical"
    mock_create.assert_called_once()

@patch("backend.llm.triage_client.client.messages.create")
def test_triage_event_cluster_retry_logic(mock_create):
    # First response invalid, second response valid
    invalid_message = MagicMock()
    invalid_message.content = [MagicMock(text='{"invalid": "json" }')]
    
    valid_message = MagicMock()
    valid_message.content = [MagicMock(text='''{
        "technique_id": "T1041",
        "technique_name": "Exfil",
        "tactic": "Exfiltration",
        "confidence": 0.8,
        "rationale": "Large data",
        "severity": "high",
        "recommended_immediate_action": "Block port"
    }''')]
    
    mock_create.side_effect = [invalid_message, valid_message]

    result = triage_event_cluster([], 0.8, {}, ["T1041"])
    assert result.technique_id == "T1041"
    assert mock_create.call_count == 2

@pytest.mark.skipif("ANTHROPIC_API_KEY" not in os.environ, reason="No Anthropic API Key")
def test_triage_event_cluster_integration():
    events = [
        {"timestamp": "2026-08-10T09:12:00Z", "event_type": "auth", "action": "failed", "source_ip": "203.0.113.44"},
        {"timestamp": "2026-08-10T09:12:01Z", "event_type": "auth", "action": "failed", "source_ip": "203.0.113.44"},
        {"timestamp": "2026-08-10T09:12:02Z", "event_type": "auth", "action": "failed", "source_ip": "203.0.113.44"}
    ]
    top_features = {"event_count_5m": 17, "failed_auth_ratio": 1.0}
    candidates = ["T1110.001", "T1021.004"]
    
    result = triage_event_cluster(events, 0.95, top_features, candidates)
    
    assert result.technique_id == "T1110.001"
    assert result.severity in ["high", "critical"]
