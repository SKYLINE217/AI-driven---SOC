# gui/app.py
"""
Root CustomTkinter window.
Creates sidebar + content area, manages page lifecycle.
"""
from __future__ import annotations

import customtkinter as ctk
from gui.theme import apply_theme
from gui.sidebar import Sidebar
from gui.worker import BackgroundWorker

# Pages
from gui.pages.alert_queue     import AlertQueuePage
from gui.pages.navigator       import NavigatorPage
from gui.pages.ops_metrics     import OpsMetricsPage
from gui.pages.playbook_library import PlaybookLibraryPage
from gui.pages.settings        import SettingsPage


class SOCApp(ctk.CTk):
    """Main application window."""

    PAGE_CLASSES = {
        "alerts":    AlertQueuePage,
        "navigator": NavigatorPage,
        "ops":       OpsMetricsPage,
        "playbooks": PlaybookLibraryPage,
        "settings":  SettingsPage,
    }

    def __init__(self):
        super().__init__()

        apply_theme()

        self.title("SOC Triager")
        self.geometry("1366x820")
        self.minsize(960, 640)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self._sidebar = Sidebar(self, navigate_fn=self.show_page)
        self._sidebar.grid(row=0, column=0, sticky="nsw")

        # Content container
        self._content = ctk.CTkFrame(self, corner_radius=0,
                                     fg_color=("white", "#0f172a"))
        self._content.grid(row=0, column=1, sticky="nsew")
        self._content.grid_rowconfigure(0, weight=1)
        self._content.grid_columnconfigure(0, weight=1)

        self._pages:    dict[str, ctk.CTkFrame] = {}
        self._cur_page: str = ""

        # Background data worker
        self._worker = BackgroundWorker(callback=self._on_data_ready)

        # Show landing page
        self.show_page("alerts")

        # Start worker after window is drawn
        self.after(200, self._worker.start)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Page management ────────────────────────────────────────────────────────

    def show_page(self, name: str) -> None:
        if name not in self._pages:
            cls = self.PAGE_CLASSES.get(name)
            if cls is None:
                return
            page = cls(self._content, app=self)
            page.grid(row=0, column=0, sticky="nsew")
            self._pages[name] = page

        for pname, frame in self._pages.items():
            frame.tkraise() if pname == name else None

        self._pages[name].tkraise()
        self._sidebar.set_active(name)
        self._cur_page = name

    # ── Data callbacks ─────────────────────────────────────────────────────────

    def _on_data_ready(self, data: dict) -> None:
        """Called from worker thread via after() — runs on main thread."""
        page = self._pages.get(self._cur_page)
        if page and hasattr(page, "refresh"):
            try:
                page.refresh(data)
            except Exception as exc:
                print(f"[app] page refresh error: {exc}")

        self._sidebar.set_alert_count(data.get("alert_count", 0))

    def trigger_refresh(self):
        """Force an immediate data refresh (called after status updates etc.)."""
        self._worker.trigger_refresh()

    # ── Shutdown ───────────────────────────────────────────────────────────────

    def _on_close(self) -> None:
        self._worker.stop()
        self.destroy()
