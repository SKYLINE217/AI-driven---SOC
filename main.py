# main.py
"""
SOC Triager Desktop Application
Single entry point: python main.py

Stack: Python · CustomTkinter · SQLite · matplotlib
No HTTP server. No browser. No web stack.
"""
from __future__ import annotations

import sys
from pathlib import Path

# ── Ensure repo root is on sys.path so all flat imports resolve ───────────────
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── Fix encoding on Windows ───────────────────────────────────────────────────
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── Initialise database before GUI ───────────────────────────────────────────
import database
database.init_db()

# ── Launch GUI ────────────────────────────────────────────────────────────────
from gui.app import SOCApp

if __name__ == "__main__":
    app = SOCApp()
    app.mainloop()
