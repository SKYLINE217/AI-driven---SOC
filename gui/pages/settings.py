# gui/pages/settings.py
"""
Settings page.
Reads real values from config.py and displays them.
Allows overriding key settings via environment variables for this session.
"""
from __future__ import annotations
import sys
import os
from pathlib import Path

import customtkinter as ctk

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gui import theme
from gui.widgets import SectionHeader, Divider


class SettingsPage(ctk.CTkFrame):

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, fg_color=theme.get("surface_0"), corner_radius=0, **kwargs)
        self._app = app

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_body()

    def _build_header(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 8))
        SectionHeader(bar, "Settings").pack(side="left")

    def _build_body(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 16))

        import config as cfg

        # ── Database section ──────────────────────────────────────────────────
        self._section(scroll, "Database")
        self._info_row(scroll, "DB Path",     str(cfg.DB_PATH))
        self._info_row(scroll, "DB Exists",   "Yes" if cfg.DB_PATH.exists() else "No (will be created)")
        self._info_row(scroll, "Data Dir",    str(cfg.DATA_DIR))

        Divider(scroll).pack(fill="x", padx=0, pady=12)

        # ── Triage section ─────────────────────────────────────────────────────
        self._section(scroll, "Triage Engine")
        self._setting_row(scroll, "Detection Threshold",
                          "SOC_THRESHOLD",
                          str(cfg.DEFAULT_THRESHOLD),
                          "Anomaly score cutoff for creating incidents (0.0–1.0)")
        self._setting_row(scroll, "Isolation Forest Weight",
                          "SOC_IF_WEIGHT",
                          str(cfg.IF_WEIGHT),
                          "Weight of Isolation Forest in combined score")
        self._setting_row(scroll, "Autoencoder Weight",
                          "SOC_AE_WEIGHT",
                          str(cfg.AE_WEIGHT),
                          "Weight of Autoencoder in combined score")
        self._setting_row(scroll, "Cluster Window (s)",
                          "SOC_CLUSTER_WINDOW",
                          str(cfg.CLUSTER_WINDOW_SECS),
                          "Time window for alert clustering")

        Divider(scroll).pack(fill="x", padx=0, pady=12)

        # ── MITRE section ──────────────────────────────────────────────────────
        self._section(scroll, "MITRE ATT&CK")
        self._info_row(scroll, "STIX File",  str(cfg.MITRE_STIX))
        self._info_row(scroll, "STIX Exists",
                       "Yes" if cfg.MITRE_STIX.exists() else "Not found (heuristic fallback active)")
        self._info_row(scroll, "Rules File",
                       str(_ROOT / "mitre" / "rules.yaml"))

        Divider(scroll).pack(fill="x", padx=0, pady=12)

        # ── Appearance section ─────────────────────────────────────────────────
        self._section(scroll, "Appearance")

        mode_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        mode_frame.pack(fill="x", pady=6)
        ctk.CTkLabel(mode_frame, text="Theme Mode",
                     font=theme.FONT_LABEL,
                     text_color=theme.get("text_secondary"),
                     width=200, anchor="w").pack(side="left")
        seg = ctk.CTkSegmentedButton(
            mode_frame,
            values=["System", "Light", "Dark"],
            command=self._change_mode,
            font=theme.FONT_SMALL,
        )
        seg.set(ctk.get_appearance_mode())
        seg.pack(side="left")

        Divider(scroll).pack(fill="x", padx=0, pady=12)

        # ── About section ──────────────────────────────────────────────────────
        self._section(scroll, "About")
        about_items = [
            ("Application",  "SOC Triager Desktop"),
            ("Stack",        "Python · CustomTkinter · matplotlib · SQLite"),
            ("Backend",      "services.incident_service (direct call, no HTTP)"),
            ("Python",       sys.version.split()[0]),
            ("Config file",  str(_ROOT / "config.py")),
        ]
        for k, v in about_items:
            self._info_row(scroll, k, v)

    # ── Helper widgets ─────────────────────────────────────────────────────────

    def _section(self, parent, title: str):
        ctk.CTkLabel(parent, text=title,
                     font=theme.FONT_SUBHEAD,
                     text_color=theme.get("text_primary"),
                     anchor="w").pack(fill="x", pady=(8, 4))

    def _info_row(self, parent, key: str, value: str):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=3)
        ctk.CTkLabel(row, text=key + ":",
                     font=theme.FONT_LABEL,
                     text_color=theme.get("text_secondary"),
                     width=200, anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=value,
                     font=theme.FONT_MONO_SM,
                     text_color=theme.get("text_primary"),
                     anchor="w",
                     wraplength=600).pack(side="left", fill="x")

    def _setting_row(self, parent, label: str, env_key: str,
                     current: str, description: str):
        """Editable setting with an Apply button."""
        frame = ctk.CTkFrame(parent,
                             fg_color=theme.get("surface_1"),
                             corner_radius=8,
                             border_width=1,
                             border_color=theme.get("border"))
        frame.pack(fill="x", pady=4)

        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(8, 4))
        top.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top, text=label,
                     font=theme.FONT_LABEL,
                     text_color=theme.get("text_primary"),
                     anchor="w", width=200).grid(row=0, column=0, sticky="w")

        entry = ctk.CTkEntry(top, width=160, font=theme.FONT_MONO_SM,
                             placeholder_text=current)
        entry.insert(0, os.environ.get(env_key, current))
        entry.grid(row=0, column=1, sticky="w", padx=(0, 8))

        ctk.CTkButton(
            top, text="Apply", width=70, height=28,
            font=theme.FONT_SMALL,
            fg_color=theme.get("text_accent"),
            text_color="white",
            corner_radius=6,
            command=lambda e=entry, k=env_key: self._apply_env(k, e.get()),
        ).grid(row=0, column=2, sticky="e")

        ctk.CTkLabel(frame, text=description,
                     font=theme.FONT_SMALL,
                     text_color=theme.get("text_muted"),
                     anchor="w").pack(fill="x", padx=12, pady=(0, 8))

    def _apply_env(self, key: str, value: str):
        os.environ[key] = value.strip()
        # Show brief confirmation
        import threading
        # Flash the button text (can't easily do in CTk without state tracking)
        print(f"[Settings] {key} = {value.strip()}")

    def _change_mode(self, mode: str):
        ctk.set_appearance_mode(mode)

    def refresh(self, data: dict):
        pass  # Settings page is static
