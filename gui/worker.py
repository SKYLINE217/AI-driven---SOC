# gui/worker.py
"""
Background data refresh worker.
Runs in a daemon thread; posts results to the main thread via tkinter's after().
NEVER touches any widget directly.
"""
from __future__ import annotations

import sqlite3
import sys
import threading
from pathlib import Path
from typing import Callable

# Ensure repo root on path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import database
from config import DB_PATH
from services.incident_service import list_incidents

REFRESH_INTERVAL = 30   # seconds between auto-refreshes


def _fetch_all() -> dict:
    """
    Fetch all data the UI needs.
    Returns plain Python dicts — no JSON, no HTTP.
    """
    incidents = list_incidents(limit=500)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    alerts = [
        dict(r) for r in conn.execute(
            "SELECT * FROM alerts ORDER BY created_at DESC LIMIT 1000"
        ).fetchall()
    ]
    conn.close()

    by_sev: dict[str, int]    = {}
    by_status: dict[str, int] = {}
    open_critical = 0
    for inc in incidents:
        sev = inc.get("severity", "low") or "low"
        st  = inc.get("status",   "open") or "open"
        by_sev[sev]   = by_sev.get(sev, 0) + 1
        by_status[st] = by_status.get(st, 0) + 1
        if sev == "critical" and st == "open":
            open_critical += 1

    scores = [a["anomaly_score"] for a in alerts if a.get("anomaly_score")]
    avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0

    new_alerts = [a for a in alerts if (a.get("status") or "new") == "new"]

    return {
        "incidents":       incidents,
        "alerts":          alerts,
        "total_incidents": len(incidents),
        "by_severity":     by_sev,
        "by_status":       by_status,
        "open_critical":   open_critical,
        "total_alerts":    len(alerts),
        "avg_score":       avg_score,
        "new_alerts":      new_alerts,
        "alert_count":     len(new_alerts),
    }


class BackgroundWorker:
    """Daemon thread that fetches data and posts it to the main thread."""

    def __init__(self, callback: Callable[[dict], None]):
        self._callback   = callback
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self):
        """Call from main thread after the root window exists."""
        # Immediate first fetch
        self._thread = threading.Thread(target=self._run, daemon=True, name="soc-worker")
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def trigger_refresh(self):
        """Immediately trigger a refresh (e.g. after a status update)."""
        t = threading.Thread(target=self._single_fetch, daemon=True)
        t.start()

    def _single_fetch(self):
        try:
            data = _fetch_all()
            self._post(data)
        except Exception as exc:
            print(f"[worker] refresh error: {exc}")

    def _run(self):
        # Fetch immediately on start
        self._single_fetch()
        while not self._stop_event.is_set():
            self._stop_event.wait(REFRESH_INTERVAL)
            if not self._stop_event.is_set():
                self._single_fetch()

    def _post(self, data: dict):
        """Schedule callback on the main tkinter event loop (thread-safe)."""
        try:
            from tkinter import _default_root  # type: ignore
            if _default_root:
                _default_root.after(0, self._callback, data)
        except Exception:
            pass
