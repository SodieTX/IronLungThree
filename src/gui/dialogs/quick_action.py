"""Quick action dialog for fast status changes."""

import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox, ttk
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import (
    Activity,
    ActivityOutcome,
    ActivityType,
    Population,
)
from src.engine.cadence import set_follow_up
from src.engine.populations import get_available_transitions, transition_prospect
from src.gui.theme import FONTS

logger = get_logger(__name__)

# Quick action presets
CALL_OUTCOMES = [
    ("Spoke with — interested", ActivityOutcome.INTERESTED),
    ("Spoke with — not now", ActivityOutcome.NOT_NOW),
    ("Spoke with — not interested", ActivityOutcome.NOT_INTERESTED),
    ("Left voicemail", ActivityOutcome.LEFT_VM),
    ("No answer", ActivityOutcome.NO_ANSWER),
    ("Demo set", ActivityOutcome.DEMO_SET),
]

FOLLOW_UP_PRESETS = [
    ("Tomorrow", 1),
    ("In 2 days", 2),
    ("In 3 days", 3),
    ("Next week", 7),
    ("In 2 weeks", 14),
    ("In 1 month", 30),
]


class QuickActionDialog:
    """Quick action dialog for fast disposition after a call or interaction."""

    def __init__(self, parent: tk.Widget, prospect_id: int, db: Optional[Database] = None):
        self.parent = parent
        self.prospect_id = prospect_id
        self.db = db
        self._action_taken = False
        self._dialog: Optional[tk.Toplevel] = None
        self._outcome_var = tk.StringVar()
        self._notes_text: Optional[tk.Text] = None
        self._follow_up_var = tk.StringVar()
        self._pop_var: Optional[tk.StringVar] = None

    def show(self) -> bool:
        """Display dialog. Returns True if action taken."""
        self._dialog = tk.Toplevel(self.parent)
        self._dialog.title("Quick Action")
        self._dialog.geometry("420x480")
        self._dialog.transient(self.parent)
        self._dialog.grab_set()

        main = ttk.Frame(self._dialog, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        # Call outcome section
        ttk.Label(main, text="Call Outcome:", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", pady=(0, 4)
        )
        for label, outcome in CALL_OUTCOMES:
            ttk.Radiobutton(
                main, text=label, variable=self._outcome_var, value=outcome.value,
            ).pack(anchor="w", padx=12)

        ttk.Separator(main, orient="horizontal").pack(fill=tk.X, pady=8)

        # Follow-up section
        ttk.Label(main, text="Set Follow-up:", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", pady=(0, 4)
        )
        fu_frame = ttk.Frame(main)
        fu_frame.pack(fill=tk.X, padx=12)
        for label, days in FOLLOW_UP_PRESETS:
            ttk.Radiobutton(
                fu_frame, text=label, variable=self._follow_up_var, value=str(days),
            ).pack(anchor="w")

        ttk.Separator(main, orient="horizontal").pack(fill=tk.X, pady=8)

        # Notes
        ttk.Label(main, text="Notes:", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", pady=(0, 4)
        )
        self._notes_text = tk.Text(main, height=4, width=40, font=FONTS["small"])
        self._notes_text.pack(fill=tk.X, padx=12, pady=(0, 8))

        # Population change
        if self.db:
            prospect = self.db.get_prospect(self.prospect_id)
            if prospect and prospect.population:
                targets = get_available_transitions(prospect.population)
                if targets:
                    pop_frame = ttk.Frame(main)
                    pop_frame.pack(fill=tk.X, padx=12, pady=(0, 8))
                    ttk.Label(pop_frame, text="Move to:").pack(side=tk.LEFT, padx=(0, 4))
                    self._pop_var = tk.StringVar(value="(no change)")
                    ttk.Combobox(
                        pop_frame, textvariable=self._pop_var,
                        values=["(no change)"] + [p.value for p in targets],
                        state="readonly", width=18,
                    ).pack(side=tk.LEFT)

        # Buttons
        btn_frame = ttk.Frame(main)
        btn_frame.pack(pady=8)
        ttk.Button(btn_frame, text="Apply", command=self._on_apply).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side=tk.LEFT, padx=8)

        self._dialog.wait_window()
        return self._action_taken

    def _on_apply(self) -> None:
        """Apply the quick action."""
        if not self.db:
            self._action_taken = True
            if self._dialog:
                self._dialog.destroy()
            return

        outcome_val = self._outcome_var.get()
        notes = self._notes_text.get("1.0", tk.END).strip() if self._notes_text else ""
        fu_days = self._follow_up_var.get()

        # Log activity
        outcome = None
        if outcome_val:
            try:
                outcome = ActivityOutcome(outcome_val)
            except ValueError:
                pass

        activity = Activity(
            prospect_id=self.prospect_id,
            activity_type=ActivityType.CALL,
            outcome=outcome,
            notes=notes or None,
            created_by="user",
        )
        self.db.create_activity(activity)

        # Set follow-up
        if fu_days:
            days = int(fu_days)
            fu_date = datetime.now() + timedelta(days=days)
            set_follow_up(self.db, self.prospect_id, fu_date, reason="Quick action follow-up")

        # Population change
        if self._pop_var and self._pop_var.get() and self._pop_var.get() != "(no change)":
            try:
                target = Population(self._pop_var.get())
                transition_prospect(self.db, self.prospect_id, target, reason="Quick action")
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=self._dialog)
                return

        # Update attempt count
        prospect = self.db.get_prospect(self.prospect_id)
        if prospect:
            prospect.attempt_count = (prospect.attempt_count or 0) + 1
            self.db.update_prospect(prospect)

        self._action_taken = True
        logger.info(
            f"Quick action applied for prospect {self.prospect_id}",
            extra={"context": {"outcome": outcome_val, "follow_up_days": fu_days}},
        )
        if self._dialog:
            self._dialog.destroy()

    def _on_cancel(self) -> None:
        """Handle cancel."""
        if self._dialog:
            self._dialog.destroy()
