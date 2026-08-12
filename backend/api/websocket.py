"""
FastAPI WebSocket endpoint — durable streaming via Redis Streams (XREAD).

Replaces Redis Pub/Sub with Redis Streams so clients can replay missed
events on reconnect. Clients pass their last-seen stream ID as a query
param; the server replays from that point before switching to live polling.

Stream key: soc:ws:alerts
Consumer groups: soc-ws-analyst, soc-ws-senior_analyst, soc-ws-approver
Max stream length: 1000 entries (MAXLEN on each XADD from Faust worker)

Auth: JWT passed as ?token=<jwt> query param (same as before)
"""

from __future__ import annotations

import asyncio
import json
import os

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from backend.api.auth_middleware import decode_token

log = structlog.get_logger()

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

router = APIRouter()

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
STREAM_KEY = "soc:ws:alerts"
POLL_INTERVAL_MS = 2000   # ms to block on XREAD before sending heartbeat
HEARTBEAT_INTERVAL = 25   # seconds between heartbeats when stream is quiet


def verify_jwt(token: str) -> dict | None:
    """Verify a JWT token for WebSocket auth. Returns claims or None."""
    try:
        return decode_token(token)
    except Exception:
        return None


# ── In-process fallback (no Redis) ───────────────────────────────────────────

class ConnectionManager:
    """Single-instance in-process broadcast (dev/fallback only)."""
    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.active = [c for c in self.active if c is not ws]

    async def broadcast(self, message: str) -> None:
        dead: list[WebSocket] = []
        for conn in self.active:
            try:
                await conn.send_text(message)
            except Exception:
                dead.append(conn)
        for d in dead:
            self.disconnect(d)


manager = ConnectionManager()


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@router.websocket("/ws/alerts")
async def alerts_websocket(ws: WebSocket, token: str = "", last_id: str = "0"):
    """
    Live alert WebSocket with durable Redis Streams delivery.

    Query params:
      token    — Bearer JWT for authentication
      last_id  — Last Redis Stream ID received (e.g. "1723369200000-0").
                 Use "0" to replay all events, "$" for live-only.
                 Defaults to "0" (full replay) for new connections.
    """
    claims = verify_jwt(token)
    if not claims:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    role = claims.get("role", "analyst")
    trace_id = claims.get("sub", "unknown")

    await ws.accept()
    log.info("ws_connected", user=trace_id, role=role, last_id=last_id)

    if REDIS_AVAILABLE:
        await _stream_from_redis(ws, role, last_id, trace_id)
    else:
        log.warning("ws_redis_unavailable", msg="Falling back to in-process broadcast")
        manager.active.append(ws)
        await _heartbeat_loop(ws)
        manager.disconnect(ws)


async def _stream_from_redis(
    ws: WebSocket, role: str, last_id: str, trace_id: str
) -> None:
    """Read from Redis Stream, replay history then follow live."""
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)

    # Normalize last_id: "$" means "only new" — convert to latest ID
    if last_id == "$":
        info = await redis_client.xinfo_stream(STREAM_KEY)
        last_id = info.get("last-generated-id", "0-0") if info else "0-0"

    try:
        while True:
            try:
                # Block for POLL_INTERVAL_MS ms waiting for new entries
                entries = await redis_client.xread(
                    streams={STREAM_KEY: last_id},
                    count=50,
                    block=POLL_INTERVAL_MS,
                )
            except Exception as exc:
                log.warning("ws_redis_xread_error", error=str(exc))
                await asyncio.sleep(1)
                continue

            if entries:
                for _stream, messages in entries:
                    for msg_id, fields in messages:
                        last_id = msg_id  # Advance cursor
                        data = fields.get("data", "{}")
                        try:
                            await ws.send_text(data)
                        except Exception:
                            return  # Client disconnected
            else:
                # No new messages — send heartbeat so connection stays alive
                try:
                    await ws.send_text(
                        json.dumps({"type": "heartbeat", "last_id": last_id})
                    )
                except Exception:
                    return  # Client disconnected

    except WebSocketDisconnect:
        log.info("ws_disconnected", user=trace_id, last_id=last_id)
    finally:
        await redis_client.aclose()


async def _heartbeat_loop(ws: WebSocket) -> None:
    """Keep connection alive with periodic heartbeats (no-Redis path)."""
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            await ws.send_text(json.dumps({"type": "heartbeat"}))
    except WebSocketDisconnect:
        pass


# ── Publisher helper (called from Faust pipeline) ────────────────────────────

async def publish_alert_to_ws(alert_payload: dict) -> None:
    """
    Publish an alert to the Redis Stream for WebSocket delivery.
    Falls back to in-process broadcast if Redis is unavailable.
    """
    message = json.dumps({"type": "new_alert", "payload": alert_payload})

    if REDIS_AVAILABLE:
        try:
            redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
            await redis_client.xadd(STREAM_KEY, {"data": message}, maxlen=1000)
            await redis_client.aclose()
        except Exception as exc:
            log.warning("ws_publish_redis_failed", error=str(exc))
            await manager.broadcast(message)
    else:
        await manager.broadcast(message)
