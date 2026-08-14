# SOC Triager — Desktop Application Build Guide

**Target:** Convert the AI-Driven SOC Dashboard (React/JSX) into a lightweight, single-command Python desktop app  
**Command:** `python main.py` → native window opens with full SOC functionality  
**Stack:** Python · PyWebView · FastAPI · SQLite · Vanilla JS (compiled from existing JSX logic)

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Project Structure](#2-project-structure)
3. [Prerequisites & Installation](#3-prerequisites--installation)
4. [Backend — FastAPI REST Server](#4-backend--fastapi-rest-server)
5. [Frontend — Porting JSX to Vanilla JS](#5-frontend--porting-jsx-to-vanilla-js)
6. [The Main Entry Point](#6-the-main-entry-point)
7. [Database Layer](#7-database-layer)
8. [Live Alert Feed (SSE)](#8-live-alert-feed-sse)
9. [Performance & RAM Optimisation](#9-performance--ram-optimisation)
10. [All Six Dashboard Pages — Implementation Map](#10-all-six-dashboard-pages--implementation-map)
11. [Incident Detail Tabs — Implementation Map](#11-incident-detail-tabs--implementation-map)
12. [Complete File-by-File Code Guide](#12-complete-file-by-file-code-guide)
13. [Running & Testing](#13-running--testing)
14. [Packaging Into a Single Executable](#14-packaging-into-a-single-executable)
15. [Common Pitfalls & Fixes](#15-common-pitfalls--fixes)

---

## 1. Architecture Overview

```
python main.py
      │
      ├─► starts FastAPI on localhost:8765 (background thread, no console)
      │         │
      │         ├── GET  /api/incidents        ← incident_service.py
      │         ├── GET  /api/incidents/{id}
      │         ├── POST /api/incidents/{id}/status
      │         ├── GET  /api/alerts
      │         ├── GET  /api/rules
      │         ├── GET  /api/stats
      │         ├── GET  /api/stream           ← SSE live alert feed
      │         └── POST /api/ingest           ← file_ingestor.py
      │
      └─► opens pywebview window
                │
                └── loads  ui/index.html
                              │
                              ├── ui/app.js       (all 6 pages, ported from JSX)
                              ├── ui/style.css    (CSS variables from SOC_Dashboard.jsx)
                              └── fetches /api/* for all live data
```

**Why this stack?**

| Concern | Choice | Reason |
|---|---|---|
| Native window | `pywebview` | Ships a real OS window (WKWebView / WebView2 / GTK); 0 Electron overhead |
| HTTP backend | `FastAPI + uvicorn` | Async, lightweight, already matches the existing backend structure |
| DB | `sqlite3` (stdlib) | Already used; zero extra deps; file-based, instant startup |
| Frontend | Vanilla JS | No Node.js, no build step, no npm; the existing JSX logic is 95% plain JS anyway |
| ML/MITRE | Lazy-loaded | Heavy modules (torch, sklearn) load on first use, not on startup |

---

## 2. Project Structure

After following this guide your repository will look like this:

```
AI-driven-SOC/
├── main.py                         ← THE single entry point
├── requirements_desktop.txt        ← lean dependency list for the GUI app
│
├── backend/                        ← existing code — do NOT modify
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── display.py
│   ├── soc_triager.py
│   ├── services/
│   │   ├── incident_service.py
│   │   └── triage.py
│   ├── artifacts/
│   ├── ingestion/
│   ├── mitre/
│   └── ml/
│
├── api/                            ← NEW: FastAPI layer (thin wrappers only)
│   ├── __init__.py
│   ├── server.py                   ← FastAPI app + all routes
│   └── stream.py                   ← SSE live alert generator
│
├── ui/                             ← NEW: single-page frontend
│   ├── index.html
│   ├── style.css
│   └── app.js
│
└── data/
    ├── mitre/
    │   └── enterprise-attack-v15.1.json
    └── soc_triager.db              ← auto-created on first run
```

---

## 3. Prerequisites & Installation

### 3.1 Python version

Python 3.11 or 3.12 recommended. Python 3.10 minimum.

```bash
python --version   # must be >= 3.10
```

### 3.2 System dependencies

**Windows** — No extra steps. PyWebView uses WebView2 (built into Windows 10/11).

**macOS** — No extra steps. PyWebView uses WKWebView.

**Linux (Ubuntu/Debian)**

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 \
                 gir1.2-webkit2-4.0 libgtk-3-dev libwebkit2gtk-4.0-dev
```

### 3.3 Install Python dependencies

Create a file `requirements_desktop.txt`:

```
# Window
pywebview>=5.0.0

# API server
fastapi>=0.115.0
uvicorn[standard]>=0.30.0

# Already in the project's requirements.txt — keep them:
pydantic>=2.10.0
pyyaml
jinja2
rich
```

> **RAM note:** Do NOT install `torch`, `scikit-learn`, or `mitreattack-python` unless the user actively runs ML training. The desktop app uses the already-trained scores stored in SQLite and falls back to deterministic triage. Add them to a separate `requirements_ml.txt`.

Install:

```bash
pip install -r requirements_desktop.txt
```

---

## 4. Backend — FastAPI REST Server

Create `api/server.py`. This is a thin adapter layer. It calls the **existing** `backend/` functions — no business logic lives here.

```python
# api/server.py
"""
FastAPI REST layer for the SOC Desktop Application.
All business logic lives in backend/. This file only routes HTTP → backend.
"""
from __future__ import annotations

import asyncio
import json
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ── Ensure repo root is on sys.path ──────────────────────────────────────────
import sys
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend import database
from backend.services import incident_service


# ── Startup / shutdown ────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()          # create tables if missing
    yield
    # nothing to clean up


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
    import sqlite3
    from backend.config import DB_PATH
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
    by_sev = {}
    by_status = {}
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


# ── Detection Rules (loaded from MITRE rules.yaml) ────────────────────────────

_RULES_CACHE = None

@app.get("/api/rules")
def list_rules():
    global _RULES_CACHE
    if _RULES_CACHE is not None:
        return _RULES_CACHE
    try:
        import yaml
        rules_path = _ROOT / "backend" / "mitre" / "rules.yaml"
        with open(rules_path) as f:
            data = yaml.safe_load(f)
        _RULES_CACHE = data.get("rules", data) if isinstance(data, dict) else data
    except Exception as exc:
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
        from backend.ingestion.file_ingestor import FileIngestor
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
```

---

## 5. Frontend — Porting JSX to Vanilla JS

The `SOC_Dashboard.jsx` file is already 95% plain JavaScript. The only React-specific patterns to replace are:

### 5.1 Pattern translation table

| JSX / React pattern | Vanilla JS replacement |
|---|---|
| `useState(x)` | `let x = initial; function setX(v){ x=v; render(); }` |
| `useEffect(() => {...}, [])` | `document.addEventListener('DOMContentLoaded', ...)` |
| `useCallback`, `useMemo` | Plain functions / cached variables |
| `<Component prop={val} />` | `renderComponent(val)` returning an HTML string |
| `style={{ color: "red" }}` | `style="color:red"` |
| `className="..."` | `class="..."` |
| JSX template literals | Template literal strings returning HTML |
| `onClick={fn}` | `onclick="fn()"` or `addEventListener` |
| `<>{...}</>` fragments | `<div>...</div>` wrapper |
| Recharts `<LineChart>` | Native `<canvas>` with Chart.js (already in CDN) |

### 5.2 State management pattern (no React needed)

```javascript
// ui/app.js — global state object
const STATE = {
  page: 'alerts',
  role: 'analyst',
  incidents: [],
  alerts: [],
  stats: {},
  rules: [],
  selectedIncident: null,
  detailTab: 'overview',
  alertFilter: 'all',
  newAlertCount: 0,
};

function setState(patch) {
  Object.assign(STATE, patch);
  render();          // full re-render (fast for <500 rows)
}

function render() {
  document.getElementById('main-content').innerHTML = renderPage();
  document.getElementById('sidebar').innerHTML = renderSidebar();
  attachEventListeners();   // re-attach after innerHTML replacement
}
```

### 5.3 `ui/index.html` — the shell

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>SOC Triager</title>
  <link rel="stylesheet" href="/ui/style.css" />
  <!-- Chart.js for charts (replaces Recharts) -->
  <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.3/chart.umd.min.js"></script>
</head>
<body>
  <div id="app">
    <nav id="sidebar"></nav>
    <main id="main-content">
      <div class="loading">Starting SOC Triager…</div>
    </main>
  </div>
  <!-- Incident detail overlay -->
  <div id="detail-overlay" style="display:none"></div>
  <script src="/ui/app.js"></script>
</body>
</html>
```

### 5.4 `ui/style.css` — CSS variables (from SOC_Dashboard.jsx)

Copy the following CSS variables. These match **exactly** the inline styles used throughout the JSX file:

```css
/* ui/style.css */
:root {
  --bg:           #ffffff;
  --bg-accent:    #eff6ff;
  --surface-0:    #f8fafc;
  --surface-1:    #f1f5f9;
  --border:       #e2e8f0;
  --text-primary: #0f172a;
  --text-secondary:#64748b;
  --text-accent:  #1e3a8a;
  --accent:       #2a78d6;
  --accent-hover: #1d5fb0;

  /* Severity colours (from display.py SEVERITY_COLORS) */
  --sev-critical-bg:  #fef2f2;
  --sev-critical-br:  #fca5a5;
  --sev-critical-tx:  #991b1b;
  --sev-critical-dot: #ef4444;
  --sev-high-bg:      #fff7ed;
  --sev-high-br:      #fdba74;
  --sev-high-tx:      #9a3412;
  --sev-high-dot:     #f97316;
  --sev-medium-bg:    #fefce8;
  --sev-medium-br:    #fde047;
  --sev-medium-tx:    #854d0e;
  --sev-medium-dot:   #eab308;
  --sev-low-bg:       #f0fdf4;
  --sev-low-br:       #86efac;
  --sev-low-tx:       #166534;
  --sev-low-dot:      #22c55e;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: var(--bg);
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.5;
}

#app {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

/* ── Sidebar ── */
#sidebar {
  width: 200px;
  flex-shrink: 0;
  background: var(--surface-0);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 12px 8px;
  overflow-y: auto;
}

.nav-logo {
  font-size: 15px;
  font-weight: 700;
  color: var(--accent);
  padding: 4px 8px 16px;
  letter-spacing: -0.3px;
}

.nav-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: 6px;
  border: none;
  background: none;
  cursor: pointer;
  width: 100%;
  text-align: left;
  font-size: 12.5px;
  color: var(--text-secondary);
  transition: background 0.12s;
}
.nav-btn:hover  { background: var(--surface-1); color: var(--text-primary); }
.nav-btn.active { background: var(--bg-accent); color: var(--accent); font-weight: 600; }

.badge {
  margin-left: auto;
  background: #ef4444;
  color: #fff;
  border-radius: 9px;
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
}

/* ── Main Content ── */
#main-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}

/* ── Cards ── */
.card {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 16px;
}

/* ── Tables ── */
table { width: 100%; border-collapse: collapse; }
th {
  text-align: left;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 6px 12px;
  border-bottom: 1px solid var(--border);
  background: var(--surface-0);
}
td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--border);
  vertical-align: middle;
}
tr:hover td { background: var(--surface-0); }
tr:last-child td { border-bottom: none; }

/* ── Severity badges ── */
.sev-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
  border: 1px solid;
}
.sev-critical { background:var(--sev-critical-bg); border-color:var(--sev-critical-br); color:var(--sev-critical-tx); }
.sev-high     { background:var(--sev-high-bg);     border-color:var(--sev-high-br);     color:var(--sev-high-tx); }
.sev-medium   { background:var(--sev-medium-bg);   border-color:var(--sev-medium-br);   color:var(--sev-medium-tx); }
.sev-low      { background:var(--sev-low-bg);      border-color:var(--sev-low-br);      color:var(--sev-low-tx); }

/* ── Detail overlay ── */
#detail-overlay {
  position: fixed;
  top: 0; right: 0;
  width: 60vw;
  height: 100vh;
  background: var(--bg);
  border-left: 1px solid var(--border);
  box-shadow: -4px 0 24px rgba(0,0,0,0.10);
  z-index: 100;
  overflow-y: auto;
  padding: 24px;
}

/* ── Buttons ── */
.btn {
  padding: 6px 14px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--bg);
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  transition: background 0.1s;
}
.btn:hover { background: var(--surface-1); }
.btn-primary {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}
.btn-primary:hover { background: var(--accent-hover); }

/* ── Code blocks ── */
pre, code {
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 11px;
}
pre {
  background: var(--surface-0);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px;
  overflow-x: auto;
  white-space: pre-wrap;
}

/* ── Tabs ── */
.tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border); margin-bottom: 16px; }
.tab-btn {
  padding: 6px 14px;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-secondary);
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}
.tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }

/* ── Score bar ── */
.score-bar-track { flex: 1; height: 6px; background: var(--border); border-radius: 3px; }
.score-bar-fill  { height: 100%; border-radius: 3px; }

/* ── Loading ── */
.loading { color: var(--text-secondary); padding: 40px; text-align: center; }

/* ── MITRE heatmap ── */
.mitre-cell {
  padding: 3px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-family: monospace;
  cursor: pointer;
  user-select: none;
  transition: opacity 0.1s;
}
.mitre-cell:hover { opacity: 0.8; }

/* ── Stat cards grid ── */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}
.stat-card {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px 16px;
}
.stat-number { font-size: 26px; font-weight: 700; color: var(--text-primary); }
.stat-label  { font-size: 11px; color: var(--text-secondary); margin-top: 2px; }
```

---

## 6. The Main Entry Point

This is the only file your team runs. It starts the API server in a background thread, waits for it to be ready, then opens the OS window.

```python
# main.py
"""
SOC Triager Desktop Application
Usage: python main.py
"""
from __future__ import annotations

import sys
import threading
import time
import urllib.request
from pathlib import Path

# ── Fix encoding on Windows ───────────────────────────────────────────────────
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── Constants ─────────────────────────────────────────────────────────────────
API_HOST = "127.0.0.1"
API_PORT = 8765
API_BASE = f"http://{API_HOST}:{API_PORT}"
WINDOW_TITLE = "SOC Triager"
WINDOW_W = 1440
WINDOW_H = 860
MIN_W    = 1100
MIN_H    = 650


def _start_api_server():
    """Start FastAPI/uvicorn in a daemon thread. Logs suppressed for clean UX."""
    import logging
    import uvicorn

    logging.getLogger("uvicorn").setLevel(logging.ERROR)
    logging.getLogger("uvicorn.access").setLevel(logging.ERROR)
    logging.getLogger("uvicorn.error").setLevel(logging.ERROR)

    from api.server import app
    config = uvicorn.Config(
        app=app,
        host=API_HOST,
        port=API_PORT,
        log_level="error",
        loop="asyncio",
    )
    server = uvicorn.Server(config)
    server.run()


def _wait_for_api(timeout: float = 10.0):
    """Block until the API is accepting connections (or raise on timeout)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{API_BASE}/api/health", timeout=1)
            return
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("API server did not start within timeout")


def main():
    # 1) Start backend in background
    server_thread = threading.Thread(target=_start_api_server, daemon=True)
    server_thread.start()

    # 2) Wait until the API is ready (max 10 s)
    try:
        _wait_for_api()
    except RuntimeError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)

    # 3) Open the native window
    import webview  # pywebview

    window = webview.create_window(
        title=WINDOW_TITLE,
        url=f"{API_BASE}/ui/index.html",
        width=WINDOW_W,
        height=WINDOW_H,
        min_size=(MIN_W, MIN_H),
        resizable=True,
        text_select=True,      # allow copy-paste in the UI
        zoomable=True,
    )

    # Optional: expose a Python function the JS can call (e.g. for file dialogs)
    def pick_log_file():
        """Open a native file dialog and return the chosen path."""
        paths = window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=("Log Files (*.log *.csv *.json)",),
        )
        return paths[0] if paths else None

    window.expose(pick_log_file)

    # 4) Run the webview event loop (blocks until the window is closed)
    webview.start(debug=False)   # set debug=True to see the DevTools


if __name__ == "__main__":
    main()
```

---

## 7. Database Layer

The existing `backend/database.py` is already correct. Create `api/__init__.py` as an empty file:

```python
# api/__init__.py
```

The database file is created automatically at `data/soc_triager.db` on first launch. No migration scripts needed.

**Connection pooling note:** SQLite is not thread-safe by default. The existing code uses `get_connection()` (one connection per call) which is the correct pattern. Do NOT share a single connection across threads.

---

## 8. Live Alert Feed (SSE)

```python
# api/stream.py
"""
Server-Sent Events generator.
Polls the database every 2 seconds and pushes new alerts to the browser.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.config import DB_PATH


async def alert_generator():
    """Yields SSE-formatted events with new alerts."""
    seen_ids: set[str] = set()

    # Seed with existing alert IDs so we don't replay history on connect
    try:
        conn = sqlite3.connect(str(DB_PATH))
        rows = conn.execute("SELECT id FROM alerts").fetchall()
        seen_ids = {r[0] for r in rows}
        conn.close()
    except Exception:
        pass

    while True:
        await asyncio.sleep(2)
        try:
            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM alerts ORDER BY created_at DESC LIMIT 50"
            ).fetchall()
            conn.close()

            for row in rows:
                if row["id"] not in seen_ids:
                    seen_ids.add(row["id"])
                    payload = json.dumps(dict(row), default=str)
                    yield f"data: {payload}\n\n"
        except Exception:
            # DB not ready yet — just wait
            pass
```

---

## 9. Performance & RAM Optimisation

### 9.1 Lazy-load heavy modules

Add this to `api/server.py` for any heavy import:

```python
# Example: MITRE STIX loading
def _get_mitre_engine():
    """Load MitreRuleEngine only on first use."""
    global _MITRE_ENGINE
    if _MITRE_ENGINE is None:
        from backend.mitre.mapping_engine import MitreRuleEngine
        _MITRE_ENGINE = MitreRuleEngine()
    return _MITRE_ENGINE
_MITRE_ENGINE = None
```

### 9.2 Pagination

Always use `LIMIT` in SQL queries. The default `limit=50` in `list_incidents` already does this. In the frontend, implement virtual scrolling for tables with more than 200 rows:

```javascript
// ui/app.js — simple pagination (no library needed)
function renderTable(rows, page = 0, pageSize = 50) {
  const slice = rows.slice(page * pageSize, (page + 1) * pageSize);
  return `
    <table>
      <thead>...</thead>
      <tbody>
        ${slice.map(renderRow).join('')}
      </tbody>
    </table>
    <div class="pagination">
      ${page > 0 ? `<button onclick="setState({tablePage:${page-1}})">← Prev</button>` : ''}
      Page ${page + 1} / ${Math.ceil(rows.length / pageSize)}
      ${(page + 1) * pageSize < rows.length
          ? `<button onclick="setState({tablePage:${page+1}})">Next →</button>`
          : ''}
    </div>`;
}
```

### 9.3 Target RAM footprint

| Component | Expected RAM |
|---|---|
| Python process (FastAPI + uvicorn) | ~45 MB |
| PyWebView window (OS WebView) | ~80–110 MB |
| SQLite (file-based, no daemon) | 0 MB extra |
| ML modules (if loaded) | +300–800 MB |
| **Total (no ML)** | **~130–160 MB** |

### 9.4 Chart rendering

Use `Chart.js` via CDN instead of Recharts. Chart.js renders to `<canvas>` which is significantly more memory-efficient than SVG for time-series data.

```javascript
// Example: replace OpsPage's throughput AreaChart
function renderThroughputChart(containerId, data) {
  const ctx = document.getElementById(containerId).getContext('2d');
  new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.map(d => d.t),
      datasets: [{
        label: 'Events/min',
        data: data.map(d => d.v),
        fill: true,
        borderColor: '#2a78d6',
        backgroundColor: 'rgba(42,120,214,0.12)',
        tension: 0.3,
        pointRadius: 0,
      }]
    },
    options: {
      responsive: true,
      animation: false,      // disable animation for smooth updates
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: false } }
    }
  });
}
```

---

## 10. All Six Dashboard Pages — Implementation Map

Each page in the JSX maps to a function in `ui/app.js`. Below is the complete mapping with the data source for each.

### Page 1 — Alert Queue (`page === 'alerts'`)

**JSX source:** `AlertsPage` (line ~559)  
**API call:** `GET /api/incidents` + `GET /api/alerts`  
**Features to port:**
- Live alert ticker at top (SSE from `/api/stream`)
- Filter bar: ALL / CRITICAL / HIGH / MEDIUM / LOW
- Stats row: total incidents, critical open, avg score, total alerts
- Incident table with: entity, technique chip, severity badge, status badge, confidence score bar, alert count, age, "Open" button

```javascript
// ui/app.js
async function loadAlertsPage() {
  const [incidents, stats] = await Promise.all([
    fetch('/api/incidents').then(r => r.json()),
    fetch('/api/stats').then(r => r.json()),
  ]);
  STATE.incidents = incidents;
  STATE.stats = stats;
  render();
}

function renderAlertsPage() {
  const filtered = STATE.alertFilter === 'all'
    ? STATE.incidents
    : STATE.incidents.filter(i => i.severity === STATE.alertFilter);

  return `
    <div class="stat-grid">
      ${renderStatCard(STATE.stats.total_incidents, 'Total Incidents')}
      ${renderStatCard(STATE.stats.critical_open, 'Critical Open', '#ef4444')}
      ${renderStatCard(STATE.stats.total_alerts, 'Total Alerts')}
      ${renderStatCard(STATE.stats.avg_anomaly_score?.toFixed(3), 'Avg Score')}
    </div>
    <div class="card" style="padding:0;overflow:hidden">
      <div style="padding:12px 16px;border-bottom:1px solid var(--border);display:flex;gap:8px;align-items:center">
        <span style="font-weight:600">Alert Queue</span>
        ${['all','critical','high','medium','low'].map(f =>
          `<button class="btn ${STATE.alertFilter===f?'btn-primary':''}"
            onclick="setState({alertFilter:'${f}'})">
            ${f.charAt(0).toUpperCase()+f.slice(1)}
          </button>`
        ).join('')}
      </div>
      <table>
        <thead>
          <tr>
            <th>Entity</th><th>Technique</th><th>Severity</th>
            <th>Status</th><th>Score</th><th>Alerts</th><th>Age</th><th></th>
          </tr>
        </thead>
        <tbody>
          ${filtered.map(renderIncidentRow).join('')}
        </tbody>
      </table>
    </div>`;
}

function renderIncidentRow(inc) {
  return `
    <tr>
      <td><code style="font-size:11px">${escHtml(inc.entity)}</code></td>
      <td>${renderTechChip(inc.technique, inc.tactic)}</td>
      <td>${renderSevBadge(inc.severity)}</td>
      <td>${renderStatusBadge(inc.status)}</td>
      <td style="min-width:120px">${renderScoreBar(inc.confidence||0)}</td>
      <td>${inc.alert_count||'—'}</td>
      <td style="color:var(--text-secondary)">${timeAgo(inc.created_at)}</td>
      <td><button class="btn" onclick="openDetail('${inc.id}')">Open →</button></td>
    </tr>`;
}
```

### Page 2 — Incidents (`page === 'incidents'`)

**JSX source:** `IncidentsPage` (line ~647)  
**API call:** `GET /api/incidents`  
**Features:** Same table as Alert Queue but without the live feed header; includes filter by status dropdown.

### Page 3 — MITRE Navigator (`page === 'navigator'`)

**JSX source:** `NavigatorPage` (line ~937)  
**API call:** `GET /api/incidents` (to compute heat counts)  
**Features:**
- Heatmap grid: 11 tactics × 3–4 techniques each
- Cell colour: white=0, yellow=1, orange=2, red=3+
- Clicking a cell filters to matching incidents in a panel below

```javascript
const MITRE_MATRIX = [
  { tactic: "Initial Access",       techniques: ["T1078","T1190","T1566"] },
  { tactic: "Execution",            techniques: ["T1059","T1203","T1106"] },
  { tactic: "Persistence",          techniques: ["T1098","T1136","T1547"] },
  { tactic: "Privilege Escalation", techniques: ["T1548","T1068","T1134"] },
  { tactic: "Defense Evasion",      techniques: ["T1055","T1070","T1140"] },
  { tactic: "Credential Access",    techniques: ["T1110","T1003","T1110.001"] },
  { tactic: "Discovery",            techniques: ["T1046","T1083","T1057"] },
  { tactic: "Lateral Movement",     techniques: ["T1021","T1021.001","T1021.002","T1021.004"] },
  { tactic: "Collection",           techniques: ["T1005","T1025","T1074"] },
  { tactic: "Exfiltration",         techniques: ["T1041","T1048","T1052"] },
  { tactic: "Impact",               techniques: ["T1498","T1486","T1499"] },
];

function getHeatCount(tech) {
  return STATE.incidents.filter(i => i.technique === tech || i.technique?.startsWith(tech)).length;
}

function heatColor(c) {
  if (c === 0) return 'var(--surface-1)';
  if (c === 1) return '#fef3c7';
  if (c === 2) return '#fed7aa';
  return '#fca5a5';
}

function renderNavigatorPage() {
  return `
    <h2 style="margin-bottom:16px;font-size:16px">MITRE ATT&CK Navigator</h2>
    <div style="overflow-x:auto">
      <table style="border-collapse:separate;border-spacing:2px">
        <thead>
          <tr>
            ${MITRE_MATRIX.map(col =>
              `<th style="font-size:10px;padding:4px 6px;min-width:90px">
                ${col.tactic}
              </th>`
            ).join('')}
          </tr>
        </thead>
        <tbody>
          ${renderHeatRows()}
        </tbody>
      </table>
    </div>`;
}

function renderHeatRows() {
  const maxTechs = Math.max(...MITRE_MATRIX.map(c => c.techniques.length));
  return Array.from({length: maxTechs}, (_, row) =>
    `<tr>${MITRE_MATRIX.map(col => {
      const tech = col.techniques[row];
      if (!tech) return '<td></td>';
      const count = getHeatCount(tech);
      return `<td>
        <div class="mitre-cell"
             style="background:${heatColor(count)};color:${count>0?'#1e293b':'var(--text-secondary)'}"
             onclick="filterByTechnique('${tech}')"
             title="${tech} — ${count} incident(s)">
          ${tech}${count > 0 ? `<span style="float:right;font-weight:700">${count}</span>` : ''}
        </div>
      </td>`;
    }).join('')}</tr>`
  ).join('');
}
```

### Page 4 — Ops Metrics (`page === 'ops'`)

**JSX source:** `OpsPage` (line ~1016)  
**API call:** `GET /api/stats`  
**Features:** Four Chart.js canvases:
1. **Throughput** — Line chart, events/min over last 60 min (simulated from stats)
2. **Alert Volume** — Bar chart by day of week
3. **Latency** — Line chart, P50 and P95 triage latency
4. **Score Distribution** — Bar chart of anomaly score histogram

```javascript
function renderOpsPage() {
  return `
    <h2 style="margin-bottom:16px;font-size:16px">Operations Metrics</h2>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
      <div class="card">
        <div style="font-weight:600;margin-bottom:12px">Event Throughput (last 60m)</div>
        <canvas id="chart-throughput" height="160"></canvas>
      </div>
      <div class="card">
        <div style="font-weight:600;margin-bottom:12px">Alert Volume (weekly)</div>
        <canvas id="chart-volume" height="160"></canvas>
      </div>
      <div class="card">
        <div style="font-weight:600;margin-bottom:12px">Triage Latency</div>
        <canvas id="chart-latency" height="160"></canvas>
      </div>
      <div class="card">
        <div style="font-weight:600;margin-bottom:12px">Anomaly Score Distribution</div>
        <canvas id="chart-scores" height="160"></canvas>
      </div>
    </div>`;
}

// Call this after render() to paint charts:
function initOpsCharts() {
  if (STATE.page !== 'ops') return;
  renderThroughputChart('chart-throughput', genThroughput());
  renderVolumeChart('chart-volume', genAlertVolume());
  renderLatencyChart('chart-latency', genLatency());
  renderScoreChart('chart-scores', generateScoreDistribution());
}
```

### Page 5 — Playbook Library (`page === 'playbooks'`)

**JSX source:** `PlaybooksPage` (line ~1109)  
**Data:** Static `PLAYBOOK_CATALOG` constant (from the JSX — no API needed)  
**Features:** Card grid listing each playbook template with technique, IOC variables, and action steps.

### Page 6 — Detection Rules (`page === 'rules'`)

**JSX source:** `RulesPage` (line ~1152)  
**API call:** `GET /api/rules` (reads `backend/mitre/rules.yaml`)  
**Features:** Table of all MITRE rules with: rule ID, technique ID, name, tactic, condition string, and an enabled/disabled toggle.

---

## 11. Incident Detail Tabs — Implementation Map

When a user clicks "Open →" the detail overlay slides in. It has 5 tabs:

### Tab 1 — Overview

**JSX source:** lines ~742–800  
Renders the incident summary panel: entity, technique, tactic, confidence score bar, rationale, recommended action, list of alerts for the incident.

```javascript
function renderOverviewTab(inc) {
  return `
    <div class="card" style="margin-bottom:12px">
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div>
          <div style="font-size:18px;font-weight:700;margin-bottom:4px">
            ${escHtml(inc.entity)}
          </div>
          ${renderTechChip(inc.technique, inc.tactic)}
          ${renderSevBadge(inc.severity)}
          ${renderStatusBadge(inc.status)}
        </div>
        <div style="display:flex;gap:8px">
          ${['open','investigating','resolved','false_positive'].map(s =>
            `<button class="btn ${inc.status===s?'btn-primary':''}"
              onclick="updateStatus('${inc.id}','${s}')">
              ${s.replace('_',' ')}
            </button>`
          ).join('')}
        </div>
      </div>
    </div>
    <div style="font-size:12px;color:var(--text-secondary);margin-bottom:12px">
      ${escHtml(inc.rationale || '')}
    </div>
    <div style="font-size:12px;padding:10px;background:var(--surface-0);border-radius:6px;border:1px solid var(--border)">
      <strong>Recommended Action:</strong>
      ${escHtml(inc.recommended_immediate_action || '')}
    </div>`;
}
```

### Tab 2 — Attack Graph

**JSX source:** `genMermaidGraph` function  
**Render:** Use `<pre>` to display the Mermaid graph source (the JSX version rendered as text in the mock). For full rendering, include Mermaid.js from CDN:

```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/mermaid/10.9.0/mermaid.min.js"></script>
```

```javascript
function renderGraphTab(inc) {
  const graphSrc = genMermaidGraph(inc);
  return `
    <div class="mermaid">${escHtml(graphSrc)}</div>
    <script>mermaid.init()</script>`;
}
```

### Tab 3 — MITRE

**JSX source:** `MitreTab` component (line ~743)  
Displays the technique card with: technique ID, name, tactic, confidence, rationale, and a mini heatmap column showing where this technique sits in the ATT&CK matrix.

### Tab 4 — Playbook

**JSX source:** `genPlaybook()` function  
Renders the Ansible YAML playbook as a `<pre>` block. Include a "Copy" button using `navigator.clipboard.writeText()`.

```javascript
function renderPlaybookTab(inc) {
  const yaml = genPlaybook(inc);
  return `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
      <strong>Containment Playbook — DRAFT</strong>
      <button class="btn" onclick="navigator.clipboard.writeText(\`${yaml.replace(/`/g,'\\`')}\`)">
        Copy YAML
      </button>
    </div>
    <div style="background:#fff7ed;border:1px solid #fdba74;border-radius:6px;padding:10px;
                font-size:11px;color:#9a3412;margin-bottom:12px">
      ⚠️ DRAFT ONLY — Requires Approver authorization before execution.
    </div>
    <pre>${escHtml(yaml)}</pre>`;
}
```

### Tab 5 — Ledger

**JSX source:** `genLedger()` + `LedgerEntry` from `incident_service.py`  
**API call:** `GET /api/incidents/{id}` (includes the `ledger` array)  
Shows the hash-chained audit trail with: sequence number, action, actor, timestamp, previous hash, this hash, and a ✓/✗ validity indicator.

```javascript
function renderLedgerTab(inc) {
  const ledger = inc.ledger || [];
  return `
    <table>
      <thead>
        <tr>
          <th>Seq</th><th>Action</th><th>Actor</th>
          <th>Timestamp</th><th>Hash</th><th>Valid</th>
        </tr>
      </thead>
      <tbody>
        ${ledger.map(e => `
          <tr>
            <td>${e.id}</td>
            <td><code>${escHtml(e.action)}</code></td>
            <td>${escHtml(e.actor)}</td>
            <td style="color:var(--text-secondary)">${e.timestamp?.slice(0,19)}</td>
            <td><code style="font-size:10px">${String(e.this_hash||'').slice(0,12)}…</code></td>
            <td style="color:${e.valid===false?'#ef4444':'#22c55e'};font-size:16px">
              ${e.valid === false ? '✗' : '✓'}
            </td>
          </tr>`
        ).join('')}
      </tbody>
    </table>`;
}
```

---

## 12. Complete File-by-File Code Guide

Below is the complete list of files you need to create. Files marked **[EXISTING — DO NOT TOUCH]** already exist in the repository.

### Files to CREATE

```
main.py                     ← Full code in Section 6
api/__init__.py             ← Empty file
api/server.py               ← Full code in Section 4
api/stream.py               ← Full code in Section 8
ui/index.html               ← Full code in Section 5.3
ui/style.css                ← Full code in Section 5.4
requirements_desktop.txt    ← Full code in Section 3.3
```

### Files — EXISTING, DO NOT MODIFY

```
backend/__init__.py
backend/config.py
backend/database.py
backend/display.py
backend/models.py
backend/soc_triager.py
backend/services/incident_service.py
backend/services/triage.py
backend/artifacts/
backend/ingestion/
backend/mitre/
backend/ml/
data/mitre/enterprise-attack-v15.1.json
```

### `ui/app.js` — Skeleton

The full `app.js` is assembled from all the code blocks in Sections 5 and 10. The skeleton below shows the required function order and wiring:

```javascript
// ui/app.js
'use strict';

// ── Global state ──────────────────────────────────────────────────────────────
const STATE = {
  page: 'alerts',
  role: 'analyst',
  incidents: [],
  alerts: [],
  stats: {},
  rules: [],
  selectedIncident: null,
  detailTab: 'overview',
  alertFilter: 'all',
  tablePage: 0,
  newAlertCount: 0,
};

// ── Utility helpers ───────────────────────────────────────────────────────────
function escHtml(str) {
  return String(str||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function timeAgo(isoStr) {
  if (!isoStr) return '—';
  const diff = (Date.now() - new Date(isoStr)) / 1000;
  if (diff < 60)   return `${Math.round(diff)}s ago`;
  if (diff < 3600) return `${Math.round(diff/60)}m ago`;
  if (diff < 86400)return `${Math.round(diff/3600)}h ago`;
  return `${Math.round(diff/86400)}d ago`;
}

// ── Small component functions ─────────────────────────────────────────────────
function renderSevBadge(sev) { /* ... see Section 5.1 pattern ... */ }
function renderStatusBadge(status) { /* ... */ }
function renderTechChip(id, tactic) { /* ... */ }
function renderScoreBar(score) { /* ... */ }
function renderStatCard(value, label, color) { /* ... */ }

// ── Data generators (from SOC_Dashboard.jsx — copy directly) ─────────────────
function genThroughput() { /* ... copy from JSX */ }
function genAlertVolume() { /* ... copy from JSX */ }
function genLatency() { /* ... copy from JSX */ }
function generateScoreDistribution() { /* ... copy from JSX */ }
function genPlaybook(incident) { /* ... copy from JSX */ }
function genMermaidGraph(incident) { /* ... copy from JSX */ }
function genLedger(incident) { /* ... copy from JSX */ }
function genReport(incident) { /* ... copy from JSX */ }

// ── API calls ─────────────────────────────────────────────────────────────────
async function api(path, opts) {
  const res = await fetch('/api' + path, opts);
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`);
  return res.json();
}

async function loadData() {
  const [incidents, stats, rules] = await Promise.all([
    api('/incidents'),
    api('/stats'),
    api('/rules'),
  ]);
  STATE.incidents = incidents;
  STATE.stats = stats;
  STATE.rules = rules;
}

async function updateStatus(incidentId, newStatus) {
  await api(`/incidents/${incidentId}/status`, {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ status: newStatus, actor: STATE.role }),
  });
  await loadData();
  if (STATE.selectedIncident?.id === incidentId) {
    const updated = await api(`/incidents/${incidentId}`);
    STATE.selectedIncident = updated;
  }
  render();
}

async function openDetail(incidentId) {
  const inc = await api(`/incidents/${incidentId}`);
  STATE.selectedIncident = inc;
  STATE.detailTab = 'overview';
  renderDetail();
}

// ── Page renderers ────────────────────────────────────────────────────────────
function renderSidebar() { /* ... nav buttons ... */ }
function renderAlertsPage() { /* ... Section 10, Page 1 ... */ }
function renderIncidentsPage() { /* ... Section 10, Page 2 ... */ }
function renderNavigatorPage() { /* ... Section 10, Page 3 ... */ }
function renderOpsPage() { /* ... Section 10, Page 4 ... */ }
function renderPlaybooksPage() { /* ... Section 10, Page 5 ... */ }
function renderRulesPage() { /* ... Section 10, Page 6 ... */ }

function renderPage() {
  switch (STATE.page) {
    case 'alerts':    return renderAlertsPage();
    case 'incidents': return renderIncidentsPage();
    case 'navigator': return renderNavigatorPage();
    case 'ops':       return renderOpsPage();
    case 'playbooks': return renderPlaybooksPage();
    case 'rules':     return renderRulesPage();
    default:          return renderAlertsPage();
  }
}

// ── Detail overlay ────────────────────────────────────────────────────────────
function renderDetail() { /* ... overlay with 5 tabs ... */ }
function closeDetail() { /* ... hide overlay ... */ }

// ── Global render ─────────────────────────────────────────────────────────────
function setState(patch) {
  Object.assign(STATE, patch);
  render();
}

function render() {
  document.getElementById('sidebar').innerHTML = renderSidebar();
  document.getElementById('main-content').innerHTML = renderPage();
  if (STATE.selectedIncident) {
    document.getElementById('detail-overlay').style.display = 'block';
    document.getElementById('detail-overlay').innerHTML = renderDetailContent();
  } else {
    document.getElementById('detail-overlay').style.display = 'none';
  }
  if (STATE.page === 'ops') setTimeout(initOpsCharts, 0);
}

// ── SSE subscription ──────────────────────────────────────────────────────────
function subscribeToAlerts() {
  const es = new EventSource('/api/stream');
  es.onmessage = (e) => {
    const alert = JSON.parse(e.data);
    STATE.newAlertCount++;
    STATE.alerts.unshift(alert);
    // Re-render sidebar badge only (cheap)
    document.getElementById('sidebar').innerHTML = renderSidebar();
  };
  es.onerror = () => {
    setTimeout(subscribeToAlerts, 3000); // reconnect on error
  };
}

// ── Boot ──────────────────────────────────────────────────────────────────────
(async function boot() {
  await loadData();
  render();
  subscribeToAlerts();

  // Refresh data every 30 seconds
  setInterval(async () => {
    await loadData();
    render();
  }, 30_000);
})();
```

---

## 13. Running & Testing

### 13.1 First run

```bash
# From the repo root:
python main.py
```

A native window should open within 2–3 seconds. The API server starts on `http://127.0.0.1:8765`.

### 13.2 Verify the API is working

Open a second terminal while the app is running:

```bash
curl http://127.0.0.1:8765/api/health
# → {"status":"ok","ts":"..."}

curl http://127.0.0.1:8765/api/incidents | python -m json.tool
# → JSON list of incidents

curl http://127.0.0.1:8765/api/stats
# → {"total_incidents":...}
```

### 13.3 Debug mode

To open DevTools inside the window:

```python
# main.py — change this line:
webview.start(debug=True)
```

Right-click anywhere in the window → "Inspect Element".

### 13.4 Seed the database with test data

If your database is empty, run the existing CLI to ingest sample logs:

```bash
python -m backend.soc_triager ingest --source-type auth_log data/sample_auth.log
```

Or generate synthetic alerts:

```bash
python -m backend.soc_triager run --mode live
```

---

## 14. Packaging Into a Single Executable

Use PyInstaller to produce a standalone `.exe` (Windows) or binary (macOS/Linux) that the user can double-click.

### 14.1 Install PyInstaller

```bash
pip install pyinstaller
```

### 14.2 Build command

```bash
pyinstaller \
  --onefile \
  --windowed \
  --name "SOC-Triager" \
  --add-data "ui:ui" \
  --add-data "backend/mitre/rules.yaml:backend/mitre" \
  --add-data "data/mitre/enterprise-attack-v15.1.json:data/mitre" \
  --hidden-import "uvicorn.lifespan.on" \
  --hidden-import "uvicorn.lifespan.off" \
  --hidden-import "uvicorn.protocols.http.auto" \
  --hidden-import "uvicorn.protocols.websockets.auto" \
  main.py
```

**Windows note:** `--windowed` suppresses the console. Remove it during development to see error output.

**macOS note:** Add `--osx-bundle-identifier com.yourteam.soctriager` for a proper `.app` bundle.

### 14.3 Output

```
dist/
└── SOC-Triager.exe   (Windows, ~80 MB without ML)
    SOC-Triager       (macOS/Linux)
```

---

## 15. Common Pitfalls & Fixes

### Port already in use

If `8765` is taken, change `API_PORT` in `main.py` to any free port (e.g. `8766`). The window URL is built from the same constant so it will stay in sync.

### PyWebView shows a blank page

Usually means the API server did not start in time. Increase the wait timeout in `_wait_for_api(timeout=20.0)`.

### `ModuleNotFoundError: backend`

The repo root is not on `sys.path`. All files in `api/` already do:

```python
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
```

Make sure you run `python main.py` from the **repo root**, not from inside `api/` or `backend/`.

### MITRE STIX file not found

The STIX JSON is 43 MB. The `config.py` looks for it at `data/mitre/enterprise-attack-v15.1.json`. If it's missing, the rule engine falls back to the heuristic table in `rules.yaml` — no crash. You only need the STIX file for full technique name lookups.

### SQLite "database is locked"

This happens if two processes open the same `.db` file simultaneously. Only run one instance of `python main.py` at a time. The existing single-connection-per-call pattern in `incident_service.py` prevents locking within the app itself.

### Chart.js CDN unavailable (offline environment)

Download `chart.umd.min.js` and serve it locally:

```html
<!-- ui/index.html — replace CDN link with: -->
<script src="/ui/vendor/chart.umd.min.js"></script>
```

```bash
# Download once:
curl -o ui/vendor/chart.umd.min.js \
  https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.3/chart.umd.min.js
```

### Windows: pywebview shows white screen on first launch

WebView2 may need to initialise. Add a small splash delay:

```python
# main.py — in main():
window = webview.create_window(
    ...
    url="about:blank",   # start blank
)

def on_shown():
    time.sleep(0.3)
    window.load_url(f"{API_BASE}/ui/index.html")

webview.start(on_shown, debug=False)
```

---

## Quick-Start Checklist

```
☐ 1.  pip install -r requirements_desktop.txt
☐ 2.  Create  api/__init__.py   (empty)
☐ 3.  Create  api/server.py     (Section 4)
☐ 4.  Create  api/stream.py     (Section 8)
☐ 5.  Create  ui/index.html     (Section 5.3)
☐ 6.  Create  ui/style.css      (Section 5.4)
☐ 7.  Create  ui/app.js         (Section 12 skeleton + Sections 5/10/11 bodies)
☐ 8.  Create  main.py           (Section 6)
☐ 9.  python main.py            → window opens
☐ 10. curl /api/health          → {"status":"ok"}
☐ 11. All 6 sidebar pages load correctly
☐ 12. Click any incident → 5-tab detail panel opens
☐ 13. Change incident status → persists to SQLite
☐ 14. pyinstaller build (Section 14) produces a single binary
```

---

*Built for the AI-Driven SOC Triager project — Python 3.11+ · pywebview 5+ · FastAPI 0.115+*
