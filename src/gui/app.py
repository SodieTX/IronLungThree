"""Main application window."""

import tkinter as tk
from tkinter import ttk
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database

logger = get_logger(__name__)


class IronLungApp:
    """Main application window."""

    def __init__(self, db: Database):
        self.db = db
        self.root: Optional[tk.Tk] = None
        self._notebook: Optional[ttk.Notebook] = None
        self._import_tab = None
        self._pipeline_tab = None
        self._settings_tab = None
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
        
        # Import tab
        from src.gui.tabs.import_tab import ImportTab
        import_frame = ttk.Frame(self._notebook)
        import_tab = ImportTab(import_frame, self.db)
        import_tab.frame = import_frame
        self._notebook.add(import_frame, text="Import")
        self._import_tab = import_tab
        
        # Pipeline tab
        from src.gui.tabs.pipeline import PipelineTab
        pipeline_frame = ttk.Frame(self._notebook)
        pipeline_tab = PipelineTab(pipeline_frame, self.db)
        pipeline_tab.frame = pipeline_frame
        self._notebook.add(pipeline_frame, text="Pipeline")
        self._pipeline_tab = pipeline_tab
        
        # Settings tab (placeholder for Phase 1)
        from src.gui.tabs.settings import SettingsTab
        settings_frame = ttk.Frame(self._notebook)
        settings_tab = SettingsTab(settings_frame, self.db)
        settings_tab.frame = settings_frame
        self._notebook.add(settings_frame, text="Settings")
        self._settings_tab = settings_tab
        
        # Bind tab change event
        self._notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        
        logger.info("Tab notebook created with Import, Pipeline, and Settings tabs")

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
        self.root.bind("<Control-q>", lambda e: self.close())
        self.root.bind("<Control-w>", lambda e: self.close())
        logger.info("Keyboard shortcuts bound")

    def _on_tab_changed(self, event) -> None:
        """Handle tab change event."""
        if not self._notebook:
            return
        current_tab = self._notebook.index(self._notebook.select())
        tabs = [self._import_tab, self._pipeline_tab, self._settings_tab]
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
