# gui/sidebar.py
from __future__ import annotations
import customtkinter as ctk
from gui import theme

NAV_ITEMS = [
    ("alerts",    "🔔", "Alert Queue"),
    ("navigator", "🗺", "MITRE ATT&CK"),
    ("ops",       "📊", "Ops Metrics"),
    ("playbooks", "📖", "Playbooks"),
    ("settings",  "⚙", "Settings"),
]

SIDEBAR_W  = 210
SIDEBAR_COLLAPSED = 52


class Sidebar(ctk.CTkFrame):
    """Collapsible left navigation panel."""

    def __init__(self, parent, navigate_fn, **kwargs):
        super().__init__(
            parent,
            width=SIDEBAR_W,
            corner_radius=0,
            fg_color=theme.get("surface_1"),
            **kwargs,
        )
        self.grid_propagate(False)
        self._navigate = navigate_fn
        self._active   = ""
        self._collapsed = False
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._badge: ctk.CTkLabel | None = None
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(98, weight=1)   # spacer pushes collapse btn down

        # Logo
        self._logo = ctk.CTkLabel(
            self, text="🛡 SOC Triager",
            font=theme.FONT_SUBHEAD,
            text_color=theme.get("text_accent"),
            anchor="w",
        )
        self._logo.grid(row=0, column=0, padx=14, pady=(18, 14), sticky="w")

        ctk.CTkFrame(self, height=1, fg_color=theme.get("border")).grid(
            row=1, column=0, sticky="ew", padx=0, pady=0)

        # Navigation buttons
        for ri, (key, icon, label) in enumerate(NAV_ITEMS, start=2):
            btn = ctk.CTkButton(
                self,
                text=f"  {icon}  {label}",
                anchor="w",
                font=theme.FONT_BODY,
                fg_color="transparent",
                text_color=theme.get("text_secondary"),
                hover_color=theme.get("surface_hover"),
                corner_radius=8,
                height=38,
                command=lambda k=key: self._navigate(k),
            )
            btn.grid(row=ri, column=0, padx=8, pady=2, sticky="ew")
            self._buttons[key] = btn

            # Alert badge (placed via .place() on top of alerts button)
            if key == "alerts":
                self._badge = ctk.CTkLabel(
                    self, text="",
                    font=(theme.FONT_FAMILY, 10, "bold"),
                    text_color="white",
                    fg_color="#ef4444",
                    corner_radius=9,
                    width=22, height=18,
                )

        # Bottom area: divider + theme toggle + collapse
        ctk.CTkFrame(self, height=1, fg_color=theme.get("border")).grid(
            row=96, column=0, sticky="ew", padx=0, pady=8)

        # Dark/Light toggle
        self._theme_switch = ctk.CTkSwitch(
            self,
            text="Dark mode",
            font=theme.FONT_SMALL,
            text_color=theme.get("text_secondary"),
            command=self._toggle_theme,
            onvalue="Dark",
            offvalue="Light",
        )
        self._theme_switch.grid(row=97, column=0, padx=14, pady=(0, 4), sticky="w")
        if ctk.get_appearance_mode() == "Dark":
            self._theme_switch.select()

        # Collapse toggle
        self._collapse_btn = ctk.CTkButton(
            self, text="◀",
            width=32, height=32,
            fg_color="transparent",
            text_color=theme.get("text_muted"),
            hover_color=theme.get("surface_hover"),
            corner_radius=6,
            command=self._toggle_collapse,
        )
        self._collapse_btn.grid(row=99, column=0, padx=8, pady=(0, 10), sticky="sw")

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_active(self, key: str):
        for k, btn in self._buttons.items():
            if k == key:
                btn.configure(
                    fg_color=theme.get("bg_accent"),
                    text_color=theme.get("text_accent"),
                    font=(theme.FONT_FAMILY, 13, "bold"),
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=theme.get("text_secondary"),
                    font=theme.FONT_BODY,
                )
        self._active = key

    def set_alert_count(self, count: int):
        if self._badge is None:
            return
        if count > 0:
            self._badge.configure(text=str(min(count, 99)))
            self._badge.place(
                in_=self._buttons["alerts"],
                relx=1.0, rely=0.5, anchor="e", x=-6,
            )
        else:
            self._badge.place_forget()

    # ── Internal ───────────────────────────────────────────────────────────────

    def _toggle_theme(self):
        new_mode = self._theme_switch.get()
        ctk.set_appearance_mode(new_mode)

    def _toggle_collapse(self):
        self._collapsed = not self._collapsed
        w = SIDEBAR_COLLAPSED if self._collapsed else SIDEBAR_W
        self.configure(width=w)
        for key, btn in self._buttons.items():
            icon = next(i for k, i, _ in NAV_ITEMS if k == key)
            if self._collapsed:
                btn.configure(text=f" {icon}", anchor="center")
            else:
                label = next(l for k, _, l in NAV_ITEMS if k == key)
                btn.configure(text=f"  {icon}  {label}", anchor="w")
        self._collapse_btn.configure(text="▶" if self._collapsed else "◀")
        self._logo.configure(text="🛡" if self._collapsed else "🛡 SOC Triager")
        self._theme_switch.grid_remove() if self._collapsed else self._theme_switch.grid()
