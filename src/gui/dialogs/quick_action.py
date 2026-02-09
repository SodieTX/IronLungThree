"""Quick action dialog for fast status changes."""

import tkinter as tk
from tkinter import ttk
from typing import Optional

from src.core.logging import get_logger
from src.gui.theme import FONTS

logger = get_logger(__name__)


class QuickActionDialog:
    """Quick action dialog.

    Shows a compact menu of common actions for a prospect:
    move to population, log activity, set follow-up, etc.
    """

    def __init__(self, parent: tk.Widget, prospect_id: int):
        self.parent = parent
        self.prospect_id = prospect_id
        self._action_taken = False
        self._selected_action: Optional[str] = None
        self._dialog: Optional[tk.Toplevel] = None

    def show(self) -> bool:
        """Display dialog. Returns True if action taken."""
        self._dialog = tk.Toplevel(self.parent)
        self._dialog.title("Quick Action")
        self._dialog.geometry("340x380")
        self._dialog.resizable(False, False)
        self._dialog.transient(self.parent)
        self._dialog.grab_set()

        frame = ttk.Frame(self._dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        ttk.Label(
            frame, text="Quick Action", font=("Segoe UI", 12, "bold"),
        ).pack(anchor=tk.W, pady=(0, 12))

        # Action buttons
        actions = [
            ("Mark as Engaged", "engage"),
            ("Park for Later", "park"),
            ("Schedule Follow-up", "follow_up"),
            ("Log Call Attempt", "log_call"),
            ("Log Email Sent", "log_email"),
            ("Send to Dead/DNC", "dead_dnc"),
            ("Schedule Demo", "schedule_demo"),
        ]

        for label, action_id in actions:
            btn = ttk.Button(
                frame, text=label,
                command=lambda a=action_id: self._select_action(a),
            )
            btn.pack(fill=tk.X, pady=2)

        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

        ttk.Button(frame, text="Cancel", command=self._cancel).pack(anchor=tk.E)

        self._dialog.wait_window()
        return self._action_taken

    @property
    def selected_action(self) -> Optional[str]:
        """The action that was selected, or None."""
        return self._selected_action

    def _select_action(self, action: str) -> None:
        self._selected_action = action
        self._action_taken = True
        logger.info(
            "Quick action selected",
            extra={"context": {"prospect_id": self.prospect_id, "action": action}},
        )
        if self._dialog:
            self._dialog.destroy()

    def _cancel(self) -> None:
        self._action_taken = False
        if self._dialog:
            self._dialog.destroy()
