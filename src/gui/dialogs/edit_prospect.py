"""Edit prospect dialog."""

import tkinter as tk
from tkinter import ttk
from typing import Optional

from src.core.logging import get_logger
from src.db.models import Prospect
from src.gui.theme import COLORS, FONTS

logger = get_logger(__name__)


class EditProspectDialog:
    """Prospect editing form dialog.

    Shows editable fields for the prospect and saves on confirm.
    """

    def __init__(self, parent: tk.Widget, prospect: Prospect):
        self.parent = parent
        self.prospect = prospect
        self._saved = False
        self._dialog: Optional[tk.Toplevel] = None

        # Editable fields
        self._var_first: Optional[tk.StringVar] = None
        self._var_last: Optional[tk.StringVar] = None
        self._var_title: Optional[tk.StringVar] = None
        self._var_notes: Optional[tk.Text] = None
        self._var_score: Optional[tk.StringVar] = None

    def show(self) -> bool:
        """Display dialog. Returns True if saved."""
        self._dialog = tk.Toplevel(self.parent)
        self._dialog.title(f"Edit: {self.prospect.full_name}")
        self._dialog.geometry("500x480")
        self._dialog.resizable(False, False)
        self._dialog.transient(self.parent)
        self._dialog.grab_set()

        p = self.prospect
        frame = ttk.Frame(self._dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        # Fields
        self._var_first = tk.StringVar(value=p.first_name or "")
        self._var_last = tk.StringVar(value=p.last_name or "")
        self._var_title = tk.StringVar(value=p.title or "")
        self._var_score = tk.StringVar(value=str(p.prospect_score))

        self._field(frame, "First Name:", self._var_first)
        self._field(frame, "Last Name:", self._var_last)
        self._field(frame, "Title:", self._var_title)
        self._field(frame, "Score (0-100):", self._var_score)

        # Notes (multiline)
        ttk.Label(frame, text="Notes:").pack(anchor=tk.W, pady=(8, 2))
        self._var_notes = tk.Text(frame, height=8, font=FONTS["default"], wrap=tk.WORD)
        self._var_notes.pack(fill=tk.X)
        if p.notes:
            self._var_notes.insert("1.0", p.notes)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(16, 0))
        ttk.Button(btn_frame, text="Cancel", command=self._cancel).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Save", style="Accent.TButton", command=self._save).pack(
            side=tk.RIGHT,
        )

        self._dialog.wait_window()
        return self._saved

    def get_updated_prospect(self) -> Prospect:
        """Get updated prospect data."""
        p = self.prospect
        if self._var_first:
            p.first_name = self._var_first.get().strip()
        if self._var_last:
            p.last_name = self._var_last.get().strip()
        if self._var_title:
            p.title = self._var_title.get().strip() or None
        if self._var_score:
            try:
                p.prospect_score = max(0, min(100, int(self._var_score.get())))
            except ValueError:
                pass
        if self._var_notes:
            p.notes = self._var_notes.get("1.0", tk.END).strip() or None
        return p

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _field(self, parent: tk.Widget, label: str, var: tk.StringVar) -> None:
        ttk.Label(parent, text=label).pack(anchor=tk.W, pady=(8, 2))
        ttk.Entry(parent, textvariable=var, width=50).pack(fill=tk.X)

    def _save(self) -> None:
        self._saved = True
        if self._dialog:
            self._dialog.destroy()

    def _cancel(self) -> None:
        self._saved = False
        if self._dialog:
            self._dialog.destroy()
