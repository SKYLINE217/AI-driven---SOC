import os
import yaml

# Graceful import: mitreattack is optional. If not installed or STIX file missing,
# the rule engine still works and get_technique() returns a best-effort fallback.
try:
    from mitreattack.stix20 import MitreAttackData
    _HAS_MITREATTK = True
except Exception:
    MitreAttackData = None
    _HAS_MITREATTK = False

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MITRE_DATA_PATH = os.path.join(BASE_DIR, "data", "mitre", "enterprise-attack-v15.1.json")
RULES_PATH = os.path.join(os.path.dirname(__file__), "rules.yaml")

_attack_data = None

def get_attack_data():
    global _attack_data
    if _attack_data is None and _HAS_MITREATTK and os.path.exists(MITRE_DATA_PATH):
        _attack_data = MitreAttackData(MITRE_DATA_PATH)
    return _attack_data


_TECHNIQUE_FALLBACK = {
    "T1110.001": ("Password Guessing", "credential-access", "Brute force attacks guessing passwords against SSH/other services."),
    "T1110":     ("Brute Force", "credential-access", "Multiple failed authentication attempts indicative of brute forcing."),
    "T1078":     ("Valid Accounts", "initial-access", "Use of legitimate credentials - impossible travel or stolen creds."),
    "T1041":     ("Exfiltration Over C2 Channel", "exfiltration", "Large outbound transfer to external destination."),
    "T1021":     ("Remote Services", "lateral-movement", "Lateral movement via remote access services (SMB/RDP/SSH)."),
    "T1068":     ("Exploitation for Privilege Escalation", "privilege-escalation", "Privilege escalation via sudo/setuid or kernel exploits."),
    "T1498":     ("Network Denial of Service", "impact", "High-rate traffic characteristic of DDoS/Volumetric attack."),
    "T1059":     ("Command and Scripting Interpreter", "execution", "Suspicious command-line arguments or parent/child process tree."),
}


def get_technique(technique_id: str) -> dict:
    attack = get_attack_data()
    if attack is not None:
        try:
            technique = attack.get_object_by_attack_id(technique_id, "attack-pattern")
            if technique:
                obj = technique
                tactic = "Unknown"
                if hasattr(obj, "kill_chain_phases") and obj.kill_chain_phases:
                    tactic = obj.kill_chain_phases[0].phase_name
                return {
                    "id": technique_id,
                    "name": obj.name,
                    "tactic": tactic,
                    "description": getattr(obj, "description", "No description available."),
                }
        except Exception:
            pass

    name, tactic, desc = _TECHNIQUE_FALLBACK.get(
        technique_id,
        (technique_id, "Unknown", "Technique not found in local fallback table."),
    )
    return {"id": technique_id, "name": name, "tactic": tactic, "description": desc}


def map_techniques(events: list, top_features: list = None) -> dict:
    """
    Convenience wrapper used by the CLI ingest pipeline.
    Builds an event context from the highest-scoring event in the cluster,
    runs MitreRuleEngine, and returns {technique_ids, technique_name, tactic}.
    """
    try:
        engine = MitreRuleEngine()
        top = max(events, key=lambda e: e.get("anomaly_score", 0.0)) if events else {}
        top_feats = {f["name"]: f.get("value", 0.0) for f in (top_features or [])}

        src = top.get("source", {}) or {}
        dst = top.get("destination", {}) or {}
        evt = top.get("event", {}) or {}
        net = top.get("network", {}) or {}
        usr = top.get("user", {}) or {}

        def _internal(ip):
            return bool(ip) and ip.startswith(("10.", "172.16.", "172.17.", "172.18.", "172.19.",
                                                "172.2", "172.30.", "172.31.", "192.168.", "127."))

        ctx = {
            "event_type": evt.get("category", ""),
            "action": evt.get("action", "") or evt.get("outcome", ""),
            "dest_port": dst.get("port", 0) or 0,
            "event_count_1m": top_feats.get("event_count_1m", 0),
            "event_count_5m": top_feats.get("event_count_5m", 0),
            "distinct_dest_ports": top_feats.get("distinct_dest_ports", 0),
            "dest_ip_fanout": top_feats.get("dest_ip_fanout", 0),
            "bytes_transferred": top_feats.get("bytes_transferred", 0),
            "geo_velocity_kmh": top_feats.get("geo_velocity_kmh", 0),
            "source_is_internal": _internal(src.get("ip", "")),
            "dest_is_internal": _internal(dst.get("ip", "")),
            "dest_is_external": bool(dst.get("ip", "")) and not _internal(dst.get("ip", "")),
            "anomaly_score": top.get("anomaly_score", 0.0),
            "command_line": (top.get("process") or {}).get("command_line", ""),
            "user": usr.get("name", ""),
            "api_call": evt.get("action", ""),
            "parent_process": (top.get("process") or {}).get("parent", ""),
            "process": (top.get("process") or {}).get("name", ""),
        }
        candidates = engine.get_candidate_techniques(ctx)
    except Exception:
        candidates = []

    if not candidates:
        return {"technique_ids": ["T0000"], "technique_name": "Unknown Technique", "tactic": "Unknown"}

    primary = candidates[0]
    meta = get_technique(primary)
    return {
        "technique_ids": candidates,
        "technique_name": meta.get("name", primary),
        "tactic": meta.get("tactic", "Unknown"),
    }

class MitreRuleEngine:
    def __init__(self):
        with open(RULES_PATH, "r") as f:
            data = yaml.safe_load(f)
            self.rules = data.get("rules", [])

    def get_candidate_techniques(self, event_context: dict) -> list[str]:
        candidates = set()
        
        # Build safe local environment for rule evaluation
        # Add defaults to prevent NameError
        context = {
            "event_type": event_context.get("event_type", ""),
            "action": event_context.get("action", ""),
            "dest_port": event_context.get("dest_port", 0),
            "event_count_1m": event_context.get("event_count_1m", 0),
            "event_count_5m": event_context.get("event_count_5m", 0),
            "distinct_dest_ports": event_context.get("distinct_dest_ports", 0),
            "dest_ip_fanout": event_context.get("dest_ip_fanout", 0),
            "bytes_transferred": event_context.get("bytes_transferred", 0),
            "geo_velocity_kmh": event_context.get("geo_velocity_kmh", 0),
            "source_is_internal": event_context.get("source_is_internal", False),
            "dest_is_internal": event_context.get("dest_is_internal", False),
            "dest_is_external": event_context.get("dest_is_external", False),
            "anomaly_score": event_context.get("anomaly_score", 0.0),
            "command_line": event_context.get("command_line", ""),
            "user": event_context.get("user", ""),
            "api_call": event_context.get("api_call", ""),
            "parent_process": event_context.get("parent_process", ""),
            "process": event_context.get("process", "")
        }

        for rule in self.rules:
            try:
                # Basic eval is fine here since rules are internal config
                if eval(rule["condition"], {"__builtins__": {}}, context):
                    candidates.add(rule["technique_id"])
            except Exception as e:
                # Log error and continue if a rule fails to evaluate
                print(f"Error evaluating rule {rule['id']}: {e}")

        return list(candidates)
