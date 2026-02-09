"""Import preview dialog."""

import tkinter as tk
from tkinter import ttk
from typing import Union

from src.core.logging import get_logger
from src.db.intake import ImportPreview

logger = get_logger(__name__)


class ImportPreviewDialog:
    """Import preview and confirmation dialog."""

    def __init__(self, parent: Union[tk.Tk, tk.Toplevel], preview: ImportPreview):
        self.parent = parent
        self.preview = preview
        self._confirmed = False

    def show(self) -> bool:
        """Display dialog. Returns True if confirmed."""
        dialog = tk.Toplevel(self.parent)
        dialog.title("Import Preview")
        dialog.geometry("600x400")
        dialog.transient(self.parent)
        dialog.grab_set()

        # Summary frame
        summary = ttk.Frame(dialog, padding=10)
        summary.pack(fill=tk.X)

        ttk.Label(summary, text=f"New: {len(self.preview.new_records)}").pack(anchor=tk.W)
        ttk.Label(summary, text=f"Merged: {len(self.preview.merge_records)}").pack(anchor=tk.W)
        ttk.Label(summary, text=f"Blocked (DNC): {len(self.preview.blocked_dnc)}").pack(anchor=tk.W)

        # Buttons
        btn_frame = ttk.Frame(dialog, padding=10)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

        def confirm() -> None:
            self._confirmed = True
            dialog.destroy()

        def cancel() -> None:
            self._confirmed = False
            dialog.destroy()

        ttk.Button(btn_frame, text="Import", command=confirm).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_frame, text="Cancel", command=cancel).pack(side=tk.RIGHT, padx=4)

        dialog.wait_window()
        return self._confirmed
