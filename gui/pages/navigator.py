# gui/pages/navigator.py
"""
MITRE ATT&CK Navigator page.
Loads detection rules from mitre/rules.yaml and incident data from SQLite.
No hard-coded technique data.
"""
from __future__ import annotations
import sys
from pathlib import Path
from collections import defaultdict

import customtkinter as ctk

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gui import theme
from gui.widgets import SectionHeader, TechniqueChip, SeverityBadge, StatusBadge, Divider


# Full MITRE tactic → technique layout (mirrors the official ATT&CK matrix)
MITRE_MATRIX = [
    ("Initial Access",       ["T1078", "T1190", "T1566", "T1133"]),
    ("Execution",            ["T1059", "T1203", "T1106", "T1053"]),
    ("Persistence",          ["T1098", "T1136", "T1547", "T1543"]),
    ("Privilege Escalation", ["T1548", "T1068", "T1134", "T1548.001"]),
    ("Defense Evasion",      ["T1055", "T1070", "T1140", "T1036"]),
    ("Credential Access",    ["T1110", "T1003", "T1110.001", "T1110.003"]),
    ("Discovery",            ["T1046", "T1083", "T1057", "T1082"]),
    ("Lateral Movement",     ["T1021", "T1021.001", "T1021.002", "T1021.004"]),
    ("Collection",           ["T1005", "T1025", "T1074", "T1560"]),
    ("Exfiltration",         ["T1041", "T1048", "T1052", "T1567"]),
    ("Impact",               ["T1498", "T1486", "T1499", "T1485"]),
]


class NavigatorPage(ctk.CTkFrame):

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, fg_color=theme.get("surface_0"), corner_radius=0, **kwargs)
        self._app       = app
        self._incidents = []
        self._rules     = []
        self._selected_tech: str | None = None
        self._heat: dict[str, int] = {}
        self._cell_btns: dict[str, ctk.CTkButton] = {}

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_body()
        self._load()

    # ── Layout ──────────────────────────────────────────────────────────────────

    def _build_header(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 8))
        bar.grid_columnconfigure(0, weight=1)
        SectionHeader(bar, "MITRE ATT&CK Navigator").grid(row=0, column=0, sticky="w")

        self._sub = ctk.CTkLabel(bar, text="Loading…",
                                 font=theme.FONT_SMALL,
                                 text_color=theme.get("text_muted"))
        self._sub.grid(row=1, column=0, sticky="w")

        ctk.CTkButton(
            bar, text="⟳ Refresh",
            width=90, height=28, font=theme.FONT_SMALL,
            fg_color=theme.get("bg_accent"),
            text_color=theme.get("text_accent"),
            hover_color=theme.get("surface_hover"),
            corner_radius=6,
            command=self._load,
        ).grid(row=0, column=1, sticky="e")

    def _build_body(self):
        # Scrollable outer container
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 16))

    # ── Data ────────────────────────────────────────────────────────────────────

    def _load(self):
        from services.incident_service import list_incidents
        try:
            self._incidents = list_incidents(limit=500)
        except Exception as exc:
            print(f"[Navigator] incidents error: {exc}")
            self._incidents = []

        try:
            import yaml
            path = _ROOT / "mitre" / "rules.yaml"
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            self._rules = data.get("rules", []) if isinstance(data, dict) else []
        except Exception as exc:
            print(f"[Navigator] rules load error: {exc}")
            self._rules = []

        self._compute_heat()
        self._render()

    def refresh(self, data: dict):
        self._incidents = data.get("incidents", self._incidents)
        self._compute_heat()
        self._render()

    def _compute_heat(self):
        heat: dict[str, int] = defaultdict(int)
        for inc in self._incidents:
            tech = inc.get("technique") or ""
            if tech:
                heat[tech] += 1
                # also count parent (e.g. T1021.001 → T1021)
                parent = tech.split(".")[0]
                if parent != tech:
                    heat[parent] += 1
        self._heat = dict(heat)

    # ── Render ───────────────────────────────────────────────────────────────────

    def _render(self):
        for w in self._scroll.winfo_children():
            w.destroy()
        self._cell_btns.clear()

        total_incidents = len(self._incidents)
        rule_techs = {r.get("technique_id", "") for r in self._rules}
        self._sub.configure(
            text=f"{total_incidents} incidents · {len(self._rules)} detection rules · click cell to filter"
        )

        # Matrix grid
        matrix_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        matrix_frame.pack(fill="x", pady=(0, 20))

        max_rows = max((len(techs) for _, techs in MITRE_MATRIX), default=0)

        for ci, (tactic, techs) in enumerate(MITRE_MATRIX):
            col = ctk.CTkFrame(matrix_frame, fg_color="transparent")
            col.grid(row=0, column=ci, padx=3, sticky="n")
            matrix_frame.grid_columnconfigure(ci, weight=1)

            # Tactic header
            ctk.CTkLabel(
                col, text=tactic,
                font=theme.FONT_LABEL,
                text_color=theme.get("text_secondary"),
                wraplength=90,
                justify="center",
            ).pack(fill="x", pady=(0, 4))

            for tech in techs:
                count    = self._heat.get(tech, 0)
                has_rule = tech in rule_techs or any(
                    tech.startswith(r.split(".")[0]) for r in rule_techs if r
                )
                bg    = self._heat_color(count)
                fg    = theme.get("text_primary") if count > 0 else theme.get("text_muted")
                label = f"{tech}\n({count})" if count > 0 else tech

                btn = ctk.CTkButton(
                    col,
                    text=label,
                    font=theme.FONT_MONO_XS,
                    fg_color=bg,
                    text_color=fg,
                    hover_color=theme.get("surface_hover"),
                    border_width=1 if has_rule else 0,
                    border_color=theme.get("text_accent") if has_rule else "transparent",
                    corner_radius=5,
                    width=92, height=38,
                    command=lambda t=tech: self._select_tech(t),
                )
                btn.pack(pady=2)
                self._cell_btns[tech] = btn

        # Legend
        legend = ctk.CTkFrame(self._scroll, fg_color="transparent")
        legend.pack(fill="x", pady=(0, 16))
        for swatch, label in [
            (theme.get("surface_1"), "0 incidents"),
            ("#fef9c3", "1 incident"),
            ("#fed7aa", "2–3 incidents"),
            ("#fca5a5", "4+ incidents"),
        ]:
            s = ctk.CTkFrame(legend, fg_color=swatch, width=16, height=16,
                             corner_radius=3, border_width=1, border_color=theme.get("border"))
            s.pack(side="left", padx=(12, 4))
            ctk.CTkLabel(legend, text=label, font=theme.FONT_SMALL,
                         text_color=theme.get("text_secondary")).pack(side="left", padx=(0, 16))

        ctk.CTkLabel(legend, text="│ Blue border = detection rule exists",
                     font=theme.FONT_SMALL,
                     text_color=theme.get("text_accent")).pack(side="left")

        # Filtered incidents panel (shown when a cell is selected)
        if self._selected_tech:
            self._render_filtered()

    def _heat_color(self, count: int) -> str:
        if count == 0: return theme.get("surface_1")
        if count == 1: return "#fef9c3"
        if count <= 3: return "#fed7aa"
        return "#fca5a5"

    def _select_tech(self, tech: str):
        self._selected_tech = None if self._selected_tech == tech else tech
        # Highlight selected cell
        for t, btn in self._cell_btns.items():
            if t == self._selected_tech:
                btn.configure(border_width=2, border_color=theme.get("text_accent"))
            elif self._heat.get(t, 0) > 0:
                btn.configure(border_width=0)
        self._render_filtered_panel()

    def _render_filtered_panel(self):
        # Remove existing panel
        for w in self._scroll.winfo_children():
            if hasattr(w, "_is_filter_panel"):
                w.destroy()

        if not self._selected_tech:
            return
        self._render_filtered()

    def _render_filtered(self):
        tech = self._selected_tech
        matching = [i for i in self._incidents
                    if i.get("technique") == tech
                    or (i.get("technique") or "").startswith(tech + ".")]

        # Find matching rule
        rule = next((r for r in self._rules
                     if (r.get("technique_id") or "").startswith(tech)), None)

        panel = ctk.CTkFrame(
            self._scroll,
            fg_color=theme.get("surface_1"),
            corner_radius=10,
            border_width=1,
            border_color=theme.get("border_strong"),
        )
        panel._is_filter_panel = True  # tag for removal
        panel.pack(fill="x", pady=(0, 16))

        hdr = ctk.CTkFrame(panel, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(12, 8))

        TechniqueChip(hdr, tech).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(hdr, text=f"{len(matching)} incident(s)",
                     font=theme.FONT_BODY,
                     text_color=theme.get("text_primary")).pack(side="left")
        ctk.CTkButton(
            hdr, text="✕ Clear", width=70, height=26,
            font=theme.FONT_SMALL,
            fg_color="transparent",
            text_color=theme.get("text_muted"),
            hover_color=theme.get("surface_hover"),
            corner_radius=6,
            command=lambda: self._select_tech(tech),
        ).pack(side="right")

        if rule:
            rule_frame = ctk.CTkFrame(panel, fg_color=theme.get("surface_0"),
                                      corner_radius=6, border_width=1,
                                      border_color=theme.get("border"))
            rule_frame.pack(fill="x", padx=16, pady=(0, 10))
            ctk.CTkLabel(rule_frame,
                         text=f"📋 Rule: {rule.get('name','?')}  ·  {rule.get('tactic','?')}",
                         font=theme.FONT_SMALL,
                         text_color=theme.get("text_accent"),
                         anchor="w").pack(fill="x", padx=10, pady=(6, 2))
            ctk.CTkLabel(rule_frame,
                         text=f"Condition: {rule.get('condition','?')}",
                         font=theme.FONT_MONO_XS,
                         text_color=theme.get("text_secondary"),
                         anchor="w",
                         wraplength=700).pack(fill="x", padx=10, pady=(0, 6))

        if not matching:
            ctk.CTkLabel(panel, text="No incidents for this technique.",
                         font=theme.FONT_BODY,
                         text_color=theme.get("text_muted")).pack(pady=12)
        else:
            for inc in matching[:20]:
                row = ctk.CTkFrame(panel, fg_color=theme.get("surface_0"),
                                   corner_radius=6)
                row.pack(fill="x", padx=16, pady=3)
                rf = ctk.CTkFrame(row, fg_color="transparent")
                rf.pack(fill="x", padx=10, pady=6)
                SeverityBadge(rf, inc.get("severity","low")).pack(side="left", padx=(0,8))
                ctk.CTkLabel(rf, text=inc.get("entity","?"),
                             font=theme.FONT_BODY,
                             text_color=theme.get("text_primary")).pack(side="left")
                StatusBadge(rf, inc.get("status","open")).pack(side="right")
