"""
SOC Triager — Faust Stream Processing (Production-wired)
Consumes raw log topics, normalizes to ECS, scores anomalies,
runs MITRE mapping + LLM triage, and persists incidents to Postgres.

Usage:
    faust -A backend.stream.faust_app worker -l info
"""

import faust
import json
import os
import uuid
from datetime import datetime, timezone

import httpx
import structlog

log = structlog.get_logger()

# Faust app configuration
KAFKA_BROKER = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka://localhost:19092')
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
SCORING_API_URL = os.environ.get('SCORING_API_URL', 'http://localhost:8001')

app = faust.App(
    'soc-triager',
    broker=KAFKA_BROKER,
    store='memory://',
    topic_partitions=4,
)

# ── Topics ───────────────────────────────────────────────────────────────────

raw_syslog = app.topic('raw.syslog', value_type=bytes)
raw_cloudtrail = app.topic('raw.cloudtrail', value_type=bytes)
raw_auth = app.topic('raw.auth', value_type=bytes)
raw_cicids = app.topic('raw.cicids', value_type=bytes)
normalized_events = app.topic('normalized.events', value_type=bytes)
alerts_raw = app.topic('alerts.raw', value_type=bytes)
incidents_updates = app.topic('incidents.updates', value_type=bytes)
alerts_dead_letter = app.topic('alerts.dead_letter', value_type=bytes)

# ── Default features (used when Redis is unavailable) ─────────────────────────
DEFAULT_FEATURES = {
    "event_count_1m": 1.0,
    "event_count_5m": 5.0,
    "event_count_1h": 20.0,
    "failed_auth_ratio": 0.0,
    "distinct_dest_ports": 1.0,
    "dest_ip_fanout": 1.0,
    "bytes_transferred": 512.0,
    "tod_zscore": 0.0,
    "geo_velocity_kmh": 0.0,
}


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
            log.error("cicids_normalization_error", error=str(e))


import httpx
import uuid

# ── Agent: Score and Alert (Day 2 — wired to scoring API)
# ── Feature Fetcher (Redis with graceful degrade) ─────────────────────────────

async def get_features(entity_key: str) -> dict:
    """Fetch windowed features from Redis. Falls back to defaults if Redis is down."""
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(REDIS_URL, decode_responses=True)
        raw = await client.hgetall(f"soc:features:{entity_key}")
        await client.aclose()
        if raw:
            return {k: float(v) for k, v in raw.items()}
    except Exception as exc:
        log.warning("redis_features_unavailable", entity=entity_key, error=str(exc))
    return DEFAULT_FEATURES.copy()


# ── HTTP Client (Scoring API) ─────────────────────────────────────────────────

http_client = httpx.AsyncClient(base_url=SCORING_API_URL, timeout=5.0)


@app.agent(normalized_events)
async def score_and_alert(stream):
    """
    Scores each normalized event via the ML scoring API.
    If anomalous, constructs an alert and publishes to alerts.raw.
    """
    async for event_bytes in stream:
        try:
            event = json.loads(event_bytes)
            trace_id = event.get('trace_id', str(uuid.uuid4()))
            source_type = event.get('log', {}).get('source_type', 'unknown')
            action = event.get('event', {}).get('action', 'unknown')
            source_ip = event.get('source', {}).get('ip')
            user_name = event.get('user', {}).get('name')

            entity_key = user_name or source_ip or "unknown_entity"
            if entity_key == "unknown_entity":
                continue

            features = await get_features(entity_key)
            features["entity_key"] = entity_key

            response = await http_client.post("/score", json={"features": features})

            if response.status_code == 200:
                score_result = response.json()

                if score_result.get("is_anomaly", False):
                    alert_payload = {
                        "alert_id": str(uuid.uuid4()),
                        "trace_id": trace_id,
                        "timestamp": event.get("timestamp", datetime.now(timezone.utc).isoformat()),
                        "source_ip": source_ip,
                        "destination_host": event.get("destination", {}).get("host"),
                        "user_name": user_name,
                        "technique_id": "T1110" if action == "failed_login" else "T1059",
                        "tactic": "Credential Access" if action == "failed_login" else "Execution",
                        "anomaly_score": score_result.get("score", 0.0),
                        "top_features": score_result.get("top_features", []),
                        "severity": "high" if score_result.get("score", 0.0) > 0.85 else "medium",
                        "raw_event": event,
                    }

                    await alerts_raw.send(value=json.dumps(alert_payload).encode('utf-8'))
                    log.info("alert_generated", entity=entity_key, score=score_result.get('score'), trace_id=trace_id)

        except Exception as exc:
            log.error("scoring_error", error=str(exc))


# ── Agent: Triage and Create Incident ─────────────────────────────────────────

MAX_TRIAGE_RETRIES = 3

@app.agent(alerts_raw)
async def triage_and_create_incident(stream):
    """
    Full pipeline step 2:
    1. Run MITRE ATT&CK mapping on the alert
    2. Run LLM triage (with circuit breaker fallback)
    3. Persist incident + alert to Postgres
    4. Publish to Redis Stream for WebSocket delivery
    5. Publish to incidents.updates topic
    6. Dead-letter on exhausted retries
    """
    from backend.mitre.mapping_engine import MitreRuleEngine
    from backend.llm.triage_client import run_triage
    from backend.db.engine import AsyncSessionLocal
    from backend.db.repository import alerts as alert_repo
    from backend.db.repository import incidents as incident_repo

    rule_engine = MitreRuleEngine()

    async for alert_bytes in stream:
        retries = 0
        while retries <= MAX_TRIAGE_RETRIES:
            try:
                alert = json.loads(alert_bytes)
                trace_id = alert.get('trace_id', str(uuid.uuid4()))
                alert_id = alert.get('alert_id', str(uuid.uuid4()))

                # ── Step 1: MITRE mapping ─────────────────────────────────────
                raw_event = alert.get('raw_event', {})
                candidate_techniques = rule_engine.map(raw_event)
                technique_ids = [t.technique_id for t in candidate_techniques] if candidate_techniques else [alert.get('technique_id', 'T0000')]

                # ── Step 2: LLM triage ───────────────────────────────────────
                triage_result = await run_triage(
                    events=[raw_event],
                    anomaly_score=alert.get('anomaly_score', 0.0),
                    top_features=alert.get('top_features', []),
                    candidate_technique_ids=technique_ids,
                )

                technique_id = triage_result.technique_id if triage_result else alert.get('technique_id', 'T0000')
                technique_name = triage_result.technique_name if triage_result else 'Unknown'
                tactic = triage_result.tactic if triage_result else alert.get('tactic', 'Unknown')
                severity = triage_result.severity if triage_result else alert.get('severity', 'medium')
                confidence = triage_result.confidence if triage_result else 0.0
                rationale = triage_result.rationale if triage_result else 'Heuristic fallback'
                action = triage_result.recommended_immediate_action if triage_result else ''

                # ── Step 3: Persist to Postgres ──────────────────────────────
                async with AsyncSessionLocal() as db:
                    # Create alert row
                    await alert_repo.create_alert(db, {
                        "id": alert_id,
                        "severity": str(severity),
                        "timestamp": alert.get('timestamp', datetime.now(timezone.utc).isoformat()),
                        "source_ip": alert.get('source_ip'),
                        "destination_host": alert.get('destination_host'),
                        "user_name": alert.get('user_name'),
                        "technique_id": technique_id,
                        "tactic": tactic,
                        "anomaly_score": alert.get('anomaly_score', 0.0),
                        "top_features": alert.get('top_features'),
                        "status": "new",
                    })

                    # Create incident (idempotent on alert_id)
                    title = f"[{technique_id}] {technique_name} — {alert.get('source_ip', 'unknown')}"
                    incident = await incident_repo.create_incident(db, {
                        "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, alert_id)),  # deterministic from alert
                        "title": title,
                        "severity": str(severity),
                        "technique_id": technique_id,
                        "technique_name": technique_name,
                        "tactic": tactic,
                        "confidence": confidence,
                        "llm_rationale": rationale,
                        "recommended_action": action,
                    }, actor="faust-worker")

                    # Link alert to incident
                    await alert_repo.link_alert_to_incident(db, alert_id, incident["id"])
                    await db.commit()

                # ── Step 4: Redis Stream for WebSocket ───────────────────────
                try:
                    import redis.asyncio as aioredis
                    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
                    await redis_client.xadd(
                        "soc:ws:alerts",
                        {"data": json.dumps({"type": "new_alert", "payload": alert, "trace_id": trace_id})},
                        maxlen=1000,  # Cap stream length
                    )
                    await redis_client.aclose()
                except Exception as exc:
                    log.warning("redis_stream_publish_failed", error=str(exc), trace_id=trace_id)

                # ── Step 5: incidents.updates topic ──────────────────────────
                await incidents_updates.send(
                    value=json.dumps({"incident_id": incident["id"], "trace_id": trace_id}).encode()
                )

                log.info("incident_created", incident_id=incident["id"], technique=technique_id, trace_id=trace_id)
                break  # Success — exit retry loop

            except Exception as exc:
                retries += 1
                log.error("triage_error", attempt=retries, error=str(exc))
                if retries > MAX_TRIAGE_RETRIES:
                    # Dead-letter the alert after exhausting retries
                    await alerts_dead_letter.send(value=alert_bytes)
                    log.error("alert_dead_lettered", alert_id=alert.get('alert_id', 'unknown'))


# ── Health check endpoint ─────────────────────────────────────────────────────

@app.page('/health')
async def health(web, request):
    return web.json({'status': 'ok', 'service': 'faust-worker'})


if __name__ == '__main__':
    app.main()
