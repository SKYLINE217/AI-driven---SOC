# gui/pages/playbook_library.py
"""
Playbook Library page.
Reads available playbook templates from artifacts/playbook_templates/
and displays them as a card grid — no hard-coded playbook data.
"""
from __future__ import annotations
import sys
from pathlib import Path

import customtkinter as ctk

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gui import theme
from gui.widgets import SectionHeader, TechniqueChip, Divider
from artifacts.playbook_renderer import TECHNIQUE_TEMPLATE_MAP

# Human-readable name for each technique prefix
TECH_NAMES: dict[str, tuple[str, str]] = {
    "T1110": ("Credential Access",    "Brute Force Response"),
    "T1021": ("Lateral Movement",     "Lateral Movement Containment"),
    "T1498": ("Impact",               "DDoS Mitigation"),
    "T1548": ("Privilege Escalation", "Privilege Escalation Response"),
    "T1041": ("Exfiltration",         "Exfiltration Egress Block"),
    "T1046": ("Discovery",            "Port Scan Block"),
    "T1055": ("Defense Evasion",      "Process Injection Isolation"),
    "T1078": ("Initial Access",       "Impossible Travel Lockout"),
    "T1059": ("Execution",            "Scripting Interpreter Block"),
}

SEV_COLORS = {
    "Credential Access":    "#fef2f2",
    "Lateral Movement":     "#eff6ff",
    "Impact":               "#fef2f2",
    "Privilege Escalation": "#fff7ed",
    "Exfiltration":         "#fef2f2",
    "Discovery":            "#f0fdf4",
    "Defense Evasion":      "#fefce8",
    "Initial Access":       "#fff7ed",
    "Execution":            "#fefce8",
}


class PlaybookLibraryPage(ctk.CTkFrame):

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, fg_color=theme.get("surface_0"), corner_radius=0, **kwargs)
        self._app = app

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_grid()

    def _build_header(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 8))
        bar.grid_columnconfigure(0, weight=1)
        SectionHeader(bar, "Playbook Library").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            bar,
            text=f"{len(TECHNIQUE_TEMPLATE_MAP)} Jinja2 templates loaded from artifacts/playbook_templates/",
            font=theme.FONT_SMALL,
            text_color=theme.get("text_muted"),
        ).grid(row=1, column=0, sticky="w")

    def _build_grid(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 16))

        # Build one card per technique
        cards_per_row = 3
        for idx, (tech_prefix, template_file) in enumerate(TECHNIQUE_TEMPLATE_MAP.items()):
            tactic, name = TECH_NAMES.get(tech_prefix, ("Unknown", tech_prefix))
            bg_color     = SEV_COLORS.get(tactic, theme.get("surface_1"))
            card_row = idx // cards_per_row
            card_col = idx % cards_per_row

            scroll.grid_columnconfigure(card_col, weight=1)
            self._make_card(scroll, tech_prefix, tactic, name,
                            template_file, bg_color, card_row, card_col)

    def _make_card(self, parent, tech: str, tactic: str, name: str,
                   template_file: str, bg: str, row: int, col: int):
        card = ctk.CTkFrame(
            parent,
            fg_color=theme.get("surface_1"),
            corner_radius=10,
            border_width=1,
            border_color=theme.get("border"),
        )
        card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

        # Colour accent strip
        strip = ctk.CTkFrame(card, fg_color=bg, height=4, corner_radius=0)
        strip.pack(fill="x")

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=14, pady=12)

        # Header
        hdr = ctk.CTkFrame(body, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 8))
        TechniqueChip(hdr, tech).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(hdr, text=tactic, font=theme.FONT_SMALL,
                     text_color=theme.get("text_muted")).pack(side="left")

        ctk.CTkLabel(body, text=name,
                     font=theme.FONT_SUBHEAD,
                     text_color=theme.get("text_primary"),
                     anchor="w", wraplength=220).pack(fill="x", pady=(0, 8))

        Divider(body).pack(fill="x", pady=6)

        ctk.CTkLabel(body, text=f"Template: {template_file}",
                     font=theme.FONT_MONO_XS,
                     text_color=theme.get("text_muted"),
                     anchor="w").pack(fill="x", pady=(0, 4))

        # Preview button
        ctk.CTkButton(
            body, text="Preview Template",
            height=28, font=theme.FONT_SMALL,
            fg_color=theme.get("bg_accent"),
            text_color=theme.get("text_accent"),
            hover_color=theme.get("surface_hover"),
            corner_radius=6,
            command=lambda t=tech, n=name: self._preview(t, n),
        ).pack(fill="x", pady=(6, 0))

    def _preview(self, tech: str, name: str):
        """Open a popup showing the raw template content."""
        import tkinter as tk
        from artifacts.playbook_renderer import TEMPLATES_DIR, _get_template_name
        try:
            template_name = _get_template_name(tech)
            template_path = TEMPLATES_DIR / template_name
            content = template_path.read_text(encoding="utf-8")
        except Exception as exc:
            content = f"# Template file not found\n# Error: {exc}"

        popup = ctk.CTkToplevel(self)
        popup.title(f"Template — {name}")
        popup.geometry("700x550")
        popup.grab_set()

        ctk.CTkLabel(popup, text=f"{name}  ·  {tech}",
                     font=theme.FONT_SUBHEAD,
                     text_color=theme.get("text_primary")).pack(
            padx=16, pady=(14, 8), anchor="w")

        txt_frame = ctk.CTkFrame(popup, fg_color=theme.get("surface_1"),
                                 corner_radius=8)
        txt_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        txt = tk.Text(
            txt_frame,
            font=theme.FONT_MONO_SM,
            bg=theme.get("surface_1"),
            fg=theme.get("text_primary"),
            insertbackground=theme.get("text_primary"),
            relief="flat", bd=0,
            wrap="none",
        )
        sb = tk.Scrollbar(txt_frame, command=txt.yview, bg=theme.get("surface_1"))
        txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        txt.insert("1.0", content)
        txt.configure(state="disabled")

    def refresh(self, data: dict):
        pass  # Playbook library is static (template files don't change at runtime)
