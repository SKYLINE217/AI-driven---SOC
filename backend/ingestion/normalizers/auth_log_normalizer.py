"""
Auth Log Normalizer — Parses Linux /var/log/auth.log lines into ECS NormalizedEvent.

Handles common auth.log patterns:
    - SSH authentication (failed/accepted password, publickey)
    - sudo commands
    - su session open/close
    - PAM authentication events
    - CRON sessions
"""

import re
from datetime import datetime

from backend.models import (
    DestinationInfo,
    EventInfo,
    HostInfo,
    LogInfo,
    NormalizedEvent,
    SourceInfo,
    UserInfo,
)

# ─── Regex Patterns ──────────────────────────────────────────────────────────

# Timestamp + hostname + program header
AUTH_HEADER_RE = re.compile(
    r"^(?P<month>\w{3})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<hostname>\S+)\s+(?P<program>\S+?)(?:\[(?P<pid>\d+)\])?\s*:\s*(?P<message>.*)$"
)

# SSH failed password
SSH_FAILED_RE = re.compile(
    r"Failed password for (?:invalid user )?(?P<user>\S+) from (?P<ip>[\d.]+) port (?P<port>\d+)"
)

# SSH accepted (password or publickey)
SSH_ACCEPTED_RE = re.compile(
    r"Accepted (?:password|publickey) for (?P<user>\S+) from (?P<ip>[\d.]+) port (?P<port>\d+)"
)

# SSH invalid user attempt
SSH_INVALID_USER_RE = re.compile(
    r"Invalid user (?P<user>\S+) from (?P<ip>[\d.]+)"
)

# sudo command execution
SUDO_RE = re.compile(
    r"(?P<user>\S+)\s*:\s*TTY=\S+\s*;\s*PWD=\S+\s*;\s*USER=(?P<target_user>\S+)\s*;\s*COMMAND=(?P<command>.*)"
)

# su session open
SU_SESSION_RE = re.compile(
    r"pam_unix\(su(?:-l)?:session\):\s*session (?P<action>opened|closed) for user (?P<user>\S+)"
)

# PAM authentication failure
PAM_FAILURE_RE = re.compile(
    r"pam_unix\(\S+:auth\):\s*authentication failure.*?user=(?P<user>\S+)"
)


def _parse_auth_timestamp(month: str, day: str, time_str: str) -> datetime:
    """Parse auth.log timestamp (BSD syslog format), assuming current year."""
    year = datetime.utcnow().year
    try:
        return datetime.strptime(f"{year} {month} {day} {time_str}", "%Y %b %d %H:%M:%S")
    except ValueError:
        return datetime.utcnow()


def _classify_auth_message(message: str, program: str) -> dict:
    """
    Classify an auth.log message into an ECS event action + outcome + metadata.
    Returns a dict with action, outcome, category, user, source_ip, source_port.
    """
    # SSH failed password
    m = SSH_FAILED_RE.search(message)
    if m:
        return {
            "action": "ssh_login_failed",
            "outcome": "failure",
            "category": ["authentication"],
            "user": m.group("user"),
            "source_ip": m.group("ip"),
            "source_port": int(m.group("port")),
        }

    # SSH accepted
    m = SSH_ACCEPTED_RE.search(message)
    if m:
        return {
            "action": "ssh_login_success",
            "outcome": "success",
            "category": ["authentication"],
            "user": m.group("user"),
            "source_ip": m.group("ip"),
            "source_port": int(m.group("port")),
        }

    # SSH invalid user
    m = SSH_INVALID_USER_RE.search(message)
    if m:
        return {
            "action": "ssh_invalid_user",
            "outcome": "failure",
            "category": ["authentication"],
            "user": m.group("user"),
            "source_ip": m.group("ip"),
            "source_port": None,
        }

    # sudo
    m = SUDO_RE.search(message)
    if m:
        return {
            "action": "sudo_command",
            "outcome": "success",
            "category": ["process", "iam"],
            "user": m.group("user"),
            "source_ip": None,
            "source_port": None,
        }

    # su session
    m = SU_SESSION_RE.search(message)
    if m:
        action = "su_session_opened" if m.group("action") == "opened" else "su_session_closed"
        return {
            "action": action,
            "outcome": "success",
            "category": ["authentication", "session"],
            "user": m.group("user"),
            "source_ip": None,
            "source_port": None,
        }

    # PAM failure
    m = PAM_FAILURE_RE.search(message)
    if m:
        return {
            "action": "pam_auth_failure",
            "outcome": "failure",
            "category": ["authentication"],
            "user": m.group("user"),
            "source_ip": None,
            "source_port": None,
        }

    # CRON job (common in auth.log)
    if "CRON" in program.upper():
        return {
            "action": "cron_session",
            "outcome": "success",
            "category": ["process"],
            "user": None,
            "source_ip": None,
            "source_port": None,
        }

    # Unclassified — still capture it
    return {
        "action": "auth_event",
        "outcome": "unknown",
        "category": ["authentication"],
        "user": None,
        "source_ip": None,
        "source_port": None,
    }


def normalize_auth_log(raw_line: str) -> NormalizedEvent:
    """
    Parse a Linux auth.log line into an ECS NormalizedEvent.

    Handles SSH, sudo, su, PAM, and CRON events.
    Falls back to sensible defaults for malformed or unrecognized lines.
    """
    raw_line = raw_line.strip()

    hostname = "unknown"
    program = "unknown"
    message = raw_line
    timestamp = datetime.utcnow()

    # Parse the syslog-style header
    header_match = AUTH_HEADER_RE.match(raw_line)
    if header_match:
        hostname = header_match.group("hostname")
        program = header_match.group("program")
        message = header_match.group("message")
        timestamp = _parse_auth_timestamp(
            header_match.group("month"),
            header_match.group("day"),
            header_match.group("time"),
        )

    # Classify the message
    ctx = _classify_auth_message(message, program)

    event = NormalizedEvent(
        timestamp=timestamp,
        event=EventInfo(
            kind="event",
            category=ctx["category"],
            action=ctx["action"],
            outcome=ctx["outcome"],
        ),
        source=SourceInfo(
            ip=ctx["source_ip"],
            port=ctx["source_port"],
        ),
        destination=DestinationInfo(
            host=hostname,
            port=22 if "ssh" in ctx["action"] else None,
        ),
        user=UserInfo(
            name=ctx["user"],
        ),
        host=HostInfo(
            name=hostname,
            os_family="linux",
        ),
        log=LogInfo(
            source_type="auth_log",
            raw=raw_line,
        ),
    )

    event.related.hash = event.compute_chain_hash()
    return event
