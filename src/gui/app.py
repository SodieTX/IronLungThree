"""Main application window."""

import tkinter as tk
from tkinter import ttk
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.gui.dictation_bar import DictationBar
from src.gui.shortcuts import bind_shortcuts, unbind_shortcuts
from src.gui.theme import apply_theme

logger = get_logger(__name__)


class IronLungApp:
    """Main application window.

    Creates the root Tk window, tab notebook, dictation bar,
    status bar, and wires keyboard shortcuts.
    """

    def __init__(self, db: Database):
        self.db = db
        self.root: Optional[tk.Tk] = None
        self._notebook: Optional[ttk.Notebook] = None
        self._dictation_bar: Optional[DictationBar] = None
        self._status_var: Optional[tk.StringVar] = None
        self._tabs: dict[str, object] = {}
        self._tab_order: list[str] = []

    def run(self) -> None:
        """Start the application."""
        self._create_window()
        self._create_tabs()
        self._create_status_bar()
        self._bind_shortcuts()

        assert self.root is not None
        logger.info("GUI ready, entering mainloop")
        self.root.mainloop()

    def _create_window(self) -> None:
        """Create main window."""
        self.root = tk.Tk()
        self.root.title("IronLung 3")
        self.root.geometry("1200x800")
        self.root.minsize(900, 600)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        apply_theme(self.root)

    def _create_tabs(self) -> None:
        """Create tab notebook with all tabs."""
        assert self.root is not None

        # Main container: notebook on top, dictation bar on bottom
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        self._notebook = ttk.Notebook(main_frame)
        self._notebook.pack(fill=tk.BOTH, expand=True, padx=4, pady=(4, 0))
        self._notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # Import tabs lazily to avoid circular imports
        from src.gui.tabs.today import TodayTab
        from src.gui.tabs.pipeline import PipelineTab
        from src.gui.tabs.calendar import CalendarTab
        from src.gui.tabs.import_tab import ImportTab
        from src.gui.tabs.demos import DemosTab
        from src.gui.tabs.broken import BrokenTab
        from src.gui.tabs.analytics import AnalyticsTab
        from src.gui.tabs.partnerships import PartnershipsTab
        from src.gui.tabs.intel_gaps import IntelGapsTab
        from src.gui.tabs.troubled import TroubledTab
        from src.gui.tabs.settings import SettingsTab

        tab_specs = [
            ("Today", TodayTab),
            ("Pipeline", PipelineTab),
            ("Calendar", CalendarTab),
            ("Import", ImportTab),
            ("Demos", DemosTab),
            ("Broken", BrokenTab),
            ("Analytics", AnalyticsTab),
            ("Partnerships", PartnershipsTab),
            ("Intel Gaps", IntelGapsTab),
            ("Troubled", TroubledTab),
            ("Settings", SettingsTab),
        ]

        for name, tab_cls in tab_specs:
            try:
                tab = tab_cls(self._notebook, self.db)
                if tab.frame is not None:
                    self._notebook.add(tab.frame, text=name)
                    self._tabs[name] = tab
                    self._tab_order.append(name)
            except Exception as e:
                logger.error(
                    f"Failed to create tab: {name}",
                    extra={"context": {"error": str(e)}},
                )

        # Dictation bar at bottom
        self._dictation_bar = DictationBar(
            main_frame, on_submit=self._on_dictation_submit,
        )
        self._dictation_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # Activate the first tab
        if self._tab_order:
            first_tab = self._tabs.get(self._tab_order[0])
            if first_tab and hasattr(first_tab, "on_activate"):
                first_tab.on_activate()

    def _create_status_bar(self) -> None:
        """Create status bar at the bottom of the window."""
        assert self.root is not None

        status_frame = tk.Frame(self.root, bg="#e0e0e0", height=24)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        status_frame.pack_propagate(False)

        self._status_var = tk.StringVar(value="Ready")
        tk.Label(
            status_frame, textvariable=self._status_var,
            font=("Segoe UI", 9), bg="#e0e0e0", fg="#555555",
            anchor=tk.W,
        ).pack(fill=tk.X, padx=8)

    def _bind_shortcuts(self) -> None:
        """Bind keyboard shortcuts."""
        assert self.root is not None

        today_tab = self._tabs.get("Today")
        handlers: dict[str, object] = {
            "cancel": self.close,
        }

        # Wire Today tab actions if available
        if today_tab:
            if hasattr(today_tab, "next_card"):
                handlers["confirm"] = today_tab.next_card
            if hasattr(today_tab, "_skip"):
                handlers["skip"] = today_tab._skip
            if hasattr(today_tab, "_defer"):
                handlers["defer"] = today_tab._defer

        # Command palette
        try:
            from src.gui.adhd.command_palette import CommandPalette

            palette = CommandPalette(self.root, self.db)
            handlers["command_palette"] = palette.show
        except Exception:
            pass

        # Focus mode
        try:
            from src.gui.adhd.focus import FocusManager

            focus = FocusManager()
            handlers["focus_mode"] = focus.toggle
        except Exception:
            pass

        bind_shortcuts(self.root, handlers)

    def close(self) -> None:
        """Close application gracefully."""
        assert self.root is not None

        # Deactivate current tab
        current = self._get_current_tab()
        if current and hasattr(current, "on_deactivate"):
            current.on_deactivate()

        unbind_shortcuts(self.root)

        logger.info("Application closing")
        self.root.quit()
        self.root.destroy()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_tab_changed(self, event: tk.Event = None) -> None:  # type: ignore[assignment]
        """Handle tab switch — call on_deactivate / on_activate."""
        if not self._notebook:
            return

        # Find which tab is now selected
        try:
            selected_index = self._notebook.index(self._notebook.select())
        except (tk.TclError, ValueError):
            return

        for i, name in enumerate(self._tab_order):
            tab = self._tabs.get(name)
            if tab is None:
                continue
            if i == selected_index:
                if hasattr(tab, "on_activate"):
                    tab.on_activate()
            else:
                if hasattr(tab, "on_deactivate"):
                    tab.on_deactivate()

        if self._status_var and selected_index < len(self._tab_order):
            self._status_var.set(f"{self._tab_order[selected_index]}")

    def _get_current_tab(self) -> Optional[object]:
        """Get the currently selected tab instance."""
        if not self._notebook:
            return None
        try:
            idx = self._notebook.index(self._notebook.select())
            if idx < len(self._tab_order):
                return self._tabs.get(self._tab_order[idx])
        except (tk.TclError, ValueError):
            pass
        return None

    def _on_dictation_submit(self, text: str) -> None:
        """Handle dictation bar submission."""
        logger.info("Dictation input", extra={"context": {"text": text[:50]}})

        if self._dictation_bar:
            self._dictation_bar.show_response(
                f"Got it: \"{text[:80]}{'...' if len(text) > 80 else ''}\"\n"
                "(AI copilot processing not yet connected.)"
            )

    def set_status(self, message: str) -> None:
        """Set status bar message."""
        if self._status_var:
            self._status_var.set(message)
