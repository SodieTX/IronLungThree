"""Main application window."""

import tkinter as tk
from tkinter import ttk
from typing import Any, Optional

from src.core.logging import get_logger
from src.db.database import Database

logger = get_logger(__name__)


class IronLungApp:
    """Main application window."""

    def __init__(self, db: Database):
        self.db = db
        self.root: Optional[tk.Tk] = None
        self._notebook: Optional[ttk.Notebook] = None
        self._today_tab: Any = None
        self._import_tab: Any = None
        self._pipeline_tab: Any = None
        self._calendar_tab: Any = None
        self._broken_tab: Any = None
        self._settings_tab: Any = None
        self._status_label: Optional[ttk.Label] = None

    def run(self) -> None:
        """Start the application."""
        self._create_window()
        self._create_tabs()
        self._create_status_bar()
        self._bind_shortcuts()
        logger.info("IronLung 3 GUI launched")
        if self.root:
            self.root.mainloop()

    def _create_window(self) -> None:
        """Create main window."""
        self.root = tk.Tk()
        self.root.title("IronLung 3")
        self.root.geometry("1200x800")
        self.root.minsize(800, 600)

        from src.gui.theme import apply_theme

        apply_theme(self.root)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        logger.info("Main window created")

    def _create_tabs(self) -> None:
        """Create tab notebook."""
        if not self.root:
            return
        self._notebook = ttk.Notebook(self.root)
        self._notebook.pack(fill=tk.BOTH, expand=True, padx=4, pady=(4, 0))

        # Today tab (primary work surface)
        from src.gui.tabs.today import TodayTab

        today_frame: tk.Widget = ttk.Frame(self._notebook)
        today_tab = TodayTab(today_frame, self.db)
        today_tab.frame = today_frame  # type: ignore[assignment]
        self._notebook.add(today_frame, text="Today")
        self._today_tab = today_tab

        # Import tab
        from src.gui.tabs.import_tab import ImportTab

        import_frame: tk.Widget = ttk.Frame(self._notebook)
        import_tab = ImportTab(import_frame, self.db)
        import_tab.frame = import_frame  # type: ignore[assignment]
        self._notebook.add(import_frame, text="Import")
        self._import_tab = import_tab

        # Pipeline tab
        from src.gui.tabs.pipeline import PipelineTab

        pipeline_frame: tk.Widget = ttk.Frame(self._notebook)
        pipeline_tab = PipelineTab(pipeline_frame, self.db)
        pipeline_tab.frame = pipeline_frame  # type: ignore[assignment]
        self._notebook.add(pipeline_frame, text="Pipeline")
        self._pipeline_tab = pipeline_tab

        # Calendar tab
        from src.gui.tabs.calendar import CalendarTab

        calendar_frame: tk.Widget = ttk.Frame(self._notebook)
        calendar_tab = CalendarTab(calendar_frame, self.db)
        calendar_tab.frame = calendar_frame  # type: ignore[assignment]
        self._notebook.add(calendar_frame, text="Calendar")
        self._calendar_tab = calendar_tab

        # Broken tab
        from src.gui.tabs.broken import BrokenTab

        broken_frame: tk.Widget = ttk.Frame(self._notebook)
        broken_tab = BrokenTab(broken_frame, self.db)
        broken_tab.frame = broken_frame  # type: ignore[assignment]
        self._notebook.add(broken_frame, text="Broken")
        self._broken_tab = broken_tab

        # Settings tab
        from src.gui.tabs.settings import SettingsTab

        settings_frame: tk.Widget = ttk.Frame(self._notebook)
        settings_tab = SettingsTab(settings_frame, self.db)
        settings_tab.frame = settings_frame  # type: ignore[assignment]
        self._notebook.add(settings_frame, text="Settings")
        self._settings_tab = settings_tab

        # Bind tab change event
        self._notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        logger.info(
            "Tab notebook created with Today, Import, Pipeline, Calendar, Broken, and Settings tabs"
        )

    def _create_status_bar(self) -> None:
        """Create status bar."""
        if not self.root:
            return
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self._status_label = ttk.Label(status_frame, text="Ready", anchor=tk.W)
        self._status_label.pack(fill=tk.X, padx=4, pady=2)
        self._update_status_bar()
        logger.info("Status bar created")

    def _bind_shortcuts(self) -> None:
        """Bind keyboard shortcuts."""
        if not self.root:
            return
        from src.gui.shortcuts import bind_shortcuts

        handlers = {
            "quick_lookup": self._focus_search,
        }
        bind_shortcuts(self.root, handlers)
        self.root.bind("<Control-q>", lambda e: self.close())
        self.root.bind("<Control-w>", lambda e: self.close())
        logger.info("Keyboard shortcuts bound")

    def _focus_search(self) -> None:
        """Focus the Today tab search field (Ctrl+F)."""
        if self._notebook and self._today_tab:
            self._notebook.select(0)  # Switch to Today tab
            if hasattr(self._today_tab, "_search_var"):
                self._today_tab._search_var.set("")

    def _on_tab_changed(self, event: object) -> None:
        """Handle tab change event."""
        if not self._notebook:
            return
        current_tab = self._notebook.index(self._notebook.select())
        tabs = [
            self._today_tab,
            self._import_tab,
            self._pipeline_tab,
            self._calendar_tab,
            self._broken_tab,
            self._settings_tab,
        ]
        if current_tab < len(tabs) and tabs[current_tab]:
            tabs[current_tab].on_activate()
        self._update_status_bar()

    def _update_status_bar(self) -> None:
        """Update status bar with database statistics."""
        if not self._status_label:
            return
        try:
            from src.db.models import Population

            # Get counts for each population
            total = len(self.db.get_prospects())
            unengaged = len(self.db.get_prospects(population=Population.UNENGAGED))
            engaged = len(self.db.get_prospects(population=Population.ENGAGED))

            status_text = f"{total} prospects | {unengaged} unengaged | {engaged} engaged"
            self._status_label.config(text=status_text)
        except Exception as e:
            logger.warning(f"Failed to update status bar: {e}")
            self._status_label.config(text="Ready")

    def close(self) -> None:
        """Close application gracefully."""
        logger.info("Closing IronLung 3...")
        self.db.close()
        if self.root:
            self.root.destroy()
            self.root = None
        logger.info("IronLung 3 closed")
