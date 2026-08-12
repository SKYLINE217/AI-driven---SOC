"""
FastAPI main application — SOC Triager backend.

Endpoints (Day 4):
  POST /api/auth/login        — mock login, issues JWT
  GET  /api/auth/me           — current user
  GET  /api/alerts            — alert list (JWT required)
  GET  /api/alerts/{id}       — alert detail
  POST /api/alerts/{id}/status
  GET  /api/incidents         — incident list
  GET  /api/incidents/{id}    — incident detail
  GET  /api/incidents/{id}/ledger
  POST /api/incidents/{id}/status
  POST /api/incidents/{id}/approve  (Approver only)
  GET  /api/incidents/{id}/report.md
  GET  /api/incidents/{id}/graph.mmd
  GET  /api/incidents/{id}/playbook
  GET  /api/metrics           — ops metrics with time-series
  GET  /api/navigator/layer.json
  GET  /api/mitre/technique/{id} — MITRE technique detail
  GET  /api/playbooks         — playbook template catalog
  WS   /ws/alerts             — live alert feed
"""

from __future__ import annotations

import math
import os
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import backend.api.incident_service as svc
from backend.api.auth_middleware import get_current_user
from backend.api.routers import alerts, auth, incidents, websocket
from backend.db.engine import engine

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise DB engine on startup; dispose cleanly on shutdown."""
    log.info("startup", msg="SOC Triager API starting — connecting to database")
    # Verify DB connectivity early so a misconfigured DATABASE_URL fails fast
    async with engine.connect() as conn:
        await conn.execute(__import__('sqlalchemy').text("SELECT 1"))
    log.info("startup", msg="Database connection OK")
    yield
    await engine.dispose()
    log.info("shutdown", msg="Database engine disposed")


app = FastAPI(
    title="SOC Triager API",
    description="AI-Driven SOC Triager — MITRE ATT&CK Incident Manager",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── CORS ────────────────────────────────────────────────────────────────────
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://*.vercel.app",
]
custom_origins = os.environ.get("CORS_ORIGINS", "")
if custom_origins:
    ALLOWED_ORIGINS.extend(o.strip() for o in custom_origins.split(","))

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Rate Limiting ────────────────────────────────────────────────────────────
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ─── Security Headers ─────────────────────────────────────────────────────────
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; object-src 'none'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:;"
        )
        return response

app.add_middleware(SecurityHeadersMiddleware)

# ─── Trace ID ─────────────────────────────────────────────────────────────────
from backend.middleware.trace_id import TraceIdMiddleware
app.add_middleware(TraceIdMiddleware)

# ─── Routers ─────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(alerts.router)
app.include_router(incidents.router)
app.include_router(websocket.router)


# ─── Ops Metrics ─────────────────────────────────────────────────────────────
@app.get("/api/metrics", tags=["metrics"])
async def get_metrics(_user: dict = Depends(get_current_user)):
    """Aggregated ops metrics with realistic time-series for Recharts panels."""
    from backend.llm.triage_client import get_llm_call_stats

    llm_stats = get_llm_call_stats()
    alert_data = svc.get_alerts(page=1, page_size=1000)
    alert_count = alert_data["total"]

    # Fixed seed for reproducibility in demo
    rng = random.Random(42)

    # 60-point throughput time series (last 1 hour at 1-min intervals)
    now_ts = 1723369200
    throughput_series = [
        {"t": now_ts - (59 - i) * 60, "v": max(0, 1200 + int(math.sin(i / 5) * 180) + rng.randint(-50, 50))}
        for i in range(60)
    ]

    # Latency p50/p95 series
    latency_series = [
        {
            "t": now_ts - (59 - i) * 60,
            "p50": max(800, 1850 + int(math.sin(i / 8) * 300)),
            "p95": max(1500, 4200 + int(math.cos(i / 6) * 500)),
        }
        for i in range(60)
    ]

    # 7-day daily alert volume
    daily_alerts = [
        {"day": f"Day -{6 - i}", "alerts": max(0, alert_count + rng.randint(-2, 4))}
        for i in range(7)
    ]

    # Anomaly score distribution histogram
    score_hist = [
        {"bin": "0.0–0.3", "count": 840},
        {"bin": "0.3–0.5", "count": 215},
        {"bin": "0.5–0.7", "count": 87},
        {"bin": "0.7–0.9", "count": 34},
        {"bin": "0.9–1.0", "count": alert_count},
    ]

    # LLM cost per 1k flagged (daily, last 7d)
    llm_cost_daily = [
        {"day": f"Day -{6 - i}", "cost_per_1k": round(0.18 + rng.uniform(-0.03, 0.05), 3)}
        for i in range(7)
    ]

    return {
        "event_throughput_eps": 1240,
        "alert_volume_24h": alert_count,
        "alert_volume_7d": sum(d["alerts"] for d in daily_alerts),
        "llm_stats": llm_stats,
        "pipeline_latency_p50_ms": 1850,
        "pipeline_latency_p95_ms": 4200,
        "anomaly_score_distribution": score_hist,
        "throughput_series": throughput_series,
        "latency_series": latency_series,
        "daily_alerts": daily_alerts,
        "llm_cost_daily": llm_cost_daily,
    }


# ─── MITRE Navigator Layer ────────────────────────────────────────────────────
@app.get("/api/navigator/layer.json", tags=["navigator"])
async def get_navigator_layer(_user: dict = Depends(get_current_user)):
    """Return a MITRE ATT&CK Navigator layer.json generated from current incidents."""
    incidents_data = svc.get_incidents(page=1, page_size=1000)
    all_incidents = incidents_data["items"]

    technique_counts: dict[str, int] = {}
    for inc in all_incidents:
        tid = inc.get("technique_id")
        if tid:
            technique_counts[tid] = technique_counts.get(tid, 0) + 1

    techniques = []
    max_count = max(technique_counts.values(), default=1)
    for tid, count in technique_counts.items():
        techniques.append({
            "techniqueID": tid,
            "score": round(count / max_count * 100),
            "comment": f"{count} incident(s)",
            "color": "",
            "enabled": True,
        })

    # Include all known techniques at score 0 for context
    all_tids = ["T1110.001", "T1041", "T1046", "T1021.004", "T1498", "T1078",
                "T1055", "T1548", "T1059", "T1021.001", "T1021.002"]
    existing = {t["techniqueID"] for t in techniques}
    for tid in all_tids:
        if tid not in existing:
            techniques.append({"techniqueID": tid, "score": 0, "comment": "", "color": "", "enabled": True})

    return {
        "name": "SOC Triager — Current Incidents",
        "versions": {"attack": "15", "navigator": "4.9.6", "layer": "4.5"},
        "domain": "enterprise-attack",
        "description": f"Auto-generated from {len(all_incidents)} incidents.",
        "gradient": {"colors": ["#f0f0f0", "#ff6666"], "minValue": 0, "maxValue": 100},
        "techniques": techniques,
        "top_techniques": [
            {"technique_id": t["techniqueID"], "score": t["score"], "comment": t["comment"]}
            for t in sorted(techniques, key=lambda x: x["score"], reverse=True)[:5]
            if t["score"] > 0
        ],
    }


# ─── MITRE Technique Detail ───────────────────────────────────────────────────
@app.get("/api/mitre/technique/{technique_id}", tags=["mitre"])
async def get_mitre_technique(technique_id: str, _user: dict = Depends(get_current_user)):
    """Return MITRE ATT&CK technique details for the Technique tab."""
    from backend.mitre.mapping_engine import get_technique
    data = get_technique(technique_id)
    # get_technique returns an empty dict on miss — enrich with ATT&CK URL
    if not data.get("name"):
        # Return stub if STIX data not loaded
        data = {
            "id": technique_id,
            "name": technique_id,
            "tactic": "Unknown",
            "description": "Technique details require the MITRE STIX corpus to be loaded.",
            "url": f"https://attack.mitre.org/techniques/{technique_id.replace('.', '/')}",
        }
    data["url"] = f"https://attack.mitre.org/techniques/{technique_id.replace('.', '/')}"
    return data


# ─── Playbook Library ─────────────────────────────────────────────────────────
PLAYBOOK_CATALOG = [
    {
        "id": "T1110", "name": "Brute Force IP Block",
        "technique_id": "T1110.x", "tactic": "Credential Access",
        "description": "Blocks the attacker IP at edge firewall and forces credential rotation on victim host.",
        "variables": ["attacker_ip", "victim_host", "victim_user"],
        "template": "brute_force.yml.j2",
    },
    {
        "id": "T1021", "name": "Lateral Movement Segmentation",
        "technique_id": "T1021.x", "tactic": "Lateral Movement",
        "description": "Blocks SMB/RDP/SSH pivot traffic from the compromised host.",
        "variables": ["victim_ip", "victim_host"],
        "template": "lateral_movement.yml.j2",
    },
    {
        "id": "T1498", "name": "DDoS Mitigation",
        "technique_id": "T1498.x", "tactic": "Impact",
        "description": "Rate-limits and drops attacker traffic; enables SYN cookie protection.",
        "variables": ["attacker_ip"],
        "template": "ddos_mitigation.yml.j2",
    },
    {
        "id": "T1548", "name": "Priv-Esc Account Suspend",
        "technique_id": "T1548.x", "tactic": "Privilege Escalation",
        "description": "Locks the escalated account, kills all active sessions, revokes sudo.",
        "variables": ["victim_user", "victim_host"],
        "template": "privesc_account_suspend.yml.j2",
    },
    {
        "id": "T1041", "name": "Data Exfil Egress Block",
        "technique_id": "T1041.x", "tactic": "Exfiltration",
        "description": "Blocks outbound traffic to the exfil destination and captures a forensic memory image.",
        "variables": ["attacker_ip", "victim_host"],
        "template": "data_exfil_egress_block.yml.j2",
    },
]


@app.get("/api/playbooks", tags=["playbooks"])
async def list_playbooks(_user: dict = Depends(get_current_user)):
    """Return the catalog of containment playbook templates."""
    return {"total": len(PLAYBOOK_CATALOG), "items": PLAYBOOK_CATALOG}


@app.get("/api/playbooks/{playbook_id}/template", tags=["playbooks"])
async def get_playbook_template(playbook_id: str, _user: dict = Depends(get_current_user)):
    """Return the raw Jinja2 template source for a playbook."""
    from fastapi.responses import PlainTextResponse
    playbook = next((p for p in PLAYBOOK_CATALOG if p["id"] == playbook_id), None)
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    template_path = Path("backend/artifacts/playbook_templates") / playbook["template"]
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Template file not found")
    return PlainTextResponse(template_path.read_text(), media_type="text/plain")


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "version": "0.4.0-day4"}
