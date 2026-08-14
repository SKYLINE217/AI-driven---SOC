"""
Security and functional tests for the safe AST rule evaluator (safe_eval_condition).
"""

import pytest
from backend.mitre.mapping_engine import safe_eval_condition, MitreRuleEngine


def test_safe_eval_valid_comparisons():
    ctx = {
        "event_type": "auth",
        "action": "failed",
        "dest_port": 22,
        "event_count_5m": 15,
        "anomaly_score": 0.85,
        "source_is_internal": True,
        "dest_is_internal": True,
        "command_line": "sudo -u root /bin/bash",
        "user": "alice",
    }

    assert safe_eval_condition("event_type == 'auth' and action == 'failed' and dest_port == 22 and event_count_5m > 10", ctx) is True
    assert safe_eval_condition("dest_port in [22, 3389, 445]", ctx) is True
    assert safe_eval_condition("dest_port not in [80, 443]", ctx) is True
    assert safe_eval_condition("'sudo' in command_line and user != 'root' and anomaly_score > 0.8", ctx) is True
    assert safe_eval_condition("anomaly_score < 0.5", ctx) is False


def test_safe_eval_blocks_code_execution():
    ctx = {"user": "test"}

    # Disallow function calls
    with pytest.raises(ValueError, match="Disallowed expression element: Call"):
        safe_eval_condition("__import__('os').system('echo pwned')", ctx)

    # Disallow attribute access (sandbox escape gadget)
    with pytest.raises(ValueError, match="Disallowed expression element: Attribute"):
        safe_eval_condition("user.__class__", ctx)

    # Disallow lambda / statements
    with pytest.raises((ValueError, SyntaxError)):
        safe_eval_condition("lambda: 1", ctx)


def test_mitre_rule_engine_runs_safely():
    engine = MitreRuleEngine()
    ctx = {
        "event_type": "auth",
        "action": "failed",
        "dest_port": 22,
        "event_count_5m": 25,
    }
    candidates = engine.get_candidate_techniques(ctx)
    assert "T1110.001" in candidates
