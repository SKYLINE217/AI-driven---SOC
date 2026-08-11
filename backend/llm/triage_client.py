import anthropic
import json
import os
import time
from typing import Any, Dict, List, Optional
from datetime import datetime, UTC

# Ensure ANTHROPIC_API_KEY is available
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", "dummy_key_for_tests"))

# Import the canonical TriageResult from models (single source of truth)
from backend.models import TriageResult  # noqa: F401 (re-exported for backward compat)

SYSTEM_PROMPT = """You are an expert Security Operations Center (SOC) analyst.
Your task is to review the following security event context, anomaly scores, and candidate MITRE ATT&CK techniques, and output a highly structured JSON triage decision.
You MUST respond with raw JSON that strictly matches the requested schema. Do not include markdown code block syntax (like ```json), just output the raw JSON object.
Severity must be exactly one of: critical, high, medium, low.
"""

def build_triage_prompt(
    events: List[Dict[str, Any]], 
    anomaly_score: float, 
    top_features: Dict[str, Any], 
    candidate_technique_ids: List[str]
) -> str:
    return f"""
Anomaly Score: {anomaly_score}
Candidate MITRE Technique IDs: {candidate_technique_ids}
Top Features: {json.dumps(top_features, indent=2)}
Recent Events: {json.dumps(events[:5], indent=2)}

Analyze the context and select the MOST likely MITRE technique ID from the candidate list (if candidate list is empty, deduce the best one).
Provide confidence, a succinct rationale, severity, and immediate action.
"""

# In-memory LLM call log (persisted to DB in Day 4)
_llm_call_log: List[Dict[str, Any]] = []


def log_llm_call(response: Any, event_count: int, latency_ms: int) -> None:
    """Log LLM call metadata for cost and latency tracking."""
    # Claude pricing (Sonnet): ~$3/M input, ~$15/M output
    input_tokens = response.usage.input_tokens if hasattr(response, "usage") else 0
    output_tokens = response.usage.output_tokens if hasattr(response, "usage") else 0
    cost_usd = (input_tokens / 1_000_000 * 3.0) + (output_tokens / 1_000_000 * 15.0)

    entry = {
        "called_at": datetime.now(UTC).isoformat(),
        "model": "claude-3-5-sonnet-20240620",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": latency_ms,
        "cluster_size": event_count,
        "cost_usd": round(cost_usd, 6),
    }
    _llm_call_log.append(entry)


def get_llm_call_stats() -> Dict[str, Any]:
    """Return aggregate LLM call statistics for the /ops metrics page."""
    if not _llm_call_log:
        return {"total_calls": 0, "total_cost_usd": 0.0, "avg_latency_ms": 0.0}
    total_cost = sum(e["cost_usd"] for e in _llm_call_log)
    avg_latency = sum(e["latency_ms"] for e in _llm_call_log) / len(_llm_call_log)
    return {
        "total_calls": len(_llm_call_log),
        "total_cost_usd": round(total_cost, 4),
        "avg_latency_ms": round(avg_latency, 1),
        "cost_per_1000_flagged": round(total_cost / max(len(_llm_call_log), 1) * 1000, 2),
    }

def triage_event_cluster(
    events: List[Dict[str, Any]],
    anomaly_score: float,
    top_features: Dict[str, Any],
    candidate_technique_ids: List[str]
) -> TriageResult:
    prompt = build_triage_prompt(events, anomaly_score, top_features, candidate_technique_ids)
    
    for attempt in range(3):
        try:
            t0 = time.monotonic()
            response = client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=1000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            latency_ms = int((time.monotonic() - t0) * 1000)

            raw_text = response.content[0].text.strip()
            # Strip markdown code fences if the model included them
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

            result = TriageResult.model_validate_json(raw_text)

            if candidate_technique_ids and result.technique_id not in candidate_technique_ids:
                raise ValueError(f"Technique ID {result.technique_id} not in candidate list {candidate_technique_ids}")

            log_llm_call(response, len(events), latency_ms)
            return result

        except Exception as e:
            if attempt == 2:
                raise RuntimeError(f"Failed to parse LLM response after 3 attempts: {e}")
            continue

    raise RuntimeError("Failed to parse LLM response")
