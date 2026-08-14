from ..models import TriageResult, Severity
from typing import List, Dict, Any


SEVERITY_BANDS = [
    (0.85, Severity.CRITICAL),
    (0.70, Severity.HIGH),
    (0.50, Severity.MEDIUM),
    (0.00, Severity.LOW),
]

TACTIC_ACTIONS = {
    "Credential Access":    "Block source IP at perimeter firewall and reset affected credentials.",
    "Discovery":            "Rate-limit or null-route scanning source; review exposed service inventory.",
    "Lateral Movement":     "Isolate pivot host from internal network segment; review shared credentials.",
    "Privilege Escalation": "Suspend affected account; audit sudo/setuid changes on host.",
    "Exfiltration":         "Block egress to destination IP/domain; capture packet trace for forensics.",
    "Impact":               "Activate DDoS mitigation (null-route or scrubbing service); notify upstream.",
    "Initial Access":       "Force re-authentication for affected accounts; review access logs.",
    "Defense Evasion":      "Collect memory image of affected process; quarantine host.",
    "Execution":            "Kill suspicious process tree; capture command history and file hashes.",
}


def deterministic_triage(
    events: List[Dict[str, Any]],
    anomaly_score: float,
    top_features: List[Dict[str, Any]],
    candidate_technique_ids: List[str],
    technique_name: str,
    tactic: str,
) -> TriageResult:
    severity = Severity.LOW
    for threshold, label in SEVERITY_BANDS:
        if anomaly_score >= threshold:
            severity = label
            break

    confidence = round(min(anomaly_score * 1.1, 1.0), 3)
    technique_id = candidate_technique_ids[0] if candidate_technique_ids else "T0000"

    feat_summary = ", ".join(
        f"{f['name']}={f.get('value', '?')}" for f in top_features[:3]
    )
    entity = events[0].get("source", {}).get("ip", "unknown") if events else "unknown"
    rationale = (
        f"Anomaly score {anomaly_score:.3f} triggered on entity {entity}. "
        f"Top contributing features: {feat_summary}. "
        f"Heuristic rules matched technique {technique_id} ({tactic})."
    )[:500]

    action = TACTIC_ACTIONS.get(tactic, "Investigate host and isolate if confirmed malicious.")

    return TriageResult(
        technique_id=technique_id,
        technique_name=technique_name,
        tactic=tactic,
        confidence=confidence,
        rationale=rationale,
        severity=severity,
        recommended_immediate_action=action[:300],
    )

