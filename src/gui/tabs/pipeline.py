"""Pipeline tab - Full database view with filtering."""

import csv
import tkinter as tk
from io import StringIO
from tkinter import filedialog, ttk
from typing import Optional

from src.core.logging import get_logger
from src.db.models import Population
from src.gui.tabs import TabBase

logger = get_logger(__name__)


class PipelineTab(TabBase):
    """Full pipeline view with filtering and bulk operations."""

    def __init__(self, parent: tk.Widget, db: object):
        super().__init__(parent, db)
        self._tree: Optional[ttk.Treeview] = None
        self._population_filter: Optional[str] = None

    def refresh(self) -> None:
        """Reload pipeline data from database."""
        if self._tree is None:
            return
        self._tree.delete(*self._tree.get_children())
        prospects = self.db.get_prospects(population=self._population_filter)
        for p in prospects:
            self._tree.insert(
                "",
                tk.END,
                values=(
                    p.id,
                    p.full_name,
                    p.population.value if p.population else "",
                    p.title or "",
                    str(p.prospect_score or ""),
                ),
            )
        logger.info(f"Pipeline refreshed: {len(prospects)} prospects loaded")

    def on_activate(self) -> None:
        """Called when this tab becomes visible."""
        self.refresh()

    def apply_filters(self) -> None:
        """Apply current filter settings."""
        self.refresh()

    def export_view(self) -> None:
        """Export current view to CSV."""
        if self._tree is None:
            return
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")],
        )
        if not file_path:
            return
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "Name", "Population", "Title", "Score"])
            for row_id in self._tree.get_children():
                writer.writerow(self._tree.item(row_id)["values"])
        logger.info(f"Pipeline exported to {file_path}")

    def bulk_move(self, population: str) -> None:
        """Bulk move selected to population."""
        if self._tree is None:
            return
        selected = self._tree.selection()
        for item in selected:
            values = self._tree.item(item)["values"]
            prospect_id = values[0]
            self.db.update_prospect(prospect_id, {"population": population})
        logger.info(f"Bulk moved {len(selected)} prospects to {population}")
        self.refresh()

    def bulk_park(self, month: str) -> None:
        """Bulk park selected to month."""
        if self._tree is None:
            return
        selected = self._tree.selection()
        prospect_ids = [self._tree.item(item)["values"][0] for item in selected]
        self.db.bulk_park(prospect_ids, month)
        logger.info(f"Bulk parked {len(selected)} prospects to {month}")
        self.refresh()
