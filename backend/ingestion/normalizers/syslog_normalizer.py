"""
Syslog Normalizer — Parses RFC5424 syslog lines into ECS NormalizedEvent.

Handles standard syslog format:
    <priority>version timestamp hostname app-name procid msgid msg
    or BSD-style: Mon DD HH:MM:SS hostname program[pid]: message
"""

import re
from datetime import UTC, datetime
from typing import Optional

from ...models import (
    DestinationInfo,
    EventInfo,
    HostInfo,
    LogInfo,
    NormalizedEvent,
    SourceInfo,
    UserInfo,
)

# BSD syslog pattern: "Aug 10 09:14:22 hostname program[pid]: message"
BSD_SYSLOG_RE = re.compile(
    r"^(?P<month>\w{3})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<hostname>\S+)\s+(?P<program>\S+?)(?:\[(?P<pid>\d+)\])?\s*:\s*(?P<message>.*)$"
)

# RFC5424 pattern: "<PRI>VERSION TIMESTAMP HOSTNAME APP-NAME PROCID MSGID MSG"
RFC5424_RE = re.compile(
    r"^<(?P<pri>\d{1,3})>(?P<version>\d)?\s*"
    r"(?P<timestamp>\S+)\s+(?P<hostname>\S+)\s+(?P<appname>\S+)\s+"
    r"(?P<procid>\S+)\s+(?P<msgid>\S+)\s*(?P<msg>.*)$"
)

# Common SSH patterns inside syslog messages
SSH_FAILED_RE = re.compile(
    r"Failed password for (?:invalid user )?(?P<user>\S+) from (?P<ip>[\d.]+) port (?P<port>\d+)"
)
SSH_SUCCESS_RE = re.compile(
    r"Accepted (?:password|publickey) for (?P<user>\S+) from (?P<ip>[\d.]+) port (?P<port>\d+)"
)


def _parse_bsd_timestamp(month: str, day: str, time_str: str) -> datetime:
    """Parse BSD syslog timestamp, assuming current year."""
    year = datetime.now(UTC).year
    try:
        return datetime.strptime(f"{year} {month} {day} {time_str}", "%Y %b %d %H:%M:%S")
    except ValueError:
        return datetime.now(UTC)


def _extract_ssh_context(message: str) -> dict:
    """Extract SSH-specific fields from a syslog message."""
    failed = SSH_FAILED_RE.search(message)
    if failed:
        return {
            "action": "ssh_login_failed",
            "outcome": "failure",
            "category": ["authentication"],
            "user": failed.group("user"),
            "source_ip": failed.group("ip"),
            "source_port": int(failed.group("port")),
        }

    success = SSH_SUCCESS_RE.search(message)
    if success:
        return {
            "action": "ssh_login_success",
            "outcome": "success",
            "category": ["authentication"],
            "user": success.group("user"),
            "source_ip": success.group("ip"),
            "source_port": int(success.group("port")),
        }

    return {
        "action": "syslog_message",
        "outcome": "unknown",
        "category": ["process"],
        "user": None,
        "source_ip": None,
        "source_port": None,
    }


def normalize_syslog(raw_line: str) -> NormalizedEvent:
    """
    Parse a syslog line (BSD or RFC5424) into an ECS NormalizedEvent.

    Falls back to sensible defaults for malformed or partial lines —
    never raises on bad input.
    """
    raw_line = raw_line.strip()

    hostname = "unknown"
    program = "unknown"
    message = raw_line
    timestamp = datetime.now(UTC)

    # Try BSD format first (more common in auth.log-style syslog)
    bsd_match = BSD_SYSLOG_RE.match(raw_line)
    if bsd_match:
        hostname = bsd_match.group("hostname")
        program = bsd_match.group("program")
        message = bsd_match.group("message")
        timestamp = _parse_bsd_timestamp(
            bsd_match.group("month"),
            bsd_match.group("day"),
            bsd_match.group("time"),
        )
    else:
        # Try RFC5424 format
        rfc_match = RFC5424_RE.match(raw_line)
        if rfc_match:
            hostname = rfc_match.group("hostname")
            program = rfc_match.group("appname")
            message = rfc_match.group("msg")
            ts_str = rfc_match.group("timestamp")
            try:
                timestamp = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                timestamp = datetime.now(UTC)

    # Extract SSH-specific context from the message body
    ssh_ctx = _extract_ssh_context(message)

    event = NormalizedEvent(
        timestamp=timestamp,
        event=EventInfo(
            kind="event",
            category=ssh_ctx["category"],
            action=ssh_ctx["action"],
            outcome=ssh_ctx["outcome"],
        ),
        source=SourceInfo(
            ip=ssh_ctx["source_ip"],
            port=ssh_ctx["source_port"],
        ),
        destination=DestinationInfo(
            host=hostname,
        ),
        user=UserInfo(
            name=ssh_ctx["user"],
        ),
        host=HostInfo(
            name=hostname,
            os_family="linux",
        ),
        log=LogInfo(
            source_type="syslog",
            raw=raw_line,
        ),
    )

    # Compute chain-of-custody hash
    event.related.hash = event.compute_chain_hash()

    return event

