# api/server.py
"""
FastAPI REST layer for the SOC Desktop Application.
All business logic lives in the flat project modules (config, database, services/).
This file only routes HTTP → backend functions.

NOTE: Import paths use the flat project structure (e.g. `import database`)
rather than the guide's `from backend import database`.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ── Ensure repo root is on sys.path ──────────────────────────────────────────
import sys
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import database
from services import incident_service


# ── Startup / shutdown ────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()          # create tables if missing
    yield


app = FastAPI(title="SOC Triager Desktop", version="1.0.0", lifespan=lifespan)

# Allow the pywebview webview to reach the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the UI folder as static files
_UI = _ROOT / "ui"
app.mount("/ui", StaticFiles(directory=str(_UI)), name="ui")


# ── Helper ────────────────────────────────────────────────────────────────────

def _not_found(msg: str):
    raise HTTPException(status_code=404, detail=msg)


# ── Incidents ─────────────────────────────────────────────────────────────────

@app.get("/api/incidents")
def list_incidents(
    limit: int = Query(50, ge=1, le=500),
    status: Optional[str] = None,
    severity: Optional[str] = None,
):
    return incident_service.list_incidents(limit=limit, status=status, severity=severity)


@app.get("/api/incidents/{incident_id}")
def get_incident(incident_id: str):
    inc = incident_service.get_incident(incident_id)
    if not inc:
        _not_found(f"Incident {incident_id} not found")
    return inc


class StatusUpdate(BaseModel):
    status: str
    actor: str = "analyst"


@app.post("/api/incidents/{incident_id}/status")
def update_status(incident_id: str, body: StatusUpdate):
    updated = incident_service.update_status(incident_id, body.status, body.actor)
    if not updated:
        _not_found(f"Incident {incident_id} not found")
    return updated


@app.get("/api/incidents/{incident_id}/chain")
def verify_chain(incident_id: str):
    return incident_service.verify_chain(incident_id)


# ── Alerts ────────────────────────────────────────────────────────────────────

@app.get("/api/alerts")
def list_alerts(incident_id: Optional[str] = None, limit: int = 200):
    database.init_db()
    from config import DB_PATH
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    q = "SELECT * FROM alerts"
    params: list = []
    if incident_id:
        q += " WHERE incident_id = ?"
        params.append(incident_id)
    q += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Stats ─────────────────────────────────────────────────────────────────────

@app.get("/api/stats")
def get_stats():
    incidents = incident_service.list_incidents(limit=1000)
    total = len(incidents)
    by_sev: dict = {}
    by_status: dict = {}
    for i in incidents:
        by_sev[i["severity"]] = by_sev.get(i["severity"], 0) + 1
        by_status[i["status"]] = by_status.get(i["status"], 0) + 1

    alerts = list_alerts(limit=10000)
    scores = [a["anomaly_score"] for a in alerts if a.get("anomaly_score")]
    avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0

    return {
        "total_incidents": total,
        "by_severity": by_sev,
        "by_status": by_status,
        "total_alerts": len(alerts),
        "avg_anomaly_score": avg_score,
        "critical_open": sum(
            1 for i in incidents
            if i.get("severity") == "critical" and i.get("status") == "open"
        ),
    }


# ── Detection Rules (loaded from mitre/rules.yaml) ────────────────────────────

_RULES_CACHE = None


@app.get("/api/rules")
def list_rules():
    global _RULES_CACHE
    if _RULES_CACHE is not None:
        return _RULES_CACHE
    try:
        import yaml
        rules_path = _ROOT / "mitre" / "rules.yaml"
        with open(rules_path) as f:
            data = yaml.safe_load(f)
        _RULES_CACHE = data.get("rules", data) if isinstance(data, dict) else data
    except Exception:
        _RULES_CACHE = []
    return _RULES_CACHE


# ── File Ingestion ────────────────────────────────────────────────────────────

@app.post("/api/ingest")
async def ingest_file(path: str = Query(..., description="Absolute path to log file")):
    """
    Trigger ingestion of a log file.
    Runs in a thread pool to avoid blocking the event loop.
    """
    from concurrent.futures import ThreadPoolExecutor
    loop = asyncio.get_event_loop()

    def _do_ingest():
        from ingestion.file_ingestor import FileIngestor
        ingestor = FileIngestor()
        return ingestor.ingest(path)

    with ThreadPoolExecutor(max_workers=1) as pool:
        result = await loop.run_in_executor(pool, _do_ingest)
    return {"status": "ok", "result": str(result)}


# ── SSE Live Alert Stream ─────────────────────────────────────────────────────

@app.get("/api/stream")
async def alert_stream():
    """
    Server-Sent Events endpoint.
    The frontend subscribes once and receives new alerts in real time.
    """
    from api.stream import alert_generator
    return StreamingResponse(
        alert_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "ts": datetime.now(timezone.utc).isoformat()}
