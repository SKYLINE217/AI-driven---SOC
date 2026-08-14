"""
Containment playbook renderer.
Uses Jinja2 to select and render the appropriate Ansible/firewall
template based on the incident's MITRE technique category.
All IOC variables are validated via sanitize_ansible_var() before rendering.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .sanitizers import sanitize_ansible_var

TEMPLATES_DIR = Path(__file__).parent / "playbook_templates"

# Map technique prefix to template filename
TECHNIQUE_TEMPLATE_MAP = {
    "T1110": "brute_force.yml.j2",
    "T1021": "lateral_movement.yml.j2",
    "T1498": "ddos_mitigation.yml.j2",
    "T1548": "privesc_account_suspend.yml.j2",
    "T1041": "data_exfil_egress_block.yml.j2",
    "T1046": "port_scan_block.yml.j2",
    "T1055": "process_injection_isolation.yml.j2",
    "T1078": "impossible_travel_lockout.yml.j2",
    "T1059": "scripting_interpreter_block.yml.j2",
}

_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _get_template_name(technique_id: str) -> str:
    """Match a technique ID to a template by prefix."""
    for prefix, template in TECHNIQUE_TEMPLATE_MAP.items():
        if technique_id.startswith(prefix):
            return template
    return "generic_block.yml.j2"


def render_playbook(incident: dict[str, Any]) -> str:
    """
    Render an Ansible containment playbook draft for an incident.
    
    All IOC variables (IPs, hostnames, users) are validated with 
    sanitize_ansible_var() before being passed to the template.
    Raises ValueError if any IOC contains unsafe characters.
    
    Returns the rendered playbook as a YAML string.
    """
    technique_id = incident.get("technique_id", "")
    template_name = _get_template_name(technique_id)

    # Extract and sanitize IOC variables
    entities = incident.get("entities", [])
    iocs: dict[str, str] = {
        "incident_id": incident.get("id", "unknown"),
        "technique_id": technique_id,
        "tactic": incident.get("tactic", "unknown"),
    }

    for entity in entities:
        role = entity.get("role", "")
        if role == "attacker":
            if entity.get("ip"):
                iocs["attacker_ip"] = sanitize_ansible_var(entity["ip"])
        elif role == "victim":
            if entity.get("host"):
                iocs["victim_host"] = sanitize_ansible_var(entity["host"])
            if entity.get("ip"):
                iocs["victim_ip"] = sanitize_ansible_var(entity["ip"])
            if entity.get("user"):
                iocs["victim_user"] = sanitize_ansible_var(entity["user"])

    # Fill in safe defaults for missing variables
    iocs.setdefault("attacker_ip", "0.0.0.0")
    iocs.setdefault("victim_host", "unknown-host")
    iocs.setdefault("victim_ip", "127.0.0.1")
    iocs.setdefault("victim_user", "unknown-user")

    try:
        template = _jinja_env.get_template(template_name)
    except Exception:
        # Fall back to generic template if specific one is missing
        template = _jinja_env.get_template("generic_block.yml.j2")

    return template.render(**iocs)

