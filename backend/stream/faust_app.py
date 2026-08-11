"""
SOC Triager — Faust Stream Processing Skeleton
Consumes raw log topics, normalizes to ECS, computes features, scores anomalies.

Engineer B owns the Faust app structure; Engineer A provides the normalizer functions.

Usage:
    faust -A backend.stream.faust_app worker -l info
"""

import faust
import json
import os
from datetime import datetime, timezone

# Faust app configuration
KAFKA_BROKER = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka://localhost:19092')

app = faust.App(
    'soc-triager',
    broker=KAFKA_BROKER,
    store='memory://',
    topic_partitions=4,
)

# ── Topics ──────────────────────────────────────────────────────────────────

raw_syslog = app.topic('raw.syslog', value_type=bytes)
raw_cloudtrail = app.topic('raw.cloudtrail', value_type=bytes)
raw_auth = app.topic('raw.auth', value_type=bytes)
raw_cicids = app.topic('raw.cicids', value_type=bytes)
normalized_events = app.topic('normalized.events', value_type=bytes)
alerts_raw = app.topic('alerts.raw', value_type=bytes)
incidents_updates = app.topic('incidents.updates', value_type=bytes)


# ── Normalizer Registry ────────────────────────────────────────────────────
# Engineer A provides normalizer functions; this is the dispatch mechanism.

def get_normalizer(source_type: str):
    """
    Get the appropriate normalizer function for a given source type.
    Falls back to a passthrough normalizer if the specific one isn't available.
    """
    try:
        from backend.ingestion.normalizers import get_normalizer as _get
        return _get(source_type)
    except (ImportError, KeyError):
        # Fallback: wrap raw line in minimal ECS structure
        def passthrough_normalizer(raw_line: str) -> dict:
            return {
                '@timestamp': datetime.now(timezone.utc).isoformat(),
                'event': {
                    'kind': 'event',
                    'category': ['process'],
                    'action': 'unknown',
                    'outcome': 'unknown',
                },
                'log': {
                    'source_type': source_type,
                    'raw': raw_line[:1000],
                },
            }
        return passthrough_normalizer


# ── Agent: Normalize Syslog ────────────────────────────────────────────────

@app.agent(raw_syslog)
async def process_syslog(stream):
    normalizer = get_normalizer('syslog')
    async for raw_event in stream:
        try:
            raw_line = raw_event.decode('utf-8') if isinstance(raw_event, bytes) else raw_event
            ecs = normalizer(raw_line)
            ecs_json = json.dumps(ecs if isinstance(ecs, dict) else ecs.model_dump())
            await normalized_events.send(value=ecs_json.encode('utf-8'))
        except Exception as e:
            print(f"[Faust] Syslog normalization error: {e}")


# ── Agent: Normalize CloudTrail ────────────────────────────────────────────

@app.agent(raw_cloudtrail)
async def process_cloudtrail(stream):
    normalizer = get_normalizer('cloudtrail')
    async for raw_event in stream:
        try:
            raw_line = raw_event.decode('utf-8') if isinstance(raw_event, bytes) else raw_event
            ecs = normalizer(raw_line)
            ecs_json = json.dumps(ecs if isinstance(ecs, dict) else ecs.model_dump())
            await normalized_events.send(value=ecs_json.encode('utf-8'))
        except Exception as e:
            print(f"[Faust] CloudTrail normalization error: {e}")


# ── Agent: Normalize auth.log ──────────────────────────────────────────────

@app.agent(raw_auth)
async def process_auth(stream):
    normalizer = get_normalizer('auth')
    async for raw_event in stream:
        try:
            raw_line = raw_event.decode('utf-8') if isinstance(raw_event, bytes) else raw_event
            ecs = normalizer(raw_line)
            ecs_json = json.dumps(ecs if isinstance(ecs, dict) else ecs.model_dump())
            await normalized_events.send(value=ecs_json.encode('utf-8'))
        except Exception as e:
            print(f"[Faust] Auth normalization error: {e}")


# ── Agent: Normalize CICIDS2017 ────────────────────────────────────────────

@app.agent(raw_cicids)
async def process_cicids(stream):
    normalizer = get_normalizer('cicids')
    async for raw_event in stream:
        try:
            raw_line = raw_event.decode('utf-8') if isinstance(raw_event, bytes) else raw_event
            ecs = normalizer(raw_line)
            ecs_json = json.dumps(ecs if isinstance(ecs, dict) else ecs.model_dump())
            await normalized_events.send(value=ecs_json.encode('utf-8'))
        except Exception as e:
            print(f"[Faust] CICIDS normalization error: {e}")


import httpx
import uuid

# ── Agent: Score and Alert (Day 2 — wired to scoring API) ──────────────────

# Create httpx client for the scoring API
http_client = httpx.AsyncClient(base_url="http://localhost:8001")

@app.agent(normalized_events)
async def score_and_alert(stream):
    """
    Day 2: Wired up to Scoring API.
    1. Extract basic entity key (source IP or user)
    2. Compute windowed features (Mocked for now)
    3. Call Scoring API (localhost:8001/score)
    4. If score > threshold, publish to alerts.raw
    """
    async for event_bytes in stream:
        try:
            event = json.loads(event_bytes)
            source_type = event.get('log', {}).get('source_type', 'unknown')
            action = event.get('event', {}).get('action', 'unknown')
            source_ip = event.get('source', {}).get('ip')
            user_name = event.get('user', {}).get('name')
            
            # Determine entity key
            entity_key = user_name if user_name else (source_ip if source_ip else "unknown_entity")
            if entity_key == "unknown_entity":
                continue

            # In a real app, query Redis for the 1m/5m/1h feature aggregations here
            # For this sprint, we'll generate mock features based on the event type
            mock_features = {
                "entity_key": entity_key,
                "event_count_1m": 1.0,
                "event_count_5m": 5.0,
                "event_count_1h": 20.0,
                "failed_auth_ratio": 0.8 if action == "failed_login" else 0.1,
                "distinct_dest_ports": 2.0,
                "dest_ip_fanout": 1.0,
                "bytes_transferred": 1024.0,
                "tod_zscore": 0.5,
                "geo_velocity_kmh": 0.0
            }

            # If it's a brute force log, pump up the features
            if action == "failed_login":
                mock_features["event_count_1m"] = 150.0

            # Call Scoring API
            response = await http_client.post("/score", json={"features": mock_features})
            
            if response.status_code == 200:
                score_result = response.json()
                
                # If anomalous, construct alert and push to alerts.raw
                if score_result.get("is_anomaly", False):
                    alert_payload = {
                        "alert_id": str(uuid.uuid4()),
                        "timestamp": event.get("timestamp", datetime.now(timezone.utc).isoformat()),
                        "source_ip": source_ip,
                        "destination_host": event.get("destination", {}).get("host"),
                        "user_name": user_name,
                        "technique_id": "T1110" if action == "failed_login" else "T1059", # Mock mapping
                        "tactic": "Credential Access" if action == "failed_login" else "Execution",
                        "anomaly_score": score_result.get("score", 0.0),
                        "top_features": score_result.get("top_features", []),
                        "severity": "high" if score_result.get("score", 0.0) > 0.85 else "medium",
                        "raw_event": event
                    }
                    
                    await alerts_raw.send(value=json.dumps(alert_payload).encode('utf-8'))
                    print(f"[Faust] Generated Alert for {entity_key}: Score {score_result.get('score')}")
                    
        except Exception as e:
            print(f"[Faust] Scoring error: {e}")


# ── Health check endpoint ──────────────────────────────────────────────────

@app.page('/health')
async def health(web, request):
    return web.json({'status': 'ok', 'service': 'faust-worker'})


if __name__ == '__main__':
    app.main()
