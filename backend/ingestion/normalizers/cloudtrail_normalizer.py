"""
CloudTrail Normalizer — Maps AWS CloudTrail JSON events into ECS NormalizedEvent.

CloudTrail events have a well-defined JSON schema:
{
    "eventTime": "2026-08-10T09:14:22Z",
    "eventSource": "iam.amazonaws.com",
    "eventName": "ConsoleLogin",
    "sourceIPAddress": "203.0.113.44",
    "userIdentity": { "type": "IAMUser", "userName": "alice", "arn": "..." },
    "responseElements": { "ConsoleLogin": "Failure" },
    ...
}
"""

import json
from datetime import UTC, datetime
from typing import Any

from backend.models import (
    DestinationInfo,
    EventInfo,
    HostInfo,
    LogInfo,
    NormalizedEvent,
    SourceInfo,
    UserInfo,
)

# Mapping CloudTrail eventName to ECS action + category
EVENT_MAP: dict[str, dict[str, Any]] = {
    "ConsoleLogin": {
        "action": "console_login",
        "category": ["authentication"],
    },
    "CreateUser": {
        "action": "user_created",
        "category": ["iam"],
    },
    "DeleteUser": {
        "action": "user_deleted",
        "category": ["iam"],
    },
    "AttachUserPolicy": {
        "action": "policy_attached",
        "category": ["iam", "configuration"],
    },
    "CreateAccessKey": {
        "action": "access_key_created",
        "category": ["iam"],
    },
    "AuthorizeSecurityGroupIngress": {
        "action": "security_group_modified",
        "category": ["network", "configuration"],
    },
    "RunInstances": {
        "action": "instance_launched",
        "category": ["host"],
    },
    "StopInstances": {
        "action": "instance_stopped",
        "category": ["host"],
    },
    "GetObject": {
        "action": "s3_object_read",
        "category": ["file"],
    },
    "PutObject": {
        "action": "s3_object_write",
        "category": ["file"],
    },
    "AssumeRole": {
        "action": "role_assumed",
        "category": ["authentication", "iam"],
    },
}


def _determine_outcome(event: dict) -> str:
    """Determine success/failure from CloudTrail response elements."""
    error_code = event.get("errorCode")
    if error_code:
        return "failure"

    response = event.get("responseElements") or {}

    # ConsoleLogin has a specific response pattern
    if isinstance(response, dict):
        login_result = response.get("ConsoleLogin", "")
        if login_result == "Failure":
            return "failure"
        if login_result == "Success":
            return "success"

    return "success"


def _extract_user_info(event: dict) -> UserInfo:
    """Extract user identity from CloudTrail userIdentity block."""
    identity = event.get("userIdentity", {})
    return UserInfo(
        name=identity.get("userName", identity.get("principalId", "unknown")),
        id=identity.get("arn", ""),
        domain=identity.get("accountId", ""),
    )


def normalize_cloudtrail(raw_input: str | dict) -> NormalizedEvent:
    """
    Parse an AWS CloudTrail JSON event into an ECS NormalizedEvent.

    Accepts either a JSON string or an already-parsed dict.
    Falls back to sensible defaults for missing or malformed fields.
    """
    if isinstance(raw_input, str):
        try:
            event = json.loads(raw_input)
        except json.JSONDecodeError:
            # Malformed JSON — create a minimal event
            return NormalizedEvent(
                timestamp=datetime.now(UTC),
                event=EventInfo(
                    kind="event",
                    category=["process"],
                    action="cloudtrail_parse_error",
                    outcome="unknown",
                ),
                log=LogInfo(source_type="cloudtrail", raw=raw_input),
            )
    else:
        event = raw_input

    raw_str = json.dumps(event) if isinstance(event, dict) else str(event)

    # Parse timestamp
    try:
        timestamp = datetime.fromisoformat(
            event.get("eventTime", "").replace("Z", "+00:00")
        ).replace(tzinfo=None)
    except (ValueError, AttributeError):
        timestamp = datetime.now(UTC)

    # Map event name to ECS action and category
    event_name = event.get("eventName", "unknown_action")
    mapping = EVENT_MAP.get(event_name, {
        "action": event_name.lower(),
        "category": ["process"],
    })

    outcome = _determine_outcome(event)

    # Build the normalized event
    normalized = NormalizedEvent(
        timestamp=timestamp,
        event=EventInfo(
            kind="event",
            category=mapping["category"],
            action=mapping["action"],
            outcome=outcome,
        ),
        source=SourceInfo(
            ip=event.get("sourceIPAddress"),
        ),
        destination=DestinationInfo(
            host=event.get("eventSource", "").replace(".amazonaws.com", ""),
        ),
        user=_extract_user_info(event),
        host=HostInfo(
            name=event.get("eventSource", "aws"),
        ),
        log=LogInfo(
            source_type="cloudtrail",
            raw=raw_str,
        ),
    )

    normalized.related.hash = normalized.compute_chain_hash()
    return normalized
