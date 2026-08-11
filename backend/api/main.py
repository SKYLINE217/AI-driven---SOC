"""
SOC Triager — Main FastAPI Backend
Incident API (port 8000): alerts, incidents, playbooks, auth, WebSocket
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from backend.api.routers import alerts, incidents, auth, metrics, navigator, playbooks
from backend.api.websocket import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    yield
    # shutdown


app = FastAPI(
    title="SOC Triager — Incident API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow Vercel preview URLs + localhost dev
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    os.environ.get("VERCEL_URL", ""),
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in ALLOWED_ORIGINS if o],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
app.include_router(incidents.router, prefix="/incidents", tags=["incidents"])
app.include_router(navigator.router, prefix="/navigator", tags=["navigator"])
app.include_router(playbooks.router, prefix="/playbooks", tags=["playbooks"])
app.include_router(metrics.router, prefix="/metrics-api", tags=["metrics"])
app.include_router(ws_router, tags=["websocket"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "incident-api"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.api.main:app", host="0.0.0.0", port=8000, reload=True)
