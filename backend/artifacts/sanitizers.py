"""
Security sanitizers for artifact generation.
Per soc-triager-security skill: every log field must be sanitized before
reaching a Markdown template, Mermaid graph, or Ansible playbook.
"""

from __future__ import annotations

import html
import ipaddress
import re
from urllib.parse import urlparse


def sanitize_log_content(raw: str) -> str:
    """
    Sanitize raw log content for safe embedding in Markdown reports.
    - Strips ANSI escape sequences (prevent terminal injection)
    - Strips Mermaid/Markdown-breaking special characters
    - HTML-escapes the result
    - Hard caps at 500 characters
    Called before EVERY raw log line is passed to a Jinja2 template.
    """
    raw = re.sub(r'\x1b\[[0-9;]*m', '', raw)          # strip ANSI escapes
    raw = re.sub(r'[<>{}"\[\]|;`]', '', raw)           # strip breaking chars
    raw = html.escape(raw, quote=True)                  # HTML-escape
    return raw[:500]


def sanitize_mermaid_label(label: str) -> str:
    """
    Sanitize a string for use as a Mermaid node label.
    Strips characters that break Mermaid syntax: < > [ ] { } ; | " '
    Wraps the result in double-quotes for Mermaid safety.
    """
    safe = re.sub(r'[<>\[\]{}|;"\'`]', '', str(label))
    safe = safe.strip()[:80]  # hard cap on label length
    return f'"{safe}"' if safe else '"unknown"'


def sanitize_ansible_var(value: str) -> str:
    """
    Validate a value for use as an Ansible variable (IOC: IP, hostname, CIDR, port).
    Only allows alphanumeric, dots, hyphens, colons, slashes.
    Raises ValueError on unsafe input — the playbook should not be rendered if this raises.
    """
    if not value:
        raise ValueError("Empty value for Ansible variable")
    if not re.match(r'^[\w.\-:/]+$', value):
        raise ValueError(f"Unsafe value for Ansible variable: {repr(value)}")
    return value


def sanitize_hostname(hostname: str) -> str:
    """Validate and sanitize a hostname/FQDN for use in templates."""
    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-\.]{0,253}$', str(hostname)):
        raise ValueError(f"Unsafe hostname: {repr(hostname)}")
    return hostname


# ── F-11 FIX: Strict IOC Validation ──────────────────────────────────────────

def validate_ioc(name: str, value: str) -> str:
    """
    F-11 FIX: Validate an Indicator of Compromise (IOC) using Python stdlib types
    instead of fragile regex. This prevents command injection via crafted IOC values
    (e.g. an IP field containing '; rm -rf /').

    Supported IOC types:
      - src_ip, dst_ip, source_ip, destination_ip: validated by ipaddress.ip_address()
      - src_cidr, dst_cidr: validated by ipaddress.ip_network()
      - domain, fqdn: validated by URL parsing + hostname rules
      - port: validated as integer in range 1-65535
      - hostname: validated by sanitize_hostname()

    Raises ValueError if the value is unsafe or malformed.
    Returns the original value if valid (no transformation).
    """
    if not value or not isinstance(value, str):
        raise ValueError(f"IOC '{name}': empty or non-string value")

    ip_fields = {"src_ip", "dst_ip", "source_ip", "destination_ip", "attacker_ip", "victim_ip"}
    cidr_fields = {"src_cidr", "dst_cidr", "source_cidr", "destination_cidr"}
    domain_fields = {"domain", "fqdn", "url"}
    port_fields = {"port", "src_port", "dst_port"}

    if name in ip_fields:
        # Raises ValueError if not a valid IP address — prevents injection entirely
        ipaddress.ip_address(value)

    elif name in cidr_fields:
        # Raises ValueError if not a valid CIDR block
        ipaddress.ip_network(value, strict=False)

    elif name in domain_fields:
        # Use urlparse to extract hostname; validate with hostname rules
        parsed = urlparse(value if "://" in value else f"https://{value}")
        host = parsed.hostname or ""
        if not host or not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-\.]{0,253}$', host):
            raise ValueError(f"IOC '{name}': invalid domain/FQDN: {repr(value)}")

    elif name in port_fields:
        port_int = int(value)
        if not (1 <= port_int <= 65535):
            raise ValueError(f"IOC '{name}': port out of range: {value}")

    else:
        # Generic IOC: fall back to Ansible variable safety rules
        sanitize_ansible_var(value)

    return value
