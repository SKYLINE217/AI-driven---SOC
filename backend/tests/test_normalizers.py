"""
Unit Tests for Source Normalizers — Engineer A Day 1

Tests cover:
    - Happy path with valid sample lines
    - Lines with missing fields (should not raise — uses defaults)
    - Lines with injected special characters (should not raise)
    - Correct ECS field mapping for each source type
"""

import json
from datetime import datetime

import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.models import NormalizedEvent
from backend.ingestion.normalizers import get_normalizer, list_source_types
from backend.ingestion.normalizers.syslog_normalizer import normalize_syslog
from backend.ingestion.normalizers.cloudtrail_normalizer import normalize_cloudtrail
from backend.ingestion.normalizers.auth_log_normalizer import normalize_auth_log
from backend.ingestion.normalizers.cicids_normalizer import normalize_cicids


# ═══════════════════════════════════════════════════════════════════════════════
# Normalizer Registry Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestNormalizerRegistry:

    def test_get_normalizer_syslog(self):
        fn = get_normalizer("syslog")
        assert fn is normalize_syslog

    def test_get_normalizer_cloudtrail(self):
        fn = get_normalizer("cloudtrail")
        assert fn is normalize_cloudtrail

    def test_get_normalizer_auth_log(self):
        fn = get_normalizer("auth_log")
        assert fn is normalize_auth_log

    def test_get_normalizer_auth_alias(self):
        fn = get_normalizer("auth")
        assert fn is normalize_auth_log

    def test_get_normalizer_cicids(self):
        fn = get_normalizer("cicids")
        assert fn is normalize_cicids

    def test_get_normalizer_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown source type"):
            get_normalizer("unknown_format")

    def test_get_normalizer_case_insensitive(self):
        fn = get_normalizer("SYSLOG")
        assert fn is normalize_syslog

    def test_list_source_types(self):
        types = list_source_types()
        assert "syslog" in types
        assert "cloudtrail" in types
        assert "auth_log" in types
        assert "cicids" in types


# ═══════════════════════════════════════════════════════════════════════════════
# Syslog Normalizer Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSyslogNormalizer:

    def test_ssh_failed_password(self):
        line = "Aug 10 09:14:22 prod-db-03 sshd[1234]: Failed password for root from 203.0.113.44 port 49312 ssh2"
        event = normalize_syslog(line)

        assert isinstance(event, NormalizedEvent)
        assert event.event.action == "ssh_login_failed"
        assert event.event.outcome == "failure"
        assert "authentication" in event.event.category
        assert event.source.ip == "203.0.113.44"
        assert event.source.port == 49312
        assert event.user.name == "root"
        assert event.host.name == "prod-db-03"
        assert event.log.source_type == "syslog"
        assert event.log.raw == line
        assert event.related.hash is not None

    def test_ssh_accepted_publickey(self):
        line = "Aug 10 10:00:05 web-01 sshd[5678]: Accepted publickey for alice from 10.0.1.10 port 49200 ssh2"
        event = normalize_syslog(line)

        assert event.event.action == "ssh_login_success"
        assert event.event.outcome == "success"
        assert event.source.ip == "10.0.1.10"
        assert event.user.name == "alice"

    def test_non_ssh_syslog(self):
        line = "Aug 10 11:22:33 router1 kernel: [123456.789] eth0: link up"
        event = normalize_syslog(line)

        assert event.event.action == "syslog_message"
        assert event.event.outcome == "unknown"
        assert event.host.name == "router1"

    def test_missing_fields_no_raise(self):
        """Partial or malformed lines should not raise — use defaults."""
        line = "some random garbage that is not valid syslog at all"
        event = normalize_syslog(line)

        assert isinstance(event, NormalizedEvent)
        assert event.event.action == "syslog_message"
        assert event.log.raw == line

    def test_special_characters_no_raise(self):
        """Lines with injected special chars (potential injection) should not raise."""
        line = 'Aug 10 09:00:00 host sshd[1]: Failed password for <script>alert("xss")</script> from 1.2.3.4 port 22 ssh2'
        event = normalize_syslog(line)
        assert isinstance(event, NormalizedEvent)
        # The username captures the injected string but the normalizer doesn't crash
        assert event.source.ip == "1.2.3.4"

    def test_empty_line(self):
        event = normalize_syslog("")
        assert isinstance(event, NormalizedEvent)
        assert event.log.raw == ""

    def test_rfc5424_format(self):
        line = '<134>1 2026-08-10T09:14:22Z prod-db-03 sshd 1234 - - Failed password for root from 203.0.113.44 port 49312 ssh2'
        event = normalize_syslog(line)
        assert isinstance(event, NormalizedEvent)
        assert event.host.name == "prod-db-03"


# ═══════════════════════════════════════════════════════════════════════════════
# CloudTrail Normalizer Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestCloudTrailNormalizer:

    SAMPLE_LOGIN_FAILURE = {
        "eventTime": "2026-08-10T09:14:22Z",
        "eventSource": "signin.amazonaws.com",
        "eventName": "ConsoleLogin",
        "sourceIPAddress": "203.0.113.44",
        "userIdentity": {
            "type": "IAMUser",
            "userName": "alice",
            "arn": "arn:aws:iam::123456789012:user/alice",
            "accountId": "123456789012",
        },
        "responseElements": {"ConsoleLogin": "Failure"},
        "errorCode": "Failed authentication",
    }

    SAMPLE_LOGIN_SUCCESS = {
        "eventTime": "2026-08-10T10:00:00Z",
        "eventSource": "signin.amazonaws.com",
        "eventName": "ConsoleLogin",
        "sourceIPAddress": "10.0.1.10",
        "userIdentity": {
            "type": "IAMUser",
            "userName": "bob",
            "accountId": "123456789012",
        },
        "responseElements": {"ConsoleLogin": "Success"},
    }

    def test_console_login_failure(self):
        event = normalize_cloudtrail(self.SAMPLE_LOGIN_FAILURE)

        assert isinstance(event, NormalizedEvent)
        assert event.event.action == "console_login"
        assert event.event.outcome == "failure"
        assert "authentication" in event.event.category
        assert event.source.ip == "203.0.113.44"
        assert event.user.name == "alice"
        assert event.log.source_type == "cloudtrail"
        assert event.related.hash is not None

    def test_console_login_success(self):
        event = normalize_cloudtrail(self.SAMPLE_LOGIN_SUCCESS)

        assert event.event.action == "console_login"
        assert event.event.outcome == "success"
        assert event.user.name == "bob"

    def test_json_string_input(self):
        """Accepts JSON string as well as dict."""
        json_str = json.dumps(self.SAMPLE_LOGIN_FAILURE)
        event = normalize_cloudtrail(json_str)

        assert event.event.action == "console_login"
        assert event.source.ip == "203.0.113.44"

    def test_invalid_json_no_raise(self):
        """Malformed JSON should not raise."""
        event = normalize_cloudtrail("not valid json at all {{{")

        assert isinstance(event, NormalizedEvent)
        assert event.event.action == "cloudtrail_parse_error"

    def test_missing_fields_no_raise(self):
        """CloudTrail event with missing optional fields."""
        event = normalize_cloudtrail({"eventName": "Unknown"})

        assert isinstance(event, NormalizedEvent)
        assert event.event.action == "unknown"

    def test_special_characters_no_raise(self):
        """Event with injected special characters."""
        event_dict = {
            "eventTime": "2026-08-10T09:00:00Z",
            "eventName": "ConsoleLogin",
            "sourceIPAddress": "<script>alert(1)</script>",
            "userIdentity": {"userName": "'; DROP TABLE users;--"},
        }
        event = normalize_cloudtrail(event_dict)
        assert isinstance(event, NormalizedEvent)

    def test_create_user_event(self):
        event_dict = {
            "eventTime": "2026-08-10T09:00:00Z",
            "eventSource": "iam.amazonaws.com",
            "eventName": "CreateUser",
            "sourceIPAddress": "10.0.1.10",
            "userIdentity": {"userName": "admin", "accountId": "123456789012"},
        }
        event = normalize_cloudtrail(event_dict)
        assert event.event.action == "user_created"
        assert "iam" in event.event.category


# ═══════════════════════════════════════════════════════════════════════════════
# Auth Log Normalizer Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuthLogNormalizer:

    def test_ssh_failed_password(self):
        line = "Aug 10 09:14:22 prod-db-03 sshd[1234]: Failed password for svc-backup from 203.0.113.44 port 49312 ssh2"
        event = normalize_auth_log(line)

        assert isinstance(event, NormalizedEvent)
        assert event.event.action == "ssh_login_failed"
        assert event.event.outcome == "failure"
        assert "authentication" in event.event.category
        assert event.source.ip == "203.0.113.44"
        assert event.source.port == 49312
        assert event.user.name == "svc-backup"
        assert event.host.name == "prod-db-03"
        assert event.log.source_type == "auth_log"
        assert event.destination.port == 22  # SSH

    def test_ssh_accepted_password(self):
        line = "Aug 10 10:00:05 web-01 sshd[5678]: Accepted password for alice from 10.0.1.10 port 49200 ssh2"
        event = normalize_auth_log(line)

        assert event.event.action == "ssh_login_success"
        assert event.event.outcome == "success"

    def test_invalid_user(self):
        line = "Aug 10 09:14:23 prod-db-03 sshd[1234]: Invalid user hacker from 203.0.113.44 port 49312"
        event = normalize_auth_log(line)

        assert event.event.action == "ssh_invalid_user"
        assert event.event.outcome == "failure"
        assert event.user.name == "hacker"
        assert event.source.ip == "203.0.113.44"

    def test_sudo_command(self):
        line = "Aug 10 09:30:00 prod-db-03 sudo[2345]: alice : TTY=pts/0 ; PWD=/home/alice ; USER=root ; COMMAND=/usr/bin/systemctl restart nginx"
        event = normalize_auth_log(line)

        assert event.event.action == "sudo_command"
        assert event.event.outcome == "success"
        assert event.user.name == "alice"

    def test_pam_auth_failure(self):
        line = "Aug 10 09:14:22 prod-db-03 sshd[1234]: pam_unix(sshd:auth): authentication failure; logname= uid=0 euid=0 tty=ssh ruser= rhost=203.0.113.44 user=root"
        event = normalize_auth_log(line)

        assert event.event.action == "pam_auth_failure"
        assert event.event.outcome == "failure"
        assert event.user.name == "root"

    def test_cron_session(self):
        line = "Aug 10 12:00:00 prod-db-03 CRON[3456]: pam_unix(cron:session): session opened for user root(uid=0) by (uid=0)"
        event = normalize_auth_log(line)

        assert event.event.action == "cron_session"

    def test_missing_fields_no_raise(self):
        line = "this is not a valid auth log line"
        event = normalize_auth_log(line)

        assert isinstance(event, NormalizedEvent)
        assert event.log.source_type == "auth_log"

    def test_special_characters_no_raise(self):
        line = 'Aug 10 09:00:00 host sshd[1]: Failed password for <img src=x onerror=alert(1)> from 1.2.3.4 port 22 ssh2'
        event = normalize_auth_log(line)
        assert isinstance(event, NormalizedEvent)

    def test_empty_line(self):
        event = normalize_auth_log("")
        assert isinstance(event, NormalizedEvent)


# ═══════════════════════════════════════════════════════════════════════════════
# CICIDS2017 Normalizer Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestCICIDSNormalizer:

    SAMPLE_BENIGN = {
        " Source IP": "10.0.1.10",
        " Destination IP": "10.0.2.5",
        " Source Port": "49200",
        " Destination Port": "80",
        " Flow Duration": "1234567",
        " Total Fwd Packets": "10",
        " Total Backward Packets": "8",
        "Flow Bytes/s": "1500.5",
        "Flow Packets/s": "50.2",
        " Fwd Packet Length Mean": "120.5",
        " Bwd Packet Length Mean": "85.3",
        " Flow IAT Mean": "12345.6",
        " Label": "BENIGN",
    }

    SAMPLE_DDOS = {
        " Source IP": "203.0.113.44",
        " Destination IP": "10.0.2.5",
        " Source Port": "49200",
        " Destination Port": "80",
        " Flow Duration": "100",
        " Total Fwd Packets": "10000",
        " Total Backward Packets": "2",
        "Flow Bytes/s": "999999.9",
        "Flow Packets/s": "50000.0",
        " Fwd Packet Length Mean": "60.0",
        " Bwd Packet Length Mean": "0.0",
        " Flow IAT Mean": "0.5",
        " Label": "DDoS",
    }

    def test_benign_flow(self):
        event = normalize_cicids(self.SAMPLE_BENIGN)

        assert isinstance(event, NormalizedEvent)
        assert event.event.action == "network_flow"
        assert event.event.outcome == "success"
        assert "network" in event.event.category
        assert event.source.ip == "10.0.1.10"
        assert event.destination.ip == "10.0.2.5"
        assert event.destination.port == 80
        assert event.log.source_type == "cicids"

    def test_ddos_flow(self):
        event = normalize_cicids(self.SAMPLE_DDOS)

        assert event.event.action == "ddos"
        assert event.event.outcome == "failure"
        assert "intrusion_detection" in event.event.category

    def test_portscan_label(self):
        row = {**self.SAMPLE_BENIGN, " Label": "PortScan"}
        event = normalize_cicids(row)
        assert event.event.action == "port_scan"

    def test_missing_fields_no_raise(self):
        """Row with minimal fields should not raise."""
        row = {" Label": "BENIGN"}
        event = normalize_cicids(row)
        assert isinstance(event, NormalizedEvent)

    def test_inf_values_handled(self):
        """CICIDS2017 has Infinity values in Flow Bytes/s — must not crash."""
        row = {**self.SAMPLE_BENIGN, "Flow Bytes/s": "Infinity"}
        event = normalize_cicids(row)
        assert isinstance(event, NormalizedEvent)

    def test_nan_values_handled(self):
        row = {**self.SAMPLE_BENIGN, "Flow Bytes/s": "NaN"}
        event = normalize_cicids(row)
        assert isinstance(event, NormalizedEvent)

    def test_special_characters_no_raise(self):
        row = {**self.SAMPLE_BENIGN, " Source IP": "'; DROP TABLE events;--"}
        event = normalize_cicids(row)
        assert isinstance(event, NormalizedEvent)

    def test_unknown_label(self):
        """Unknown labels should be handled gracefully."""
        row = {**self.SAMPLE_BENIGN, " Label": "SomeNewAttackType"}
        event = normalize_cicids(row)
        assert event.event.action == "somenewattacktype"


# ═══════════════════════════════════════════════════════════════════════════════
# Cross-Normalizer Contract Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestNormalizerContract:
    """Verify all normalizers produce valid NormalizedEvent objects with required fields."""

    @pytest.fixture(
        params=[
            ("syslog", "Aug 10 09:14:22 prod-db-03 sshd[1234]: Failed password for root from 203.0.113.44 port 49312 ssh2"),
            ("auth_log", "Aug 10 09:14:22 prod-db-03 sshd[1234]: Failed password for root from 203.0.113.44 port 49312 ssh2"),
            ("cloudtrail", json.dumps({"eventName": "ConsoleLogin", "eventTime": "2026-08-10T09:00:00Z", "sourceIPAddress": "1.2.3.4", "userIdentity": {"userName": "test"}})),
        ]
    )
    def normalized_event(self, request):
        source_type, raw = request.param
        normalizer = get_normalizer(source_type)
        return normalizer(raw)

    def test_has_timestamp(self, normalized_event):
        assert isinstance(normalized_event.timestamp, datetime)

    def test_has_event_action(self, normalized_event):
        assert normalized_event.event.action != ""

    def test_has_log_source_type(self, normalized_event):
        assert normalized_event.log.source_type in ["syslog", "cloudtrail", "auth_log", "cicids"]

    def test_has_raw_log(self, normalized_event):
        assert normalized_event.log.raw != ""

    def test_has_chain_hash(self, normalized_event):
        assert normalized_event.related.hash is not None
        assert normalized_event.related.hash.startswith("sha256:")

    def test_raw_capped_at_1000(self):
        """Raw log content must be capped at 1000 characters."""
        long_line = "A" * 2000
        event = normalize_syslog(long_line)
        assert len(event.log.raw) <= 1000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
