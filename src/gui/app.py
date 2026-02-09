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
        self._notebook.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        logger.info("Tab notebook created")

    def _create_status_bar(self) -> None:
        """Create status bar."""
        if not self.root:
            return
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        status_label = ttk.Label(status_frame, text="Ready", anchor=tk.W)
        status_label.pack(fill=tk.X, padx=4, pady=2)
        logger.info("Status bar created")

    def _bind_shortcuts(self) -> None:
        """Bind keyboard shortcuts."""
        if not self.root:
            return
        self.root.bind("<Control-q>", lambda e: self.close())
        self.root.bind("<Control-w>", lambda e: self.close())
        logger.info("Keyboard shortcuts bound")

    def close(self) -> None:
        """Close application gracefully."""
        logger.info("Closing IronLung 3...")
        self.db.close()
        if self.root:
            self.root.destroy()
            self.root = None
        logger.info("IronLung 3 closed")
