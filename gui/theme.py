# gui/theme.py
"""
Colour tokens and font constants for the SOC Triager desktop app.
All widgets import from here — no inline colours anywhere.
"""
from __future__ import annotations
import sys
import customtkinter as ctk

# ── Appearance ─────────────────────────────────────────────────────────────────
DEFAULT_APPEARANCE = "system"   # honours OS dark/light setting

# ── Palettes ──────────────────────────────────────────────────────────────────
LIGHT: dict[str, str] = {
    "surface_0":     "#f8fafc",
    "surface_1":     "#f1f5f9",
    "surface_2":     "#ffffff",
    "surface_hover": "#e2e8f0",
    "text_primary":  "#0f172a",
    "text_secondary":"#64748b",
    "text_muted":    "#94a3b8",
    "text_accent":   "#1d4ed8",
    "text_danger":   "#dc2626",
    "text_warning":  "#d97706",
    "text_success":  "#16a34a",
    "border":        "#e2e8f0",
    "border_strong": "#cbd5e1",
    "bg_accent":     "#eff6ff",
    # Severity
    "sev_critical":    "#991b1b",
    "sev_critical_bg": "#fef2f2",
    "sev_high":        "#9a3412",
    "sev_high_bg":     "#fff7ed",
    "sev_medium":      "#854d0e",
    "sev_medium_bg":   "#fefce8",
    "sev_low":         "#166534",
    "sev_low_bg":      "#f0fdf4",
    "sev_info":        "#374151",
    "sev_info_bg":     "#f9fafb",
    # Status
    "status_open":           "#1e40af",
    "status_investigating":  "#92400e",
    "status_resolved":       "#14532d",
    "status_false_positive": "#374151",
    "status_new":            "#1e40af",
    "status_ack":            "#92400e",
    "status_escalated":      "#7f1d1d",
    "status_closed":         "#374151",
}

DARK: dict[str, str] = {
    "surface_0":     "#0f172a",
    "surface_1":     "#1e293b",
    "surface_2":     "#0f172a",
    "surface_hover": "#334155",
    "text_primary":  "#f1f5f9",
    "text_secondary":"#94a3b8",
    "text_muted":    "#64748b",
    "text_accent":   "#60a5fa",
    "text_danger":   "#f87171",
    "text_warning":  "#fbbf24",
    "text_success":  "#4ade80",
    "border":        "#1e293b",
    "border_strong": "#334155",
    "bg_accent":     "#1e3a5f",
    "sev_critical":    "#fca5a5",
    "sev_critical_bg": "#450a0a",
    "sev_high":        "#fdba74",
    "sev_high_bg":     "#431407",
    "sev_medium":      "#fde047",
    "sev_medium_bg":   "#422006",
    "sev_low":         "#86efac",
    "sev_low_bg":      "#052e16",
    "sev_info":        "#9ca3af",
    "sev_info_bg":     "#111827",
    "status_open":           "#93c5fd",
    "status_investigating":  "#fcd34d",
    "status_resolved":       "#6ee7b7",
    "status_false_positive": "#9ca3af",
    "status_new":            "#93c5fd",
    "status_ack":            "#fcd34d",
    "status_escalated":      "#fca5a5",
    "status_closed":         "#9ca3af",
}

# ── Fonts ──────────────────────────────────────────────────────────────────────
FONT_FAMILY  = "Segoe UI"  if sys.platform == "win32" else "SF Pro Display"
FONT_MONO    = "Consolas"  if sys.platform == "win32" else "Menlo"
FONT_BODY    = (FONT_FAMILY, 13)
FONT_SMALL   = (FONT_FAMILY, 11)
FONT_LABEL   = (FONT_FAMILY, 11, "bold")
FONT_HEADING = (FONT_FAMILY, 20, "bold")
FONT_SUBHEAD = (FONT_FAMILY, 15, "bold")
FONT_MONO_SM = (FONT_MONO,  11)
FONT_MONO_XS = (FONT_MONO,   9)


def get(key: str) -> str:
    """Return colour token for the current appearance mode."""
    mode = ctk.get_appearance_mode()
    palette = DARK if mode == "Dark" else LIGHT
    return palette.get(key, "#ff00ff")   # magenta = missing token


def sev_color(severity: str) -> str:
    return get(f"sev_{severity.lower()}")

def sev_bg(severity: str) -> str:
    return get(f"sev_{severity.lower()}_bg")

def status_color(status: str) -> str:
    key = status.lower().replace(" ", "_").replace("-", "_")
    return get(f"status_{key}")


def apply_theme() -> None:
    """Call once at startup."""
    ctk.set_appearance_mode(DEFAULT_APPEARANCE)
    ctk.set_default_color_theme("blue")
