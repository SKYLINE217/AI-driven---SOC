"""Metrics router"""
from fastapi import APIRouter, Depends
from backend.api.deps import get_current_claims

router = APIRouter()

@router.get("")
async def get_metrics(_claims: dict = Depends(get_current_claims)):
    return {
        "event_throughput_per_sec": 1240,
        "alert_volume_24h": 347,
        "anomaly_score_p95": 0.89,
        "llm_cost_per_1000_events_usd": 0.42,
        "pipeline_latency_p50_ms": 145,
        "pipeline_latency_p95_ms": 890,
        "active_incidents": 12,
        "closed_incidents_24h": 5,
    }
