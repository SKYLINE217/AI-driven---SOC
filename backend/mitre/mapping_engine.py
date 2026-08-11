import os
import yaml
from mitreattack.stix20 import MitreAttackData

MITRE_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "mitre", "enterprise-attack-v15.1.json")
RULES_PATH = os.path.join(os.path.dirname(__file__), "rules.yaml")

# Load MITRE data (lazy load to avoid slow startup in tests)
_attack_data = None

def get_attack_data() -> MitreAttackData:
    global _attack_data
    if _attack_data is None:
        _attack_data = MitreAttackData(MITRE_DATA_PATH)
    return _attack_data

def get_technique(technique_id: str) -> dict:
    attack = get_attack_data()
    # MITRE ATT&CK STIX API
    technique = attack.get_object_by_attack_id(technique_id, "attack-pattern")
    
    if not technique:
        return {
            "id": technique_id,
            "name": "Unknown Technique",
            "tactic": "Unknown",
            "description": "Technique not found in STIX data."
        }
    
    obj = technique
    tactic = "Unknown"
    if hasattr(obj, "kill_chain_phases") and obj.kill_chain_phases:
        tactic = obj.kill_chain_phases[0].phase_name

    return {
        "id": technique_id,
        "name": obj.name,
        "tactic": tactic,
        "description": getattr(obj, "description", "No description available.")
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
