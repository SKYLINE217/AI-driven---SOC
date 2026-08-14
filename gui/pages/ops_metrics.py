# gui/pages/ops_metrics.py
"""
Operations Metrics page.
Embeds matplotlib figures inside the Tk window using FigureCanvasTkAgg.
All data comes directly from SQLite — no hard-coded numbers.
"""
from __future__ import annotations
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone, timedelta

import customtkinter as ctk

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gui import theme
from gui.widgets import SectionHeader, StatCard, Divider

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np


def _mpl_style(fig, axes, dark: bool):
    """Apply SOC colour theme to matplotlib figure."""
    bg = "#1e293b" if dark else "#ffffff"
    fg = "#f1f5f9" if dark else "#0f172a"
    grid = "#334155" if dark else "#e2e8f0"

    fig.patch.set_facecolor(bg)
    for ax in (axes if hasattr(axes, "__iter__") else [axes]):
        ax.set_facecolor(bg)
        ax.tick_params(colors=fg, labelsize=8)
        ax.xaxis.label.set_color(fg)
        ax.yaxis.label.set_color(fg)
        ax.title.set_color(fg)
        for spine in ax.spines.values():
            spine.set_edgecolor(grid)
        ax.grid(True, color=grid, linewidth=0.5, linestyle="--", alpha=0.5)


class OpsMetricsPage(ctk.CTkFrame):

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, fg_color=theme.get("surface_0"), corner_radius=0, **kwargs)
        self._app       = app
        self._incidents = []
        self._alerts    = []
        self._canvases: list = []

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_stats()

        self._chart_area = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._chart_area.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 16))
        self._chart_area.grid_columnconfigure(0, weight=1)
        self._chart_area.grid_columnconfigure(1, weight=1)

        self._load()

    # ── Layout ──────────────────────────────────────────────────────────────────

    def _build_header(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 4))
        bar.grid_columnconfigure(0, weight=1)
        SectionHeader(bar, "Operations Metrics").grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            bar, text="⟳ Refresh",
            width=90, height=28, font=theme.FONT_SMALL,
            fg_color=theme.get("bg_accent"),
            text_color=theme.get("text_accent"),
            hover_color=theme.get("surface_hover"),
            corner_radius=6,
            command=self._load,
        ).grid(row=0, column=1, sticky="e")

    def _build_stats(self):
        self._stat_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._stat_frame.grid(row=1, column=0, sticky="ew", padx=24, pady=(8, 12))

    # ── Data ────────────────────────────────────────────────────────────────────

    def _load(self):
        import sqlite3
        import database
        from services.incident_service import list_incidents
        from config import DB_PATH

        try:
            self._incidents = list_incidents(limit=500)
            database.init_db()
            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            self._alerts = [dict(r) for r in conn.execute(
                "SELECT * FROM alerts ORDER BY created_at DESC LIMIT 2000").fetchall()]
            conn.close()
        except Exception as exc:
            print(f"[OpsMetrics] load error: {exc}")

        self._refresh_stats()
        self._render_charts()

    def refresh(self, data: dict):
        self._incidents = data.get("incidents", self._incidents)
        self._alerts    = data.get("alerts", self._alerts)
        self._refresh_stats()
        self._render_charts()

    def _refresh_stats(self):
        for w in self._stat_frame.winfo_children():
            w.destroy()
        incs   = self._incidents
        alerts = self._alerts
        total  = len(incs)
        crit   = sum(1 for i in incs if i.get("severity") == "critical" and i.get("status") == "open")
        scores = [a["anomaly_score"] for a in alerts if a.get("anomaly_score")]
        avg    = round(sum(scores) / len(scores), 3) if scores else 0.0
        resolved = sum(1 for i in incs if i.get("status") == "resolved")
        mttd = round(sum(
            (datetime.fromisoformat((i.get("updated_at") or "").replace("Z", "+00:00")).timestamp()
             - datetime.fromisoformat((i.get("created_at") or "").replace("Z", "+00:00")).timestamp())
            for i in incs
            if i.get("status") == "resolved" and i.get("updated_at") and i.get("created_at")
        ) / max(resolved, 1) / 60, 1)

        for value, label, color in [
            (str(total),        "Total Incidents", None),
            (str(crit),         "Critical Open",   theme.sev_color("critical")),
            (str(len(alerts)),  "Total Alerts",    None),
            (f"{avg:.3f}",      "Avg Score",       None),
            (f"{resolved}",     "Resolved",        theme.get("text_success")),
            (f"{mttd}m",        "Avg MTTD",        None),
        ]:
            StatCard(self._stat_frame, value=value, label=label,
                     color=color, width=130).pack(side="left", padx=(0, 10))

    # ── Charts ───────────────────────────────────────────────────────────────────

    def _render_charts(self):
        # Destroy old canvases
        for c in self._canvases:
            try:
                c.get_tk_widget().destroy()
            except Exception:
                pass
        self._canvases.clear()
        for w in self._chart_area.winfo_children():
            w.destroy()

        dark = ctk.get_appearance_mode() == "Dark"
        accent = "#60a5fa" if dark else "#2a78d6"

        self._chart_severity_dist(0, 0, dark, accent)
        self._chart_score_histogram(0, 1, dark, accent)
        self._chart_status_dist(1, 0, dark, accent)
        self._chart_alerts_over_time(1, 1, dark, accent)

    def _make_fig(self) -> tuple:
        fig, ax = plt.subplots(figsize=(5.2, 3.0), dpi=96)
        return fig, ax

    def _embed(self, fig, row: int, col: int):
        canvas = FigureCanvasTkAgg(fig, master=self._chart_area)
        canvas.draw()
        widget = canvas.get_tk_widget()
        widget.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
        self._canvases.append(canvas)
        plt.close(fig)

    def _chart_severity_dist(self, row, col, dark, accent):
        fig, ax = self._make_fig()
        _mpl_style(fig, ax, dark)
        by_sev = defaultdict(int)
        for inc in self._incidents:
            by_sev[(inc.get("severity") or "low")] += 1

        if not by_sev:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    transform=ax.transAxes,
                    color="#94a3b8", fontsize=11)
            ax.set_title("Incidents by Severity", fontsize=10, pad=8)
        else:
            order  = ["critical", "high", "medium", "low"]
            labels = [s for s in order if s in by_sev]
            values = [by_sev[s] for s in labels]
            colors_map = {
                "critical": "#ef4444", "high": "#f97316",
                "medium":   "#eab308", "low":  "#22c55e",
            }
            colors = [colors_map.get(s, "#94a3b8") for s in labels]
            wedges, texts, autotexts = ax.pie(
                values, labels=labels, colors=colors,
                autopct="%1.0f%%", startangle=90,
                textprops={"fontsize": 8},
            )
            for at in autotexts:
                at.set_color("white")
                at.set_fontweight("bold")
            ax.set_title("Incidents by Severity", fontsize=10, pad=8)

        fig.tight_layout(pad=1.5)
        self._embed(fig, row, col)

    def _chart_score_histogram(self, row, col, dark, accent):
        fig, ax = self._make_fig()
        _mpl_style(fig, ax, dark)
        scores = [a["anomaly_score"] for a in self._alerts if a.get("anomaly_score") is not None]

        if not scores:
            ax.text(0.5, 0.5, "No score data", ha="center", va="center",
                    transform=ax.transAxes, color="#94a3b8", fontsize=11)
        else:
            ax.hist(scores, bins=20, color=accent, alpha=0.85, edgecolor="none", rwidth=0.85)
            ax.set_xlabel("Anomaly Score", fontsize=8)
            ax.set_ylabel("Alert Count",   fontsize=8)
            mean = sum(scores) / len(scores)
            ax.axvline(mean, color="#ef4444", linestyle="--", linewidth=1.2,
                       label=f"Mean {mean:.3f}")
            ax.legend(fontsize=7)

        ax.set_title("Anomaly Score Distribution", fontsize=10, pad=8)
        fig.tight_layout(pad=1.5)
        self._embed(fig, row, col)

    def _chart_status_dist(self, row, col, dark, accent):
        fig, ax = self._make_fig()
        _mpl_style(fig, ax, dark)
        by_status = defaultdict(int)
        for inc in self._incidents:
            by_status[(inc.get("status") or "open")] += 1

        if not by_status:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    transform=ax.transAxes, color="#94a3b8", fontsize=11)
        else:
            labels = list(by_status.keys())
            values = [by_status[l] for l in labels]
            sc = {"open":"#3b82f6","investigating":"#f59e0b",
                  "resolved":"#22c55e","false_positive":"#94a3b8"}
            colors = [sc.get(l, accent) for l in labels]
            bars = ax.bar(labels, values, color=colors, width=0.55)
            ax.bar_label(bars, fontsize=8, padding=2,
                         color="#f1f5f9" if dark else "#0f172a")
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels([l.replace("_", " ").title() for l in labels],
                               rotation=15, ha="right", fontsize=7)

        ax.set_title("Incidents by Status", fontsize=10, pad=8)
        fig.tight_layout(pad=1.5)
        self._embed(fig, row, col)

    def _chart_alerts_over_time(self, row, col, dark, accent):
        """Plot alerts per day over the last 14 days."""
        fig, ax = self._make_fig()
        _mpl_style(fig, ax, dark)

        now   = datetime.now(timezone.utc)
        days  = [(now - timedelta(days=i)).date() for i in range(13, -1, -1)]
        count = defaultdict(int)
        for a in self._alerts:
            try:
                dt = datetime.fromisoformat(
                    (a.get("created_at") or "").replace("Z", "+00:00"))
                count[dt.date()] += 1
            except Exception:
                pass

        x = list(range(len(days)))
        y = [count.get(d, 0) for d in days]
        labels = [d.strftime("%m/%d") for d in days]

        ax.fill_between(x, y, color=accent, alpha=0.25)
        ax.plot(x, y, color=accent, linewidth=2, marker="o", markersize=4)
        ax.set_xticks(x[::2])
        ax.set_xticklabels(labels[::2], rotation=20, ha="right", fontsize=7)
        ax.set_ylabel("Alerts", fontsize=8)
        ax.set_title("Alerts per Day (Last 14 Days)", fontsize=10, pad=8)
        ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
        fig.tight_layout(pad=1.5)
        self._embed(fig, row, col)
