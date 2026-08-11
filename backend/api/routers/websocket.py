"""
WebSocket router — /ws/alerts live alert feed.

Architecture:
- Client connects, gets a per-connection asyncio.Queue registered with incident_service.
- incident_service._broadcast() enqueues JSON messages.
- This handler dequeues and sends to the WebSocket client.
- On disconnect/error, the queue is unregistered.

The WebSocket endpoint does NOT require auth for simplicity in Day 3 (the BFF layer
validates the JWT before proxying the WS upgrade). In production, validate the token
from the initial HTTP request using `websocket.headers` before accepting.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

import backend.api.incident_service as svc

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket):
    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    svc.register_ws_client(queue)
    try:
        # Send all current alerts on connect (so the UI pre-populates immediately)
        current = svc.get_alerts(page=1, page_size=200)
        await websocket.send_json({"type": "initial_state", "alerts": current["items"]})

        while True:
            # Wait for a broadcast message with a keep-alive ping every 20s
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=20.0)
                await websocket.send_text(payload)
            except asyncio.TimeoutError:
                # Send a keep-alive ping to detect dead connections
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        svc.unregister_ws_client(queue)
