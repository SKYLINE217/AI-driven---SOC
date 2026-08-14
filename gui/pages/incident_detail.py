# gui/pages/incident_detail.py
"""
Incident detail side panel.
Tabs: Overview | Alerts | Playbook | Audit Ledger
Data: services.incident_service.get_incident()
Playbook: artifacts.playbook_renderer.render_playbook()
"""
from __future__ import annotations
import sys
import tkinter as tk
from pathlib import Path

import customtkinter as ctk

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gui import theme
from gui.widgets import (
    SeverityBadge, StatusBadge, TechniqueChip, ScoreBar, Divider
)

TABS = ["Overview", "Alerts", "Playbook", "Audit Ledger"]


class IncidentDetailPanel(ctk.CTkFrame):
    """Slide-in detail panel for a single incident."""

    def __init__(self, parent, incident_id: str, on_close: callable, **kwargs):
        super().__init__(
            parent,
            fg_color=theme.get("surface_0"),
            border_width=1,
            border_color=theme.get("border_strong"),
            corner_radius=0,
            **kwargs,
        )
        self._id       = incident_id
        self._on_close = on_close
        self._incident = None
        self._tab      = "Overview"

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_tabs()

        self._body = ctk.CTkFrame(self, fg_color="transparent")
        self._body.grid(row=2, column=0, sticky="nsew")
        self._body.grid_rowconfigure(0, weight=1)
        self._body.grid_columnconfigure(0, weight=1)

        self._load()

    # ── Layout ─────────────────────────────────────────────────────────────────

    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color=theme.get("surface_1"), corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hdr, text="Incident Details",
            font=theme.FONT_SUBHEAD,
            text_color=theme.get("text_primary"),
            anchor="w",
        ).grid(row=0, column=0, padx=16, pady=10, sticky="w")

        ctk.CTkButton(
            hdr, text="✕", width=28, height=28,
            fg_color="transparent",
            text_color=theme.get("text_muted"),
            hover_color=theme.get("surface_hover"),
            corner_radius=6,
            command=self._on_close,
        ).grid(row=0, column=1, padx=10, pady=8, sticky="e")

    def _build_tabs(self):
        bar = ctk.CTkFrame(self, fg_color=theme.get("surface_1"), height=40, corner_radius=0)
        bar.grid(row=1, column=0, sticky="ew")
        self._tab_btns: dict[str, ctk.CTkButton] = {}
        for i, tab in enumerate(TABS):
            btn = ctk.CTkButton(
                bar, text=tab, height=32,
                font=theme.FONT_SMALL,
                fg_color="transparent",
                text_color=theme.get("text_secondary"),
                hover_color=theme.get("surface_hover"),
                corner_radius=6,
                command=lambda t=tab: self._switch(t),
            )
            btn.grid(row=0, column=i, padx=(6 if i == 0 else 2, 2), pady=4)
            self._tab_btns[tab] = btn
        self._highlight_tab("Overview")

    def _highlight_tab(self, active: str):
        for tab, btn in self._tab_btns.items():
            if tab == active:
                btn.configure(fg_color=theme.get("bg_accent"),
                              text_color=theme.get("text_accent"))
            else:
                btn.configure(fg_color="transparent",
                              text_color=theme.get("text_secondary"))

    # ── Data ───────────────────────────────────────────────────────────────────

    def _load(self):
        from services.incident_service import get_incident
        try:
            self._incident = get_incident(self._id)
        except Exception as exc:
            print(f"[IncidentDetail] load error: {exc}")
            self._incident = None
        self._render()

    def _switch(self, tab: str):
        self._tab = tab
        self._highlight_tab(tab)
        self._render()

    def _render(self):
        for w in self._body.winfo_children():
            w.destroy()
        if not self._incident:
            ctk.CTkLabel(self._body, text="Incident not found.",
                         font=theme.FONT_BODY,
                         text_color=theme.get("text_muted")).grid(pady=32)
            return
        dispatch = {
            "Overview":    self._tab_overview,
            "Alerts":      self._tab_alerts,
            "Playbook":    self._tab_playbook,
            "Audit Ledger":self._tab_ledger,
        }
        dispatch.get(self._tab, self._tab_overview)()

    # ── Tab: Overview ──────────────────────────────────────────────────────────

    def _tab_overview(self):
        inc  = self._incident
        body = ctk.CTkScrollableFrame(self._body, fg_color="transparent")
        body.grid(row=0, column=0, sticky="nsew")
        self._body.grid_rowconfigure(0, weight=1)

        # Badges
        badge_row = ctk.CTkFrame(body, fg_color="transparent")
        badge_row.pack(fill="x", padx=16, pady=(12, 8))
        SeverityBadge(badge_row, inc.get("severity", "low")).pack(side="left", padx=(0, 6))
        StatusBadge(badge_row, inc.get("status", "open")).pack(side="left", padx=(0, 6))
        TechniqueChip(badge_row, inc.get("technique", "?"), inc.get("tactic", "")).pack(side="left")

        Divider(body).pack(fill="x", padx=16, pady=6)

        # Key-value grid
        kv = ctk.CTkFrame(body, fg_color="transparent")
        kv.pack(fill="x", padx=16, pady=4)
        kv.grid_columnconfigure(1, weight=1)
        rows = [
            ("Entity",     inc.get("entity", "?")),
            ("Tactic",     inc.get("tactic", "—")),
            ("Confidence", f"{float(inc.get('confidence', 0) or 0):.1%}"),
            ("Created",    str(inc.get("created_at", ""))[:19].replace("T", " ")),
            ("Updated",    str(inc.get("updated_at", ""))[:19].replace("T", " ")),
        ]
        for ri, (k, v) in enumerate(rows):
            ctk.CTkLabel(kv, text=k + ":", font=theme.FONT_LABEL,
                         text_color=theme.get("text_secondary"),
                         anchor="w", width=90).grid(row=ri, column=0, padx=(0, 8), pady=3, sticky="w")
            ctk.CTkLabel(kv, text=v, font=theme.FONT_BODY,
                         text_color=theme.get("text_primary"),
                         anchor="w", wraplength=360).grid(row=ri, column=1, pady=3, sticky="w")

        Divider(body).pack(fill="x", padx=16, pady=8)

        # Score bar
        sf = ctk.CTkFrame(body, fg_color="transparent")
        sf.pack(fill="x", padx=16, pady=(0, 8))
        ctk.CTkLabel(sf, text="Anomaly Score:", font=theme.FONT_LABEL,
                     text_color=theme.get("text_secondary")).pack(side="left", padx=(0, 8))
        ScoreBar(sf, float(inc.get("confidence", 0) or 0)).pack(side="left")

        Divider(body).pack(fill="x", padx=16, pady=6)

        # Rationale
        if inc.get("rationale"):
            ctk.CTkLabel(body, text="Rationale", font=theme.FONT_LABEL,
                         text_color=theme.get("text_secondary"), anchor="w").pack(fill="x", padx=16, pady=(4, 2))
            ctk.CTkLabel(body, text=inc["rationale"], font=theme.FONT_BODY,
                         text_color=theme.get("text_primary"),
                         anchor="w", justify="left", wraplength=500).pack(fill="x", padx=16, pady=(0, 10))
            Divider(body).pack(fill="x", padx=16, pady=6)

        # Status update buttons
        ctk.CTkLabel(body, text="Update Status", font=theme.FONT_LABEL,
                     text_color=theme.get("text_secondary"), anchor="w").pack(fill="x", padx=16, pady=(6, 4))
        bf = ctk.CTkFrame(body, fg_color="transparent")
        bf.pack(fill="x", padx=16, pady=(0, 16))
        for st in ["investigating", "resolved", "false_positive"]:
            ctk.CTkButton(
                bf, text=st.replace("_", " ").title(),
                height=30, font=theme.FONT_SMALL,
                fg_color=theme.get("surface_1"),
                text_color=theme.get("text_primary"),
                hover_color=theme.get("surface_hover"),
                border_width=1, border_color=theme.get("border"),
                corner_radius=6,
                command=lambda s=st: self._update_status(s),
            ).pack(side="left", padx=(0, 6))

    def _update_status(self, new_status: str):
        from services.incident_service import update_status
        try:
            updated = update_status(self._id, new_status, actor="analyst")
            if updated:
                self._incident = updated
                self._render()
        except Exception as exc:
            print(f"[IncidentDetail] status update error: {exc}")

    # ── Tab: Alerts ────────────────────────────────────────────────────────────

    def _tab_alerts(self):
        alerts = self._incident.get("alerts", [])
        body   = ctk.CTkScrollableFrame(self._body, fg_color="transparent")
        body.grid(row=0, column=0, sticky="nsew")
        self._body.grid_rowconfigure(0, weight=1)

        ctk.CTkLabel(body, text=f"{len(alerts)} linked alert(s)",
                     font=theme.FONT_SUBHEAD, text_color=theme.get("text_primary"),
                     anchor="w").pack(fill="x", padx=16, pady=(12, 8))

        if not alerts:
            ctk.CTkLabel(body, text="No alerts for this incident.",
                         font=theme.FONT_BODY, text_color=theme.get("text_muted")).pack(pady=16)
            return

        for a in alerts:
            card = ctk.CTkFrame(body, fg_color=theme.get("surface_1"),
                                corner_radius=8, border_width=1,
                                border_color=theme.get("border"))
            card.pack(fill="x", padx=16, pady=4)

            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=12, pady=(8, 4))
            SeverityBadge(top, a.get("severity", "low")).pack(side="left", padx=(0, 8))
            StatusBadge(top, a.get("status", "new")).pack(side="left", padx=(0, 8))
            ctk.CTkLabel(top,
                         text=str(a.get("created_at", ""))[:16].replace("T", " "),
                         font=theme.FONT_SMALL,
                         text_color=theme.get("text_muted")).pack(side="right")

            ctk.CTkLabel(card,
                         text=f"Source: {a.get('source_type', '?')}   Score: {float(a.get('anomaly_score', 0) or 0):.3f}",
                         font=theme.FONT_SMALL,
                         text_color=theme.get("text_secondary"),
                         anchor="w").pack(fill="x", padx=12, pady=(0, 8))

    # ── Tab: Playbook ──────────────────────────────────────────────────────────

    def _tab_playbook(self):
        body = ctk.CTkScrollableFrame(self._body, fg_color="transparent")
        body.grid(row=0, column=0, sticky="nsew")
        self._body.grid_rowconfigure(0, weight=1)

        # Try the real playbook renderer first
        yaml_text = self._get_playbook_yaml()

        # Header
        hdr = ctk.CTkFrame(body, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(12, 8))
        ctk.CTkLabel(hdr, text="Containment Playbook — DRAFT",
                     font=theme.FONT_SUBHEAD,
                     text_color=theme.get("text_primary")).pack(side="left")
        ctk.CTkButton(
            hdr, text="📋 Copy", width=80, height=28,
            font=theme.FONT_SMALL,
            fg_color=theme.get("surface_1"),
            text_color=theme.get("text_primary"),
            hover_color=theme.get("surface_hover"),
            border_width=1, border_color=theme.get("border"),
            corner_radius=6,
            command=lambda: self._copy_to_clipboard(yaml_text),
        ).pack(side="right")

        # Warning box
        warn = ctk.CTkFrame(body, fg_color="#fff7ed",
                            corner_radius=6, border_width=1,
                            border_color="#fdba74")
        warn.pack(fill="x", padx=16, pady=(0, 10))
        ctk.CTkLabel(warn,
                     text="⚠ DRAFT ONLY — Requires Approver authorization before execution.",
                     font=theme.FONT_SMALL,
                     text_color="#9a3412",
                     anchor="w").pack(padx=10, pady=6)

        # YAML code block
        code_frame = ctk.CTkFrame(body, fg_color=theme.get("surface_1"),
                                  corner_radius=8, border_width=1,
                                  border_color=theme.get("border"))
        code_frame.pack(fill="x", padx=16, pady=(0, 16))

        txt = tk.Text(
            code_frame,
            font=theme.FONT_MONO_SM,
            bg=theme.get("surface_1"),
            fg=theme.get("text_primary"),
            insertbackground=theme.get("text_primary"),
            relief="flat", bd=0,
            wrap="none",
            height=28,
        )
        txt.insert("1.0", yaml_text)
        txt.configure(state="disabled")
        txt.pack(fill="both", expand=True, padx=8, pady=8)

    def _get_playbook_yaml(self) -> str:
        inc = self._incident
        try:
            from artifacts.playbook_renderer import render_playbook
            return render_playbook(inc)
        except Exception as exc:
            # Graceful fallback if templates are missing
            return (
                f"# Fallback playbook (renderer error: {exc})\n"
                f"# Incident: {inc.get('id', '?')}\n"
                f"# Entity:   {inc.get('entity', '?')}\n"
                f"# Tech:     {inc.get('technique', '?')}\n"
                f"# Severity: {inc.get('severity', '?')}\n\n"
                f"- name: Contain incident {inc.get('id', '')[:8]}\n"
                f"  hosts: '{inc.get('entity', 'unknown')}'\n"
                f"  tasks:\n"
                f"    - name: Isolate host\n"
                f"      command: echo 'isolation placeholder'\n"
            )

    def _copy_to_clipboard(self, text: str):
        self.clipboard_clear()
        self.clipboard_append(text)

    # ── Tab: Audit Ledger ──────────────────────────────────────────────────────

    def _tab_ledger(self):
        ledger = self._incident.get("ledger", [])
        body   = ctk.CTkScrollableFrame(self._body, fg_color="transparent")
        body.grid(row=0, column=0, sticky="nsew")
        self._body.grid_rowconfigure(0, weight=1)

        hdr = ctk.CTkFrame(body, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(12, 8))
        ctk.CTkLabel(hdr, text="Audit Ledger",
                     font=theme.FONT_SUBHEAD, text_color=theme.get("text_primary")).pack(side="left")
        ctk.CTkLabel(hdr,
                     text=f"{len(ledger)} entries · SHA-256 hash-chained",
                     font=theme.FONT_SMALL,
                     text_color=theme.get("text_muted")).pack(side="left", padx=8)

        if not ledger:
            ctk.CTkLabel(body, text="No ledger entries.",
                         font=theme.FONT_BODY, text_color=theme.get("text_muted")).pack(pady=16)
            return

        for e in ledger:
            ok = e.get("valid", True) is not False
            card = ctk.CTkFrame(body,
                                fg_color=theme.get("surface_1"),
                                corner_radius=8,
                                border_width=1,
                                border_color=("#86efac" if ok else "#fca5a5"))
            card.pack(fill="x", padx=16, pady=3)

            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=6)

            valid_icon = "✓" if ok else "✗"
            valid_col  = theme.get("text_success") if ok else theme.get("text_danger")

            ctk.CTkLabel(row, text=valid_icon, font=(theme.FONT_FAMILY, 16, "bold"),
                         text_color=valid_col, width=24).pack(side="left", padx=(0, 8))
            ctk.CTkLabel(row,
                         text=f"#{e.get('id', '?')}  {e.get('action', '?')}",
                         font=theme.FONT_BODY,
                         text_color=theme.get("text_primary")).pack(side="left")
            ctk.CTkLabel(row,
                         text=str(e.get("timestamp", ""))[:19].replace("T", " "),
                         font=theme.FONT_SMALL,
                         text_color=theme.get("text_muted")).pack(side="right")

            ctk.CTkLabel(card,
                         text=f"Actor: {e.get('actor', '?')}   Hash: {str(e.get('this_hash', ''))[:16]}…",
                         font=theme.FONT_MONO_XS,
                         text_color=theme.get("text_muted"),
                         anchor="w").pack(fill="x", padx=12, pady=(0, 6))
