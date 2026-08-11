"""
FastAPI WebSocket endpoint — streams alerts via Redis Pub/Sub
"""

from __future__ import annotations

import json
import os
from jose import jwt, JWTError
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

router = APIRouter()

JWT_SECRET = os.environ.get("JWT_SECRET", "dev_secret_change_me")
JWT_ALGORITHM = "HS256"

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


def verify_jwt(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.active = [c for c in self.active if c is not ws]

    async def broadcast(self, message: str) -> None:
        dead: list[WebSocket] = []
        for connection in self.active:
            try:
                await connection.send_text(message)
            except Exception:
                dead.append(connection)
        for d in dead:
            self.disconnect(d)


manager = ConnectionManager()


@router.websocket("/ws/alerts")
async def alerts_websocket(ws: WebSocket, token: str = ""):
    """
    WebSocket endpoint for live alert streaming.
    Token is passed as query param: /ws/alerts?token=<jwt>
    Auth validated before accepting connection.
    """
    claims = verify_jwt(token)
    if not claims:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(ws)

    if REDIS_AVAILABLE:
        redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("ws:alerts:broadcast")
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    await ws.send_text(message["data"])
        except WebSocketDisconnect:
            pass
        finally:
            await pubsub.unsubscribe("ws:alerts:broadcast")
            manager.disconnect(ws)
            await redis_client.aclose()
    else:
        # No Redis — keep connection alive, send heartbeats
        import asyncio
        try:
            while True:
                await asyncio.sleep(30)
                await ws.send_text(json.dumps({"type": "heartbeat"}))
        except WebSocketDisconnect:
            manager.disconnect(ws)


async def publish_alert_to_ws(alert_payload: dict) -> None:
    """
    Called by the incident correlation service to push an alert to all WS clients.
    Falls back to in-process broadcast if Redis is unavailable.
    """
    message = json.dumps({"type": "new_alert", "payload": alert_payload})

    if REDIS_AVAILABLE:
        redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
        await redis_client.publish("ws:alerts:broadcast", message)
        await redis_client.aclose()
    else:
        # Direct in-process broadcast (single-instance dev mode)
        await manager.broadcast(message)
