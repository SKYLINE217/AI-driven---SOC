"""
SOC Triager — Sandboxed Jinja2 Playbook Renderer.

Replaces the bare jinja2.Environment with jinja2.sandbox.SandboxedEnvironment.
The sandboxed environment blocks:
  - Access to Python builtins (__import__, open, exec, eval, etc.)
  - Attribute traversal to dunder methods
  - Any attempt to escape the template context

This wraps the existing playbook_renderer.py logic with hardened validation
using the new Pydantic ioc_validators.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog
from jinja2.sandbox import SandboxedEnvironment
from jinja2 import FileSystemLoader, TemplateNotFound

from .ioc_validators import IOCType, validate_playbook_iocs

log = structlog.get_logger()

TEMPLATES_DIR = Path(__file__).parent / "playbook_templates"

# IOC type hints per template variable name
_IOC_TYPE_HINTS: dict[str, IOCType] = {
    "attacker_ip": IOCType.IP,
    "victim_ip": IOCType.IP,
    "source_ip": IOCType.IP,
    "destination_ip": IOCType.IP,
    "pivot_host_ip": IOCType.IP,
    "attacker_cidrs": IOCType.CIDR,
    "target_subnet": IOCType.CIDR,
    "port": IOCType.PORT,
    "exfil_port": IOCType.PORT,
    "victim_host": IOCType.HOSTNAME,
    "pivot_host": IOCType.HOSTNAME,
    "compromised_host": IOCType.HOSTNAME,
    "victim_user": IOCType.USERNAME,
    "compromised_user": IOCType.USERNAME,
    "user_id": IOCType.USERNAME,
}

# Technique → template filename map (mirrors playbook_renderer.py)
TECHNIQUE_TEMPLATE_MAP: dict[str, str] = {
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

# ── Sandboxed Jinja2 Environment ──────────────────────────────────────────────

_sandbox_env = SandboxedEnvironment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
    # autoescape is disabled for YAML output but IOCs are pre-validated
    autoescape=False,
)


# ── Public API ────────────────────────────────────────────────────────────────

def render_playbook_safe(incident: dict[str, Any]) -> str:
    """
    Render a containment playbook using a Jinja2 SandboxedEnvironment.

    All IOC values are validated with Pydantic type validators before
    being passed to the template. Any invalid IOC raises ValueError —
    the playbook is not rendered and the error is logged.

    Returns the rendered YAML string.
    """
    technique_id = incident.get("technique_id", "")
    template_name = _get_template_name(technique_id)

    # ── Collect raw IOC values from incident entities ─────────────────────────
    raw_iocs: dict[str, str] = {
        "incident_id": str(incident.get("id", "unknown")),
        "technique_id": technique_id,
        "tactic": str(incident.get("tactic", "unknown")),
    }

    for entity in incident.get("entities", []):
        role = str(entity.get("role", ""))
        if entity.get("ip"):
            key = "attacker_ip" if role == "attacker" else "victim_ip"
            raw_iocs[key] = str(entity["ip"])
        if entity.get("host"):
            raw_iocs["victim_host"] = str(entity["host"])
        if entity.get("user"):
            raw_iocs["victim_user"] = str(entity["user"])

    # Add sensible defaults so templates always have required variables
    raw_iocs.setdefault("attacker_ip", "0.0.0.0")
    raw_iocs.setdefault("victim_host", "unknown-host")
    raw_iocs.setdefault("victim_ip", "127.0.0.1")
    raw_iocs.setdefault("victim_user", "nobody")

    # ── Validate with Pydantic type validators ────────────────────────────────
    try:
        clean_iocs = validate_playbook_iocs(raw_iocs, _IOC_TYPE_HINTS)
    except ValueError as exc:
        log.error("playbook_ioc_validation_failed", technique=technique_id, error=str(exc))
        raise

    # ── Render in sandboxed Jinja2 environment ────────────────────────────────
    try:
        template = _sandbox_env.get_template(template_name)
    except TemplateNotFound:
        log.warning("playbook_template_not_found", template=template_name, fallback="generic_block.yml.j2")
        template = _sandbox_env.get_template("generic_block.yml.j2")

    rendered = template.render(**clean_iocs)
    log.info("playbook_rendered", technique=technique_id, template=template_name)
    return rendered


def _get_template_name(technique_id: str) -> str:
    for prefix, template in TECHNIQUE_TEMPLATE_MAP.items():
        if technique_id.startswith(prefix):
            return template
    return "generic_block.yml.j2"

