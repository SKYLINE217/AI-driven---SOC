# api/stream.py
"""
Server-Sent Events generator.
Polls the database every 2 seconds and pushes new alerts to the browser.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import DB_PATH


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
