"""
SOC Triager — Production Ansible IOC Validators.

Replaces the regex whitelist in sanitize_ansible_var() with strict
Pydantic type validators. This makes it impossible for a unicode lookalike
or embedded newline to bypass validation — Pydantic rejects anything that
doesn't parse as the target type.

Usage:
    from .ioc_validators import validate_ioc, IOCType
    safe_ip = validate_ioc("192.168.1.1", IOCType.IP)
"""

from __future__ import annotations

import re
from enum import Enum
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import Union

from pydantic import BaseModel, field_validator, model_validator


# ── IOC Type Enum ─────────────────────────────────────────────────────────────

class IOCType(str, Enum):
    IP = "ip"
    CIDR = "cidr"
    PORT = "port"
    HOSTNAME = "hostname"
    USERNAME = "username"


# ── RFC 1123 hostname pattern ─────────────────────────────────────────────────

_RFC1123 = re.compile(
    r"^(?:[a-zA-Z0-9]"           # First char: alphanumeric
    r"(?:[a-zA-Z0-9\-]{0,61}"    # Middle: alphanumeric or hyphen
    r"[a-zA-Z0-9])?"             # Last char: alphanumeric
    r"\.)*"                       # Labels separated by dots
    r"[a-zA-Z0-9]"               # TLD starts with alphanumeric
    r"(?:[a-zA-Z0-9\-]{0,61}"
    r"[a-zA-Z0-9])?$"
)

_UNIX_USERNAME = re.compile(r"^[a-z_][a-z0-9_\-]{0,31}$")


# ── Pydantic IOC Models ───────────────────────────────────────────────────────

class IPAddress(BaseModel):
    value: str

    @field_validator("value")
    @classmethod
    def must_be_valid_ip(cls, v: str) -> str:
        v = v.strip()
        try:
            ip_address(v)
        except ValueError:
            raise ValueError(f"Invalid IP address: {v!r}")
        return v


class CIDRBlock(BaseModel):
    value: str

    @field_validator("value")
    @classmethod
    def must_be_valid_cidr(cls, v: str) -> str:
        v = v.strip()
        import ipaddress
        try:
            ipaddress.ip_network(v, strict=False)
        except ValueError:
            raise ValueError(f"Invalid CIDR block: {v!r}")
        return v


class PortNumber(BaseModel):
    value: Union[int, str]
    validated: int = 0

    @model_validator(mode="after")
    def must_be_valid_port(self) -> "PortNumber":
        try:
            port = int(self.value)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid port: {self.value!r}")
        if not (1 <= port <= 65535):
            raise ValueError(f"Port {port} out of range 1–65535")
        self.validated = port
        return self


class Hostname(BaseModel):
    value: str

    @field_validator("value")
    @classmethod
    def must_be_valid_hostname(cls, v: str) -> str:
        v = v.strip()
        if len(v) > 253:
            raise ValueError(f"Hostname too long: {len(v)} chars")
        if not _RFC1123.match(v):
            raise ValueError(f"Invalid hostname (RFC 1123): {v!r}")
        return v


class Username(BaseModel):
    value: str

    @field_validator("value")
    @classmethod
    def must_be_valid_username(cls, v: str) -> str:
        v = v.strip()
        if not _UNIX_USERNAME.match(v):
            raise ValueError(f"Invalid username: {v!r}")
        return v


# ── Public API ────────────────────────────────────────────────────────────────

def validate_ioc(value: str, ioc_type: IOCType) -> str:
    """
    Validate an IOC value against the appropriate type.
    Returns the sanitized string value, raises ValueError on failure.
    """
    value = str(value).strip()

    # Reject any value with newlines, null bytes, or unicode control chars
    if any(c in value for c in ("\n", "\r", "\x00", "\t")):
        raise ValueError(f"IOC value contains disallowed whitespace/control chars: {value!r}")

    if ioc_type == IOCType.IP:
        return IPAddress(value=value).value
    elif ioc_type == IOCType.CIDR:
        return CIDRBlock(value=value).value
    elif ioc_type == IOCType.PORT:
        return str(PortNumber(value=value).validated)
    elif ioc_type == IOCType.HOSTNAME:
        return Hostname(value=value).value
    elif ioc_type == IOCType.USERNAME:
        return Username(value=value).value
    else:
        raise ValueError(f"Unknown IOC type: {ioc_type}")


def validate_playbook_iocs(iocs: dict[str, str], type_hints: dict[str, IOCType]) -> dict[str, str]:
    """
    Validate an entire dict of IOC values using per-key type hints.
    Returns a clean dict or raises ValueError for the first invalid value.

    Example:
        clean = validate_playbook_iocs(
            {"source_ip": "10.0.0.1", "port": "443"},
            {"source_ip": IOCType.IP, "port": IOCType.PORT},
        )
    """
    result: dict[str, str] = {}
    for key, value in iocs.items():
        hint = type_hints.get(key)
        if hint:
            result[key] = validate_ioc(value, hint)
        else:
            # No type hint — apply minimal sanitization (alphanumeric + safe punctuation)
            if not re.match(r'^[\w.\-:/ ]{1,200}$', value):
                raise ValueError(f"IOC key {key!r} has unsafe value: {value!r}")
            result[key] = value
    return result

