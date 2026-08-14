"""
Unit tests for artifact generators, template renderers, sanitizers, and IOC validators.
"""

import pytest
from backend.artifacts.sanitizers import (
    sanitize_log_content,
    sanitize_mermaid_label,
    sanitize_ansible_var,
)
from backend.artifacts.ioc_validators import validate_ioc, IOCType, validate_playbook_iocs
from backend.artifacts.playbook_renderer import render_playbook, TECHNIQUE_TEMPLATE_MAP
from backend.artifacts.report_generator import generate_incident_report


def test_sanitizers_block_injection():
    # ANSI escape sequences stripped
    dirty_log = "\x1b[31mFailed password\x1b[0m for root"
    clean = sanitize_log_content(dirty_log)
    assert "\x1b" not in clean

    # Mermaid sanitization removes brackets and quotes and wraps in double-quotes
    mermaid_label = "Attacker (192.168.1.1) [Internal] \"Admin\""
    sanitized_mermaid = sanitize_mermaid_label(mermaid_label)
    assert "[" not in sanitized_mermaid
    assert "]" not in sanitized_mermaid
    # Inside the wrapped label, there should be no unescaped inner quotes
    assert sanitized_mermaid.startswith('"') and sanitized_mermaid.endswith('"')
    assert '"Admin"' not in sanitized_mermaid

    # Ansible variable injection validation
    with pytest.raises(ValueError):
        sanitize_ansible_var("192.168.1.1\n  - command: evil")


def test_ioc_validators():
    assert validate_ioc("10.0.0.1", IOCType.IP) == "10.0.0.1"
    with pytest.raises(ValueError):
        validate_ioc("999.999.999.999", IOCType.IP)
    with pytest.raises(ValueError):
        validate_ioc("10.0.0.1; rm -rf", IOCType.IP)

    assert validate_ioc(22, IOCType.PORT) == "22"
    assert validate_ioc("8080", IOCType.PORT) == "8080"
    with pytest.raises(ValueError):
        validate_ioc("70000", IOCType.PORT)

    assert validate_ioc("web-prod-01.corp", IOCType.HOSTNAME) == "web-prod-01.corp"
    with pytest.raises(ValueError):
        validate_ioc("host$(whoami)", IOCType.HOSTNAME)

    assert validate_ioc("alice_admin", IOCType.USERNAME) == "alice_admin"
    with pytest.raises(ValueError):
        validate_ioc("user; drop table", IOCType.USERNAME)


def test_all_playbook_templates_render():
    """Verify that every mapped MITRE technique renders without template errors."""
    for technique_id in TECHNIQUE_TEMPLATE_MAP.keys():
        incident = {
            "id": f"inc-{technique_id}",
            "technique_id": technique_id,
            "tactic": "Test Tactic",
            "entities": [
                {"role": "attacker", "ip": "198.51.100.22"},
                {"role": "victim", "host": "srv-prod-01", "ip": "10.0.0.5", "user": "testuser"},
            ],
        }
        playbook_text = render_playbook(incident)
        assert playbook_text is not None
        assert "SOC Containment" in playbook_text
        assert technique_id in playbook_text or "SOC-" in playbook_text


def test_report_generator_markdown_formatting():
    """Verify that Markdown report does not HTML-escape mathematical or technical symbols."""
    incident = {
        "id": "inc-test-01",
        "title": "Suspicious Activity",
        "severity": "high",
        "confidence": 0.85,
        "technique_id": "T1110.001",
        "tactic": "Credential Access",
        "entity": "10.0.0.1",
        "recommended_action": "Block source IP if anomaly score > 0.40 & failed attempts > 5.",
        "rationale": "High rate of failed authentications (count > 20).",
        "raw_evidence": ["Failed password for invalid user admin from 198.51.100.22 port 44212 <auth>"],
    }

    report = generate_incident_report(incident)
    assert report is not None
    # Verify no HTML entity corruption in Markdown
    assert "&gt;" not in report
    assert "&lt;" not in report
    assert "> 0.40" in report or "count > 20" in report
