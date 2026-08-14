# gui/pages/alert_queue.py
"""
Alert Queue page — main landing screen.
Shows all incidents from SQLite with severity filter + detail panel.
Data: services.incident_service.list_incidents()  — no hard-coded data.
"""
from __future__ import annotations
import sys
from pathlib import Path

import customtkinter as ctk

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gui import theme
from gui.widgets import (
    SectionHeader, ScrollableTable, SeverityBadge,
    StatusBadge, ScoreBar, TechniqueChip, StatCard, Divider,
)
from gui.pages.incident_detail import IncidentDetailPanel

SEVERITIES = ["all", "critical", "high", "medium", "low"]


class AlertQueuePage(ctk.CTkFrame):

    COLUMNS = [
        ("Severity",  100),
        ("Entity",    180),
        ("Technique", 100),
        ("Status",    110),
        ("Score",     110),
        ("Age",       90),
        ("",          70),   # Open button
    ]

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, fg_color=theme.get("surface_0"), corner_radius=0, **kwargs)
        self._app     = app
        self._detail: IncidentDetailPanel | None = None
        self._filter  = "all"
        self._incidents: list[dict] = []
        self._stats: dict = {}

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_stats()
        self._build_body()
        self._load()

    # ── Layout ──────────────────────────────────────────────────────────────────

    def _build_header(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 4))
        bar.grid_columnconfigure(0, weight=1)

        SectionHeader(bar, "Alert Queue").grid(row=0, column=0, sticky="w")

        # Filter buttons
        filter_frame = ctk.CTkFrame(bar, fg_color="transparent")
        filter_frame.grid(row=0, column=1, sticky="e")

        self._filter_btns: dict[str, ctk.CTkButton] = {}
        for sev in SEVERITIES:
            btn = ctk.CTkButton(
                filter_frame,
                text=sev.capitalize(),
                width=75, height=28,
                font=theme.FONT_SMALL,
                fg_color=theme.get("surface_1"),
                text_color=theme.get("text_secondary"),
                hover_color=theme.get("surface_hover"),
                border_width=1,
                border_color=theme.get("border"),
                corner_radius=6,
                command=lambda s=sev: self._apply_filter(s),
            )
            btn.pack(side="left", padx=3)
            self._filter_btns[sev] = btn

        # Refresh button
        ctk.CTkButton(
            filter_frame, text="⟳ Refresh",
            width=80, height=28,
            font=theme.FONT_SMALL,
            fg_color=theme.get("bg_accent"),
            text_color=theme.get("text_accent"),
            hover_color=theme.get("surface_hover"),
            corner_radius=6,
            command=self._load,
        ).pack(side="left", padx=(10, 0))

        self._set_active_filter("all")

    def _build_stats(self):
        self._stat_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._stat_frame.grid(row=1, column=0, sticky="ew", padx=24, pady=(8, 12))

    def _build_body(self):
        self._main = ctk.CTkFrame(self, fg_color="transparent")
        self._main.grid(row=2, column=0, sticky="nsew", padx=0, pady=0)
        self._main.grid_rowconfigure(0, weight=1)
        self._main.grid_columnconfigure(0, weight=1)

        self._table = ScrollableTable(self._main, columns=self.COLUMNS)
        self._table.grid(row=0, column=0, sticky="nsew", padx=24, pady=(0, 16))

    # ── Data ────────────────────────────────────────────────────────────────────

    def _load(self):
        from services.incident_service import list_incidents
        import sqlite3
        from config import DB_PATH
        import database
        try:
            self._incidents = list_incidents(limit=500)
            database.init_db()
            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            alerts = [dict(r) for r in conn.execute(
                "SELECT * FROM alerts ORDER BY created_at DESC LIMIT 1000").fetchall()]
            conn.close()

            total = len(self._incidents)
            open_critical = sum(1 for i in self._incidents
                                if i.get("severity") == "critical" and i.get("status") == "open")
            scores = [a["anomaly_score"] for a in alerts if a.get("anomaly_score")]
            avg   = round(sum(scores) / len(scores), 3) if scores else 0.0

            self._stats = {
                "total": total,
                "open_critical": open_critical,
                "total_alerts": len(alerts),
                "avg_score": avg,
            }
        except Exception as exc:
            print(f"[AlertQueuePage] load error: {exc}")

        self._refresh_stats()
        self._render_table()

    def refresh(self, data: dict):
        """Called by background worker."""
        self._incidents = data.get("incidents", self._incidents)
        self._stats = {
            "total": data.get("total_incidents", 0),
            "open_critical": data.get("open_critical", 0),
            "total_alerts": data.get("total_alerts", 0),
            "avg_score": data.get("avg_score", 0.0),
        }
        self._refresh_stats()
        self._render_table()

    def _refresh_stats(self):
        for w in self._stat_frame.winfo_children():
            w.destroy()
        s = self._stats
        cards = [
            (str(s.get("total", 0)),         "Total Incidents",  None),
            (str(s.get("open_critical", 0)), "Critical Open",    theme.sev_color("critical")),
            (str(s.get("total_alerts", 0)),  "Total Alerts",     None),
            (f"{s.get('avg_score', 0):.3f}", "Avg Score",        None),
        ]
        for value, label, color in cards:
            StatCard(self._stat_frame, value=value, label=label,
                     color=color, width=160).pack(side="left", padx=(0, 12))

    def _render_table(self):
        self._table.clear_rows()
        filtered = (
            self._incidents if self._filter == "all"
            else [i for i in self._incidents if (i.get("severity") or "").lower() == self._filter]
        )[:50]
        for inc in filtered:
            inc_id = inc["id"]
            ts     = str(inc.get("created_at", ""))[:16].replace("T", " ")
            age    = self._time_ago(inc.get("created_at", ""))

            self._table.add_row(
                cells=[
                    lambda p, s=inc.get("severity","low"):      SeverityBadge(p, s),
                    inc.get("entity", "?"),
                    lambda p, t=inc.get("technique","?"):        TechniqueChip(p, t),
                    lambda p, st=inc.get("status","open"):       StatusBadge(p, st),
                    lambda p, sc=float(inc.get("confidence",0) or 0): ScoreBar(p, sc),
                    age,
                    lambda p, iid=inc_id: self._open_btn(p, iid),
                ],
                on_click=lambda iid=inc_id: self._open_detail(iid),
            )

    # ── Filter ──────────────────────────────────────────────────────────────────

    def _apply_filter(self, sev: str):
        self._filter = sev
        self._set_active_filter(sev)
        self._render_table()

    def _set_active_filter(self, sev: str):
        for s, btn in self._filter_btns.items():
            if s == sev:
                btn.configure(fg_color=theme.get("text_accent"), text_color="white")
            else:
                btn.configure(fg_color=theme.get("surface_1"),
                              text_color=theme.get("text_secondary"))

    # ── Open detail ─────────────────────────────────────────────────────────────

    def _open_btn(self, parent, inc_id: str) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent, text="Open →",
            width=68, height=26,
            font=theme.FONT_SMALL,
            fg_color=theme.get("bg_accent"),
            text_color=theme.get("text_accent"),
            hover_color=theme.get("surface_hover"),
            corner_radius=6,
            command=lambda: self._open_detail(inc_id),
        )

    def _open_detail(self, inc_id: str):
        if self._detail:
            self._detail.destroy()
            self._detail = None

        self._table.grid(row=0, column=0, sticky="nsew", padx=(24, 0), pady=(0, 16))
        self._main.grid_columnconfigure(1, weight=0, minsize=600)

        self._detail = IncidentDetailPanel(
            self._main, incident_id=inc_id, on_close=self._close_detail,
        )
        self._detail.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)

    def _close_detail(self):
        if self._detail:
            self._detail.destroy()
            self._detail = None
        self._main.grid_columnconfigure(1, weight=0, minsize=0)
        self._table.grid(row=0, column=0, sticky="nsew", padx=24, pady=(0, 16))

    # ── Helpers ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _time_ago(iso: str) -> str:
        if not iso:
            return "—"
        from datetime import datetime, timezone
        try:
            dt   = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            diff = (datetime.now(timezone.utc) - dt).total_seconds()
            if diff < 60:    return f"{int(diff)}s ago"
            if diff < 3600:  return f"{int(diff/60)}m ago"
            if diff < 86400: return f"{int(diff/3600)}h ago"
            return f"{int(diff/86400)}d ago"
        except Exception:
            return iso[:10]
