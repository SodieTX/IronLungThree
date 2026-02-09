"""Import preview dialog."""

import tkinter as tk
from tkinter import ttk
from typing import Optional

from src.core.logging import get_logger
from src.db.intake import ImportPreview
from src.gui.theme import COLORS, FONTS

logger = get_logger(__name__)


class ImportPreviewDialog:
    """Import preview and confirmation dialog.

    Shows a breakdown of analyzed import records before committing:
    new, merge, needs_review, blocked_dnc, and incomplete.
    """

    def __init__(self, parent: tk.Widget, preview: ImportPreview):
        self.parent = parent
        self.preview = preview
        self._confirmed = False
        self._dialog: Optional[tk.Toplevel] = None

    def show(self) -> bool:
        """Display dialog. Returns True if confirmed."""
        self._dialog = tk.Toplevel(self.parent)
        self._dialog.title("Import Preview")
        self._dialog.geometry("520x440")
        self._dialog.resizable(False, False)
        self._dialog.transient(self.parent)
        self._dialog.grab_set()

        p = self.preview
        frame = ttk.Frame(self._dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        # Header
        ttk.Label(
            frame, text=f"Import: {p.filename or p.source_name}",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor=tk.W, pady=(0, 8))

        ttk.Label(
            frame, text=f"Total records analyzed: {p.total_records}",
            style="Muted.TLabel",
        ).pack(anchor=tk.W, pady=(0, 12))

        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=4)

        # Summary rows
        rows = [
            ("New prospects:", len(p.new_records), COLORS["success"]),
            ("Merge into existing:", len(p.merge_records), COLORS["accent"]),
            ("Needs manual review:", len(p.needs_review), COLORS["warning"]),
            ("Blocked (DNC):", len(p.blocked_dnc), COLORS["danger"]),
            ("Incomplete:", len(p.incomplete), COLORS["muted"]),
        ]

        for label_text, count, color in rows:
            row = ttk.Frame(frame)
            row.pack(fill=tk.X, pady=3)
            ttk.Label(row, text=label_text, font=FONTS["default"]).pack(side=tk.LEFT)
            lbl = tk.Label(
                row, text=str(count), font=("Segoe UI", 11, "bold"),
                fg=color, bg=COLORS["bg"],
            )
            lbl.pack(side=tk.RIGHT)

        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

        # Action summary
        if p.can_import:
            action_text = (
                f"Will create {len(p.new_records)} new prospect(s) "
                f"and merge {len(p.merge_records)} into existing records."
            )
        else:
            action_text = "No records to import."

        ttk.Label(
            frame, text=action_text, wraplength=480, style="Muted.TLabel",
        ).pack(anchor=tk.W, pady=(4, 12))

        # Warnings
        if p.blocked_dnc:
            ttk.Label(
                frame,
                text=f"{len(p.blocked_dnc)} record(s) blocked by DNC — these will NOT be imported.",
                style="Danger.TLabel", wraplength=480,
            ).pack(anchor=tk.W, pady=(0, 8))

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btn_frame, text="Cancel", command=self._cancel).pack(side=tk.LEFT)

        if p.can_import:
            ttk.Button(
                btn_frame, text="Import", style="Accent.TButton", command=self._confirm,
            ).pack(side=tk.RIGHT)

        self._dialog.wait_window()
        return self._confirmed

    def _confirm(self) -> None:
        self._confirmed = True
        if self._dialog:
            self._dialog.destroy()

    def _cancel(self) -> None:
        self._confirmed = False
        if self._dialog:
            self._dialog.destroy()
