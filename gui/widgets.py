# gui/widgets.py
"""
Reusable atomic widgets used across all pages.
Each widget class mirrors a component from the original React dashboard.
No page-specific logic lives here.
"""
from __future__ import annotations
import customtkinter as ctk
from gui import theme


# ── SeverityBadge ─────────────────────────────────────────────────────────────

class SeverityBadge(ctk.CTkLabel):
    """Coloured pill for a severity level (critical/high/medium/low)."""

    DOTS = {"critical": "⬤", "high": "⬤", "medium": "⬤", "low": "⬤"}

    def __init__(self, parent, severity: str, **kwargs):
        sev  = (severity or "low").lower()
        text = f"{self.DOTS.get(sev, '●')} {sev.capitalize()}"
        super().__init__(
            parent,
            text=text,
            text_color=theme.sev_color(sev),
            fg_color=theme.sev_bg(sev),
            corner_radius=10,
            font=theme.FONT_LABEL,
            **{"padx": 8, "pady": 2, **kwargs},
        )


# ── StatusBadge ───────────────────────────────────────────────────────────────

class StatusBadge(ctk.CTkLabel):
    """Status pill for incident/alert status."""

    LABELS = {
        "open": "Open",
        "investigating": "Investigating",
        "resolved": "Resolved",
        "false_positive": "False Positive",
        "new": "New",
        "ack": "Acknowledged",
        "escalated": "Escalated",
        "closed": "Closed",
    }

    def __init__(self, parent, status: str, **kwargs):
        st    = (status or "open").lower()
        label = self.LABELS.get(st, st.replace("_", " ").title())
        super().__init__(
            parent,
            text=label,
            text_color=theme.status_color(st),
            fg_color=theme.get("surface_1"),
            corner_radius=8,
            font=theme.FONT_SMALL,
            **{"padx": 6, "pady": 2, **kwargs},
        )


# ── ScoreBar ──────────────────────────────────────────────────────────────────

class ScoreBar(ctk.CTkFrame):
    """Horizontal progress bar for anomaly scores 0.0–1.0."""

    def __init__(self, parent, score: float, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        score = max(0.0, min(1.0, float(score or 0.0)))
        if score >= 0.75:
            color = theme.get("sev_critical")
        elif score >= 0.50:
            color = theme.get("sev_high")
        elif score >= 0.25:
            color = theme.get("sev_medium")
        else:
            color = theme.get("sev_low")

        bar = ctk.CTkProgressBar(
            self, width=80, height=7, corner_radius=4,
            fg_color=theme.get("border"),
            progress_color=color,
        )
        bar.set(score)
        bar.pack(side="left", padx=(0, 5))

        ctk.CTkLabel(
            self, text=f"{score:.2f}",
            font=theme.FONT_SMALL,
            text_color=theme.get("text_muted"),
        ).pack(side="left")


# ── TechniqueChip ─────────────────────────────────────────────────────────────

class TechniqueChip(ctk.CTkLabel):
    """MITRE technique ID chip (e.g. T1110.001)."""

    def __init__(self, parent, technique_id: str, tactic: str = "", **kwargs):
        super().__init__(
            parent,
            text=technique_id or "–",
            text_color=theme.get("text_accent"),
            fg_color=theme.get("bg_accent"),
            corner_radius=6,
            font=theme.FONT_MONO_SM,
            **{"padx": 6, "pady": 2, **kwargs},
        )


# ── Divider ───────────────────────────────────────────────────────────────────

class Divider(ctk.CTkFrame):
    """1-pixel horizontal rule."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, height=1, fg_color=theme.get("border"), **kwargs)


# ── SectionHeader ─────────────────────────────────────────────────────────────

class SectionHeader(ctk.CTkLabel):
    """Page-level heading."""

    def __init__(self, parent, text: str, **kwargs):
        super().__init__(
            parent, text=text,
            font=theme.FONT_HEADING,
            text_color=theme.get("text_primary"),
            anchor="w",
            **kwargs,
        )


# ── StatCard ──────────────────────────────────────────────────────────────────

class StatCard(ctk.CTkFrame):
    """Small metric card with a big number and a label below."""

    def __init__(self, parent, value: str, label: str, color: str | None = None, **kwargs):
        super().__init__(
            parent,
            fg_color=theme.get("surface_2"),
            corner_radius=10,
            border_width=1,
            border_color=theme.get("border"),
            **kwargs,
        )
        ctk.CTkLabel(
            self, text=str(value),
            font=(theme.FONT_FAMILY, 26, "bold"),
            text_color=color or theme.get("text_primary"),
        ).pack(padx=16, pady=(14, 2))
        ctk.CTkLabel(
            self, text=label,
            font=theme.FONT_SMALL,
            text_color=theme.get("text_muted"),
        ).pack(padx=16, pady=(0, 14))


# ── ScrollableTable ───────────────────────────────────────────────────────────

class ScrollableTable(ctk.CTkScrollableFrame):
    """
    Scrollable table with column headers.
    columns: list of (header_text, min_width_px)
    """

    ROW_BG_ALT = None   # set in __init__ after theme is available

    def __init__(self, parent, columns: list[tuple[str, int]], **kwargs):
        super().__init__(
            parent,
            fg_color=theme.get("surface_2"),
            scrollbar_button_color=theme.get("border"),
            **kwargs,
        )
        self._columns = columns
        self._ncols = len(columns)
        self._row_count = 0

        for ci, (header, mw) in enumerate(columns):
            self.grid_columnconfigure(ci, minsize=mw, weight=1 if ci == 2 else 0)
            ctk.CTkLabel(
                self, text=header.upper(),
                font=theme.FONT_LABEL,
                text_color=theme.get("text_muted"),
                fg_color=theme.get("surface_1"),
                anchor="w",
            ).grid(row=0, column=ci, padx=(10, 4), pady=(8, 6), sticky="ew")

        Divider(self).grid(row=1, column=0, columnspan=self._ncols, sticky="ew", padx=0)
        self._data_row = 2

    def clear_rows(self):
        for widget in self.winfo_children():
            info = widget.grid_info()
            if info and int(info.get("row", 0)) >= self._data_row:
                widget.destroy()
        self._row_count = 0

    def add_row(self, cells: list, on_click=None, bg: str | None = None):
        """
        cells: list of str | callable(parent)->widget
        on_click: optional zero-arg function called when row is clicked
        """
        row_idx = self._data_row + self._row_count * 2
        row_bg  = bg or (theme.get("surface_1") if self._row_count % 2 else theme.get("surface_2"))

        widgets_in_row = []
        for ci, cell in enumerate(cells):
            if callable(cell):
                w = cell(self)
            else:
                w = ctk.CTkLabel(
                    self, text=str(cell),
                    font=theme.FONT_BODY,
                    text_color=theme.get("text_primary"),
                    fg_color=row_bg,
                    anchor="w",
                )
            w.grid(row=row_idx, column=ci, padx=(10, 4), pady=5, sticky="ew")
            widgets_in_row.append(w)

        # Hover + click binding
        if on_click:
            def _bind_hover(wlist, fn):
                hover_bg = theme.get("surface_hover")
                for w in wlist:
                    try:
                        orig = w.cget("fg_color")
                    except Exception:
                        orig = row_bg
                    w.bind("<Enter>",    lambda e, _w=w, _b=hover_bg: _w.configure(fg_color=_b))
                    w.bind("<Leave>",    lambda e, _w=w, _b=orig:     _w.configure(fg_color=_b))
                    w.bind("<Button-1>", lambda e, _f=fn: _f())
                    try:
                        w.configure(cursor="hand2")
                    except Exception:
                        pass
            _bind_hover(widgets_in_row, on_click)

        # Row separator
        Divider(self).grid(row=row_idx + 1, column=0,
                           columnspan=self._ncols, sticky="ew", padx=0)
        self._row_count += 1
