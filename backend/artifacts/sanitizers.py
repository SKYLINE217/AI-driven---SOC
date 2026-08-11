"""
Security sanitizers for artifact generation.
Per soc-triager-security skill: every log field must be sanitized before
reaching a Markdown template, Mermaid graph, or Ansible playbook.
"""

from __future__ import annotations

import html
import re


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
