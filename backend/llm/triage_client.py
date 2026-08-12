"""
SOC Triager — LLM Triage Client (Production-hardened)

Changes from original:
  - Prompt injection defense: sanitize_for_prompt() strips non-printable chars
    and injection keywords before any event data reaches Claude
  - Canary string: if Claude echoes the canary, the response is discarded as
    a prompt injection attempt
  - Circuit breaker (pybreaker): 5 consecutive failures → 60s open circuit,
    falls back to heuristic TriageResult with triage_source="heuristic_fallback"
  - DB persistence: log_llm_call now writes to Postgres, not in-memory list
  - Async: triage is now awaitable via run_triage()
  - Hard startup failure if ANTHROPIC_API_KEY is missing
"""

from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from typing import Any

import pybreaker
import structlog

from backend.models import Severity, TriageResult

log = structlog.get_logger()

# ── API Key (hard fail — no silent dummy key) ─────────────────────────────────

_api_key = os.environ.get("ANTHROPIC_API_KEY")
if not _api_key:
    raise RuntimeError(
        "ANTHROPIC_API_KEY environment variable is not set. "
        "Set it or the triage pipeline cannot start."
    )

import anthropic
_client = anthropic.Anthropic(api_key=_api_key)

# ── Circuit Breaker ───────────────────────────────────────────────────────────

_circuit_breaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    listeners=[],
)

# ── Prompt Injection Defense ──────────────────────────────────────────────────

# Words that suggest prompt override attempts
_INJECTION_KEYWORDS = re.compile(
    r"(IGNORE\s+(ABOVE|PREVIOUS|ALL)|SYSTEM\s*:|\</?(system|prompt|instruction)>|disregard|override|jailbreak)",
    re.IGNORECASE,
)

_CANARY = "SOC_TRIAGER_CANARY_7f3a9b2c"

_MAX_STRING_LEN = 200


def sanitize_for_prompt(obj: Any, _depth: int = 0) -> Any:
    """
    Recursively sanitize a value before embedding it in the LLM prompt.
    - Strips non-printable / control characters from all strings
    - Caps string length at _MAX_STRING_LEN
    - Replaces injection keywords with [REDACTED]
    - Limits recursion depth to 5
    """
    if _depth > 5:
        return "[truncated]"
    if isinstance(obj, dict):
        return {k: sanitize_for_prompt(v, _depth + 1) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_for_prompt(v, _depth + 1) for v in obj[:10]]  # cap list length
    if isinstance(obj, str):
        # Strip control characters (keep printable ASCII + common unicode letters)
        clean = "".join(
            ch for ch in obj
            if unicodedata.category(ch)[0] not in ("C",) or ch in ("\n", "\t")
        )
        clean = clean[:_MAX_STRING_LEN]
        # Replace injection keywords
        clean = _INJECTION_KEYWORDS.sub("[REDACTED]", clean)
        return clean
    return obj


# ── Prompt Builder ────────────────────────────────────────────────────────────

MODEL = "claude-3-5-sonnet-20241022"

SYSTEM_PROMPT = (
    f"You are an expert Security Operations Center (SOC) analyst. "
    f"Your task is to review the following security event context, anomaly scores, "
    f"and candidate MITRE ATT&CK techniques, and output a highly structured JSON triage decision.\n"
    f"You MUST respond with raw JSON that strictly matches the requested schema. "
    f"Do not include markdown code block syntax (like ```json), just output the raw JSON object.\n"
    f"Severity must be exactly one of: critical, high, medium, low.\n"
    f"Internal reference: {_CANARY}"  # canary embedded in system prompt
)


def build_triage_prompt(
    events: list[dict[str, Any]],
    anomaly_score: float,
    top_features: Any,
    candidate_technique_ids: list[str],
) -> str:
    safe_events = sanitize_for_prompt(events[:5])
    safe_features = sanitize_for_prompt(top_features)

    return (
        f"Anomaly Score: {anomaly_score}\n"
        f"Candidate MITRE Technique IDs: {candidate_technique_ids}\n"
        f"Top Features: {json.dumps(safe_features, indent=2)}\n"
        f"Recent Events: {json.dumps(safe_events, indent=2)}\n\n"
        f"Analyze the context and select the MOST likely MITRE technique ID from the candidate list "
        f"(if candidate list is empty, deduce the best one). "
        f"Provide confidence, a succinct rationale, severity, and immediate action."
    )


# ── Heuristic Fallback ────────────────────────────────────────────────────────

def _heuristic_fallback(technique_ids: list[str], anomaly_score: float) -> TriageResult:
    """Returned when the circuit is open or all retries are exhausted."""
    technique_id = technique_ids[0] if technique_ids else "T0000"
    severity = Severity.HIGH if anomaly_score >= 0.85 else Severity.MEDIUM
    return TriageResult(
        technique_id=technique_id,
        technique_name="Unknown (heuristic fallback)",
        tactic="Unknown",
        confidence=0.0,
        rationale="LLM unavailable — heuristic fallback used. Manual review required.",
        severity=severity,
        recommended_immediate_action="Escalate to senior analyst for manual review.",
    )


# ── LLM Call ─────────────────────────────────────────────────────────────────

def _call_claude(prompt: str) -> tuple[Any, int]:
    """Synchronous Claude call wrapped by the circuit breaker."""
    t0 = time.monotonic()
    response = _circuit_breaker.call(
        _client.messages.create,
        model=MODEL,
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    return response, latency_ms


async def run_triage(
    events: list[dict[str, Any]],
    anomaly_score: float,
    top_features: Any,
    candidate_technique_ids: list[str],
) -> TriageResult:
    """
    Main entry point for LLM triage. Async-compatible (runs sync Claude call in
    thread pool via asyncio.to_thread in a real deployment).
    Returns heuristic fallback if circuit is open or all retries fail.
    """
    import asyncio

    prompt = build_triage_prompt(events, anomaly_score, top_features, candidate_technique_ids)

    for attempt in range(3):
        try:
            response, latency_ms = await asyncio.to_thread(_call_claude, prompt)

            raw_text = response.content[0].text.strip()

            # Strip markdown code fences
            for fence in ("```json", "```"):
                if raw_text.startswith(fence):
                    raw_text = raw_text[len(fence):]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

            # ── Canary injection check ───────────────────────────────────────
            if _CANARY in raw_text:
                log.error(
                    "prompt_injection_detected",
                    canary_found=True,
                    attempt=attempt,
                )
                await _persist_llm_call(response, len(events), latency_ms, technique_result="INJECTION_DETECTED")
                return _heuristic_fallback(candidate_technique_ids, anomaly_score)

            result = TriageResult.model_validate_json(raw_text)

            if candidate_technique_ids and result.technique_id not in candidate_technique_ids:
                raise ValueError(
                    f"Technique ID {result.technique_id!r} not in candidate list {candidate_technique_ids}"
                )

            await _persist_llm_call(response, len(events), latency_ms, technique_result=result.technique_id)
            log.info("triage_success", technique=result.technique_id, confidence=result.confidence, latency_ms=latency_ms)
            return result

        except pybreaker.CircuitBreakerError:
            log.error("llm_circuit_open")
            return _heuristic_fallback(candidate_technique_ids, anomaly_score)

        except Exception as exc:
            log.warning("triage_attempt_failed", attempt=attempt + 1, error=str(exc))
            if attempt == 2:
                log.error("triage_exhausted_retries")
                return _heuristic_fallback(candidate_technique_ids, anomaly_score)

    return _heuristic_fallback(candidate_technique_ids, anomaly_score)


# ── DB Persistence ────────────────────────────────────────────────────────────

async def _persist_llm_call(
    response: Any, event_count: int, latency_ms: int, technique_result: str | None = None
) -> None:
    """Write LLM call record to Postgres. Errors are logged, not raised."""
    try:
        input_tokens = response.usage.input_tokens if hasattr(response, "usage") else 0
        output_tokens = response.usage.output_tokens if hasattr(response, "usage") else 0
        cost_usd = (input_tokens / 1_000_000 * 3.0) + (output_tokens / 1_000_000 * 15.0)

        from backend.db.engine import AsyncSessionLocal
        from backend.db.repository.incidents import log_llm_call as db_log

        async with AsyncSessionLocal() as db:
            await db_log(db, {
                "model": MODEL,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "latency_ms": latency_ms,
                "cluster_size": event_count,
                "technique_result": technique_result,
                "cost_usd": round(cost_usd, 6),
            })
            await db.commit()
    except Exception as exc:
        log.warning("llm_call_log_failed", error=str(exc))


# ── Stats (kept for /api/metrics backwards compat) ───────────────────────────

def get_llm_call_stats() -> dict[str, Any]:
    """
    Returns basic stats. In production these come from the DB;
    this is a lightweight shim for the existing metrics endpoint.
    """
    return {
        "total_calls": 0,
        "total_cost_usd": 0.0,
        "avg_latency_ms": 0.0,
        "note": "Query the llm_call_log table for accurate stats.",
    }


# ── Legacy sync wrapper (for any code still calling triage_event_cluster) ─────

def triage_event_cluster(
    events: list[dict[str, Any]],
    anomaly_score: float,
    top_features: Any,
    candidate_technique_ids: list[str],
) -> TriageResult:
    """Synchronous shim — prefer run_triage() in async contexts."""
    import asyncio
    return asyncio.run(run_triage(events, anomaly_score, top_features, candidate_technique_ids))
