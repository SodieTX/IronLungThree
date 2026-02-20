"""Edit prospect dialog."""

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Optional

from src.core.logging import get_logger
from src.db.models import EngagementStage, Population, Prospect
from src.engine.populations import get_available_transitions
from src.gui.theme import COLORS, FONTS

logger = get_logger(__name__)


class EditProspectDialog:
    """Prospect editing form dialog."""

    def __init__(self, parent: tk.Widget, prospect: Prospect):
        self.parent = parent
        self.prospect = prospect
        self._saved = False
        self._dialog: Optional[tk.Toplevel] = None

        # Field variables
        self._first_name_var = tk.StringVar(value=prospect.first_name or "")
        self._last_name_var = tk.StringVar(value=prospect.last_name or "")
        self._title_var = tk.StringVar(value=prospect.title or "")
        self._population_var = tk.StringVar(
            value=prospect.population.value if prospect.population else ""
        )
        self._stage_var = tk.StringVar(
            value=prospect.engagement_stage.value if prospect.engagement_stage else ""
        )
        self._follow_up_var = tk.StringVar(
            value=str(prospect.follow_up_date)[:10] if prospect.follow_up_date else ""
        )
        self._notes_text: Optional[tk.Text] = None
        self._source_var = tk.StringVar(value=prospect.source or "")

    def show(self) -> bool:
        """Display dialog. Returns True if saved."""
        self._dialog = tk.Toplevel(self.parent)
        self._dialog.title(f"Edit: {self.prospect.full_name}")
        self._dialog.geometry("500x550")
        self._dialog.transient(self.parent.winfo_toplevel())
        self._dialog.grab_set()

        main = ttk.Frame(self._dialog, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        row = 0

        # First name
        ttk.Label(main, text="First Name:").grid(row=row, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(main, textvariable=self._first_name_var, width=30).grid(
            row=row, column=1, sticky="w", padx=4, pady=4
        )
        row += 1

        # Last name
        ttk.Label(main, text="Last Name:").grid(row=row, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(main, textvariable=self._last_name_var, width=30).grid(
            row=row, column=1, sticky="w", padx=4, pady=4
        )
        row += 1

        # Title
        ttk.Label(main, text="Title:").grid(row=row, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(main, textvariable=self._title_var, width=30).grid(
            row=row, column=1, sticky="w", padx=4, pady=4
        )
        row += 1

        # Population
        ttk.Label(main, text="Population:").grid(row=row, column=0, sticky="e", padx=4, pady=4)
        current_pop = self.prospect.population
        valid_targets = get_available_transitions(current_pop) if current_pop else []
        pop_values = [current_pop.value] + [p.value for p in valid_targets] if current_pop else []
        ttk.Combobox(
            main, textvariable=self._population_var, values=pop_values,
            state="readonly", width=28,
        ).grid(row=row, column=1, sticky="w", padx=4, pady=4)
        row += 1

        # Engagement stage (only visible when engaged)
        ttk.Label(main, text="Stage:").grid(row=row, column=0, sticky="e", padx=4, pady=4)
        stage_values = [s.value for s in EngagementStage]
        ttk.Combobox(
            main, textvariable=self._stage_var, values=stage_values,
            state="readonly", width=28,
        ).grid(row=row, column=1, sticky="w", padx=4, pady=4)
        row += 1

        # Follow-up date
        ttk.Label(main, text="Follow-up (YYYY-MM-DD):").grid(
            row=row, column=0, sticky="e", padx=4, pady=4
        )
        ttk.Entry(main, textvariable=self._follow_up_var, width=30).grid(
            row=row, column=1, sticky="w", padx=4, pady=4
        )
        row += 1

        # Source
        ttk.Label(main, text="Source:").grid(row=row, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(main, textvariable=self._source_var, width=30).grid(
            row=row, column=1, sticky="w", padx=4, pady=4
        )
        row += 1

        # Notes
        ttk.Label(main, text="Notes:").grid(row=row, column=0, sticky="ne", padx=4, pady=4)
        self._notes_text = tk.Text(main, width=35, height=6, font=FONTS["small"])
        self._notes_text.grid(row=row, column=1, sticky="w", padx=4, pady=4)
        if self.prospect.notes:
            self._notes_text.insert("1.0", self.prospect.notes)
        row += 1

        # Buttons
        btn_frame = ttk.Frame(main)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=12)
        ttk.Button(btn_frame, text="Save", command=self._on_save).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side=tk.LEFT, padx=8)

        self._dialog.wait_window()
        return self._saved

    def get_updated_prospect(self) -> Prospect:
        """Get updated prospect data."""
        p = self.prospect
        p.first_name = self._first_name_var.get().strip()
        p.last_name = self._last_name_var.get().strip()
        p.title = self._title_var.get().strip() or None
        p.source = self._source_var.get().strip() or None

        # Population
        pop_val = self._population_var.get()
        if pop_val:
            try:
                p.population = Population(pop_val)
            except ValueError:
                pass

        # Stage
        stage_val = self._stage_var.get()
        if stage_val and p.population == Population.ENGAGED:
            try:
                p.engagement_stage = EngagementStage(stage_val)
            except ValueError:
                pass
        elif p.population != Population.ENGAGED:
            p.engagement_stage = None

        # Follow-up date
        fu = self._follow_up_var.get().strip()
        if fu:
            try:
                p.follow_up_date = datetime.fromisoformat(fu)
            except ValueError:
                pass
        else:
            p.follow_up_date = None

        # Notes
        if self._notes_text:
            p.notes = self._notes_text.get("1.0", tk.END).strip() or None

        return p

    def _on_save(self) -> None:
        """Handle save button."""
        parent = self._dialog if self._dialog else self.parent.winfo_toplevel()
        if not self._first_name_var.get().strip():
            messagebox.showwarning("Validation", "First name is required.", parent=parent)
            return
        if not self._last_name_var.get().strip():
            messagebox.showwarning("Validation", "Last name is required.", parent=parent)
            return
        self._saved = True
        if self._dialog:
            self._dialog.destroy()

    def _on_cancel(self) -> None:
        """Handle cancel button."""
        if self._dialog:
            self._dialog.destroy()
