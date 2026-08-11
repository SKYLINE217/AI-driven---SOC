"""
Synthetic CloudTrail Generator — Generates AWS CloudTrail JSON events with
injected attack patterns for testing and demo scenarios.

Attack patterns:
    - Credential stuffing: repeated ConsoleLogin failures from one IP
    - IAM privilege escalation: AttachUserPolicy with AdminAccess
    - Data exfiltration: high-volume S3 GetObject calls
    - Reconnaissance: excessive DescribeInstances / ListBuckets calls
"""

import json
import random
import uuid
from datetime import datetime, timedelta
from typing import Any, Generator

# ─── Configuration ───────────────────────────────────────────────────────────

LEGITIMATE_USERS = [
    {"userName": "alice.dev", "arn": "arn:aws:iam::123456789012:user/alice.dev", "accountId": "123456789012"},
    {"userName": "bob.ops", "arn": "arn:aws:iam::123456789012:user/bob.ops", "accountId": "123456789012"},
    {"userName": "ci-runner", "arn": "arn:aws:iam::123456789012:user/ci-runner", "accountId": "123456789012"},
]

ATTACKER_IPS = ["203.0.113.44", "198.51.100.77", "192.0.2.111"]
LEGITIMATE_IPS = ["10.0.1.10", "10.0.1.22", "172.16.0.15", "54.200.100.50"]

AWS_REGIONS = ["us-east-1", "us-west-2", "eu-west-1"]
S3_BUCKETS = ["company-data-prod", "customer-records", "backup-vault", "logs-archive"]


def _build_event(
    event_name: str,
    event_source: str,
    timestamp: datetime,
    user_identity: dict,
    source_ip: str,
    response_elements: dict | None = None,
    request_parameters: dict | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    region: str = "us-east-1",
) -> dict[str, Any]:
    """Build a CloudTrail-format event dict."""
    event: dict[str, Any] = {
        "eventVersion": "1.09",
        "eventTime": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "eventSource": event_source,
        "eventName": event_name,
        "awsRegion": region,
        "sourceIPAddress": source_ip,
        "userAgent": "aws-cli/2.15.0 Python/3.11.6 Linux/6.1.0",
        "userIdentity": {
            "type": "IAMUser",
            "principalId": f"AIDA{uuid.uuid4().hex[:16].upper()}",
            **user_identity,
        },
        "eventID": str(uuid.uuid4()),
        "readOnly": event_name.startswith(("Get", "List", "Describe")),
        "eventType": "AwsApiCall",
        "managementEvent": True,
        "recipientAccountId": user_identity.get("accountId", "123456789012"),
    }

    if response_elements is not None:
        event["responseElements"] = response_elements
    if request_parameters is not None:
        event["requestParameters"] = request_parameters
    if error_code:
        event["errorCode"] = error_code
        event["errorMessage"] = error_message or "Access Denied"

    return event


def generate_normal_cloudtrail(
    start_time: datetime,
    duration_minutes: int = 60,
    events_per_minute: float = 1.5,
) -> Generator[str, None, None]:
    """Generate benign CloudTrail events — routine API calls."""
    current = start_time
    end_time = start_time + timedelta(minutes=duration_minutes)

    normal_operations = [
        ("DescribeInstances", "ec2.amazonaws.com"),
        ("ListBuckets", "s3.amazonaws.com"),
        ("GetObject", "s3.amazonaws.com"),
        ("PutObject", "s3.amazonaws.com"),
        ("DescribeSecurityGroups", "ec2.amazonaws.com"),
        ("AssumeRole", "sts.amazonaws.com"),
        ("GetCallerIdentity", "sts.amazonaws.com"),
    ]

    while current < end_time:
        interval = timedelta(seconds=random.expovariate(events_per_minute / 60.0))
        current += interval
        if current >= end_time:
            break

        user = random.choice(LEGITIMATE_USERS)
        ip = random.choice(LEGITIMATE_IPS)
        op_name, op_source = random.choice(normal_operations)
        region = random.choice(AWS_REGIONS)

        request_params = {}
        if op_name == "GetObject":
            request_params = {
                "bucketName": random.choice(S3_BUCKETS),
                "key": f"data/{random.choice(['report', 'config', 'log'])}-{random.randint(1,100)}.json",
            }

        event = _build_event(
            event_name=op_name,
            event_source=op_source,
            timestamp=current,
            user_identity=user,
            source_ip=ip,
            region=region,
            request_parameters=request_params if request_params else None,
            response_elements={"status": "Success"} if not op_name.startswith(("Get", "List", "Describe")) else None,
        )

        yield json.dumps(event)


def generate_credential_stuffing(
    start_time: datetime,
    attacker_ip: str = "203.0.113.44",
    num_attempts: int = 15,
    duration_seconds: float = 120.0,
) -> Generator[str, None, None]:
    """
    Generate a credential stuffing attack:
    - Multiple failed ConsoleLogin attempts from one IP
    - Targeting different usernames
    """
    interval = duration_seconds / num_attempts
    current = start_time

    target_users = [
        {"userName": f"admin{i}", "accountId": "123456789012"}
        for i in range(1, 8)
    ] + [
        {"userName": "root", "accountId": "123456789012"},
        {"userName": "administrator", "accountId": "123456789012"},
    ]

    for i in range(num_attempts):
        user = target_users[i % len(target_users)]
        ts = current

        event = _build_event(
            event_name="ConsoleLogin",
            event_source="signin.amazonaws.com",
            timestamp=ts,
            user_identity=user,
            source_ip=attacker_ip,
            response_elements={"ConsoleLogin": "Failure"},
            error_code="Failed authentication",
            error_message=f"No username found in the given account: {user['userName']}",
        )

        yield json.dumps(event)
        current += timedelta(seconds=interval + random.uniform(-1.0, 1.0))


def generate_iam_escalation(
    start_time: datetime,
    attacker_ip: str = "198.51.100.77",
    compromised_user: str = "ci-runner",
) -> Generator[str, None, None]:
    """
    Generate an IAM privilege escalation attack:
    - CreateUser → CreateAccessKey → AttachUserPolicy (AdministratorAccess)
    """
    user_identity = {
        "userName": compromised_user,
        "arn": f"arn:aws:iam::123456789012:user/{compromised_user}",
        "accountId": "123456789012",
    }
    current = start_time

    # Step 1: Create a new backdoor user
    yield json.dumps(_build_event(
        event_name="CreateUser",
        event_source="iam.amazonaws.com",
        timestamp=current,
        user_identity=user_identity,
        source_ip=attacker_ip,
        request_parameters={"userName": "backdoor-admin"},
        response_elements={"user": {"userName": "backdoor-admin"}},
    ))
    current += timedelta(seconds=5)

    # Step 2: Create access key for the backdoor user
    yield json.dumps(_build_event(
        event_name="CreateAccessKey",
        event_source="iam.amazonaws.com",
        timestamp=current,
        user_identity=user_identity,
        source_ip=attacker_ip,
        request_parameters={"userName": "backdoor-admin"},
        response_elements={"accessKey": {"accessKeyId": "AKIA" + uuid.uuid4().hex[:16].upper()}},
    ))
    current += timedelta(seconds=3)

    # Step 3: Attach AdministratorAccess policy to the backdoor user
    yield json.dumps(_build_event(
        event_name="AttachUserPolicy",
        event_source="iam.amazonaws.com",
        timestamp=current,
        user_identity=user_identity,
        source_ip=attacker_ip,
        request_parameters={
            "userName": "backdoor-admin",
            "policyArn": "arn:aws:iam::aws:policy/AdministratorAccess",
        },
    ))


def generate_data_exfiltration(
    start_time: datetime,
    attacker_ip: str = "192.0.2.111",
    num_objects: int = 50,
    duration_seconds: float = 300.0,
) -> Generator[str, None, None]:
    """
    Generate a data exfiltration pattern:
    - High-volume S3 GetObject calls from an unusual IP
    - Targeting sensitive bucket
    """
    interval = duration_seconds / num_objects
    current = start_time
    compromised_user = {
        "userName": "ci-runner",
        "arn": "arn:aws:iam::123456789012:user/ci-runner",
        "accountId": "123456789012",
    }

    for i in range(num_objects):
        event = _build_event(
            event_name="GetObject",
            event_source="s3.amazonaws.com",
            timestamp=current,
            user_identity=compromised_user,
            source_ip=attacker_ip,
            request_parameters={
                "bucketName": "customer-records",
                "key": f"exports/customers-batch-{i:04d}.csv",
            },
        )
        yield json.dumps(event)
        current += timedelta(seconds=interval + random.uniform(-0.5, 0.5))


def generate_full_scenario(
    start_time: datetime | None = None,
) -> Generator[str, None, None]:
    """
    Generate a complete multi-stage CloudTrail attack scenario:

    1. T+0min:   Normal API activity
    2. T+5min:   Credential stuffing (15 failed console logins)
    3. T+8min:   IAM privilege escalation (create backdoor user)
    4. T+10min:  Data exfiltration (50 S3 GetObject calls)
    5. T+15min:  Normal traffic continues
    """
    if start_time is None:
        start_time = datetime.utcnow()

    # Phase 1: Normal traffic
    yield from generate_normal_cloudtrail(start_time, duration_minutes=5)

    # Phase 2: Credential stuffing at T+5min
    yield from generate_credential_stuffing(start_time + timedelta(minutes=5))

    # Phase 3: IAM escalation at T+8min
    yield from generate_iam_escalation(start_time + timedelta(minutes=8))

    # Phase 4: Data exfiltration at T+10min
    yield from generate_data_exfiltration(start_time + timedelta(minutes=10))

    # Phase 5: Normal traffic continues
    yield from generate_normal_cloudtrail(
        start_time + timedelta(minutes=15),
        duration_minutes=5,
    )


if __name__ == "__main__":
    """Generate and print a full scenario to stdout for testing."""
    for line in generate_full_scenario():
        print(line)
