"""
CICIDS2017 Normalizer — Maps CICIDS2017 CSV rows into ECS NormalizedEvent.

CICIDS2017 is a labeled network intrusion detection dataset with columns like:
    Destination Port, Flow Duration, Total Fwd Packets, Total Backward Packets,
    Flow Bytes/s, Flow Packets/s, Flow IAT Mean, ... , Label

We map these network flow features to ECS-style events and preserve the raw
CSV data for feature engineering downstream.
"""

import math
from datetime import UTC, datetime
from typing import Any

from ...models import (
    DestinationInfo,
    EventInfo,
    HostInfo,
    LogInfo,
    NormalizedEvent,
    SourceInfo,
    UserInfo,
)

# CICIDS2017 label to ECS action mapping
LABEL_ACTION_MAP: dict[str, dict[str, Any]] = {
    "BENIGN": {
        "action": "network_flow",
        "outcome": "success",
        "category": ["network"],
    },
    "FTP-Patator": {
        "action": "ftp_brute_force",
        "outcome": "failure",
        "category": ["network", "intrusion_detection"],
    },
    "SSH-Patator": {
        "action": "ssh_brute_force",
        "outcome": "failure",
        "category": ["network", "intrusion_detection"],
    },
    "DoS slowloris": {
        "action": "dos_slowloris",
        "outcome": "failure",
        "category": ["network", "intrusion_detection"],
    },
    "DoS Slowhttptest": {
        "action": "dos_slowhttp",
        "outcome": "failure",
        "category": ["network", "intrusion_detection"],
    },
    "DoS Hulk": {
        "action": "dos_hulk",
        "outcome": "failure",
        "category": ["network", "intrusion_detection"],
    },
    "DoS GoldenEye": {
        "action": "dos_goldeneye",
        "outcome": "failure",
        "category": ["network", "intrusion_detection"],
    },
    "Heartbleed": {
        "action": "heartbleed_exploit",
        "outcome": "failure",
        "category": ["network", "intrusion_detection"],
    },
    "Web Attack \u2013 Brute Force": {
        "action": "web_brute_force",
        "outcome": "failure",
        "category": ["network", "web", "intrusion_detection"],
    },
    "Web Attack \u2013 XSS": {
        "action": "web_xss",
        "outcome": "failure",
        "category": ["network", "web", "intrusion_detection"],
    },
    "Web Attack \u2013 Sql Injection": {
        "action": "web_sqli",
        "outcome": "failure",
        "category": ["network", "web", "intrusion_detection"],
    },
    "Infiltration": {
        "action": "infiltration",
        "outcome": "failure",
        "category": ["network", "intrusion_detection"],
    },
    "Bot": {
        "action": "botnet_activity",
        "outcome": "failure",
        "category": ["network", "intrusion_detection"],
    },
    "PortScan": {
        "action": "port_scan",
        "outcome": "failure",
        "category": ["network", "intrusion_detection"],
    },
    "DDoS": {
        "action": "ddos",
        "outcome": "failure",
        "category": ["network", "intrusion_detection"],
    },
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert a value to float, handling inf/nan/empty."""
    try:
        v = float(value)
        if math.isinf(v) or math.isnan(v):
            return default
        return v
    except (ValueError, TypeError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    """Safely convert a value to int."""
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def normalize_cicids(row: dict[str, Any]) -> NormalizedEvent:
    """
    Convert a CICIDS2017 CSV row (as a dict from csv.DictReader or pandas)
    into an ECS NormalizedEvent.

    The row dict keys are the CICIDS2017 column names (which have leading spaces
    in some files — we strip them).
    """
    # Normalize column names — CICIDS2017 CSVs have inconsistent leading spaces
    cleaned: dict[str, Any] = {}
    for k, v in row.items():
        cleaned[k.strip()] = v

    # Get the label
    label = str(cleaned.get("Label", "BENIGN")).strip()
    mapping = LABEL_ACTION_MAP.get(label, {
        "action": label.lower().replace(" ", "_"),
        "outcome": "unknown",
        "category": ["network"],
    })

    # Parse timestamp — CICIDS2017 uses various date formats
    timestamp = datetime.now(UTC)
    ts_str = cleaned.get("Timestamp", cleaned.get("Flow ID", ""))
    if ts_str:
        for fmt in [
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%m/%d/%Y %H:%M",
        ]:
            try:
                timestamp = datetime.strptime(str(ts_str).strip(), fmt)
                break
            except ValueError:
                continue

    # Extract network flow fields
    src_ip = str(cleaned.get("Source IP", cleaned.get("Src IP", ""))).strip() or None
    dst_ip = str(cleaned.get("Destination IP", cleaned.get("Dst IP", ""))).strip() or None
    src_port = _safe_int(cleaned.get("Source Port", cleaned.get("Src Port")))
    dst_port = _safe_int(cleaned.get("Destination Port", cleaned.get("Dst Port")))

    # Build raw data summary for forensics
    flow_summary = {
        "label": label,
        "flow_duration": _safe_float(cleaned.get("Flow Duration")),
        "total_fwd_packets": _safe_int(cleaned.get("Total Fwd Packets")),
        "total_bwd_packets": _safe_int(cleaned.get("Total Backward Packets", cleaned.get("Total Bwd Packets"))),
        "flow_bytes_per_s": _safe_float(cleaned.get("Flow Bytes/s")),
        "flow_packets_per_s": _safe_float(cleaned.get("Flow Packets/s")),
        "fwd_packet_length_mean": _safe_float(cleaned.get("Fwd Packet Length Mean")),
        "bwd_packet_length_mean": _safe_float(cleaned.get("Bwd Packet Length Mean")),
        "flow_iat_mean": _safe_float(cleaned.get("Flow IAT Mean")),
    }

    import json
    raw_str = json.dumps(flow_summary)

    event = NormalizedEvent(
        timestamp=timestamp,
        event=EventInfo(
            kind="event",
            category=mapping["category"],
            action=mapping["action"],
            outcome=mapping["outcome"],
        ),
        source=SourceInfo(
            ip=src_ip,
            port=src_port if src_port else None,
        ),
        destination=DestinationInfo(
            ip=dst_ip,
            host=dst_ip,
            port=dst_port if dst_port else None,
        ),
        user=UserInfo(),  # CICIDS2017 doesn't have user-level info
        host=HostInfo(
            name=dst_ip or "unknown",
        ),
        log=LogInfo(
            source_type="cicids",
            raw=raw_str,
        ),
    )

    event.related.hash = event.compute_chain_hash()
    return event

