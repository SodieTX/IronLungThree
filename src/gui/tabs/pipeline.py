"""Pipeline tab - Full database view with filtering."""

import csv
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import Population, Prospect
from src.gui.tabs import TabBase

logger = get_logger(__name__)

# Columns displayed in the pipeline treeview
_COLUMNS = ("name", "company", "population", "stage", "score", "follow_up", "attempts", "source")


class PipelineTab(TabBase):
    """Full pipeline view with filtering and bulk operations."""

    def __init__(self, parent: tk.Widget, db: Database):
        super().__init__(parent, db)
        self._prospects: list[Prospect] = []
        self._build_ui()

    def _build_ui(self) -> None:
        self.frame = ttk.Frame(self.parent)  # type: ignore[assignment]

        # --- Header ---
        header = ttk.Frame(self.frame)
        header.pack(fill=tk.X, padx=10, pady=(10, 5))
        ttk.Label(header, text="Pipeline", font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Export CSV", command=self.export_view).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="Refresh", command=self.refresh).pack(side=tk.LEFT)

        # --- Filter bar ---
        filter_frame = ttk.Frame(self.frame)
        filter_frame.pack(fill=tk.X, padx=10, pady=(0, 5))

        ttk.Label(filter_frame, text="Population:").pack(side=tk.LEFT, padx=(0, 4))
        self._pop_var = tk.StringVar(value="All")
        pop_values = ["All"] + [p.value for p in Population]
        pop_combo = ttk.Combobox(
            filter_frame, textvariable=self._pop_var, values=pop_values,
            state="readonly", width=14,
        )
        pop_combo.pack(side=tk.LEFT, padx=(0, 12))
        pop_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())

        ttk.Label(filter_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 4))
        self._search_var = tk.StringVar()
        search_entry = ttk.Entry(filter_frame, textvariable=self._search_var, width=24)
        search_entry.pack(side=tk.LEFT, padx=(0, 8))
        search_entry.bind("<Return>", lambda e: self.apply_filters())
        ttk.Button(
            filter_frame, text="Go", command=self.apply_filters, style="Small.TButton",
        ).pack(side=tk.LEFT)

        # Score range
        ttk.Label(filter_frame, text="Score:").pack(side=tk.LEFT, padx=(12, 4))
        self._score_min_var = tk.StringVar(value="")
        self._score_max_var = tk.StringVar(value="")
        ttk.Entry(filter_frame, textvariable=self._score_min_var, width=4).pack(side=tk.LEFT)
        ttk.Label(filter_frame, text="\u2013").pack(side=tk.LEFT, padx=2)
        ttk.Entry(filter_frame, textvariable=self._score_max_var, width=4).pack(side=tk.LEFT)

        # Population counts
        self._counts_var = tk.StringVar(value="")
        ttk.Label(filter_frame, textvariable=self._counts_var, style="Muted.TLabel").pack(
            side=tk.RIGHT,
        )

        ttk.Separator(self.frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=2)

        # --- Treeview ---
        tree_frame = ttk.Frame(self.frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self._tree = ttk.Treeview(
            tree_frame, columns=_COLUMNS, show="headings", selectmode="extended",
        )
        headings = {
            "name": ("Name", 160),
            "company": ("Company", 150),
            "population": ("Population", 100),
            "stage": ("Stage", 100),
            "score": ("Score", 60),
            "follow_up": ("Follow-up", 100),
            "attempts": ("Attempts", 70),
            "source": ("Source", 100),
        }
        for col, (text, width) in headings.items():
            self._tree.heading(col, text=text, command=lambda c=col: self._sort_by(c))
            self._tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # --- Bulk action bar ---
        bulk_frame = ttk.Frame(self.frame)
        bulk_frame.pack(fill=tk.X, padx=10, pady=(0, 5))

        ttk.Label(bulk_frame, text="Move selected to:").pack(side=tk.LEFT, padx=(0, 4))
        for pop in [Population.UNENGAGED, Population.ENGAGED, Population.PARKED, Population.DEAD_DNC]:
            ttk.Button(
                bulk_frame, text=pop.value, style="Small.TButton",
                command=lambda p=pop.value: self.bulk_move(p),
            ).pack(side=tk.LEFT, padx=2)

        # Status bar
        self._status_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self._status_var, style="Muted.TLabel").pack(
            fill=tk.X, padx=10, pady=(0, 10),
        )

        # Sort state
        self._sort_col = "score"
        self._sort_reverse = True

    # ------------------------------------------------------------------
    # TabBase
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        self.apply_filters()

    def on_activate(self) -> None:
        self.refresh()

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def apply_filters(self) -> None:
        """Query the database with current filter values and update tree."""
        pop_str = self._pop_var.get()
        population: Optional[Population] = None
        if pop_str != "All":
            try:
                population = Population(pop_str)
            except ValueError:
                pass

        search = self._search_var.get().strip() or None
        score_min = _safe_int(self._score_min_var.get())
        score_max = _safe_int(self._score_max_var.get())

        sort_col_map = {
            "name": "first_name",
            "score": "prospect_score",
            "follow_up": "follow_up_date",
            "attempts": "attempt_count",
        }
        sort_by = sort_col_map.get(self._sort_col, "prospect_score")
        sort_dir = "DESC" if self._sort_reverse else "ASC"

        try:
            self._prospects = self.db.get_prospects(
                population=population,
                search_query=search,
                score_min=score_min,
                score_max=score_max,
                sort_by=sort_by,
                sort_dir=sort_dir,
                limit=500,
            )
        except Exception as e:
            logger.error("Pipeline query failed", extra={"context": {"error": str(e)}})
            self._prospects = []

        self._populate_tree()
        self._update_counts()

    def _populate_tree(self) -> None:
        """Fill the treeview from self._prospects."""
        for item in self._tree.get_children():
            self._tree.delete(item)

        for p in self._prospects:
            company = self.db.get_company(p.company_id)
            company_name = company.name if company else ""
            pop_val = p.population.value if p.population else ""
            stage_val = p.engagement_stage.value if p.engagement_stage else ""
            follow_up = str(p.follow_up_date) if p.follow_up_date else ""

            self._tree.insert(
                "", tk.END, iid=str(p.id),
                values=(
                    p.full_name, company_name, pop_val, stage_val,
                    p.prospect_score, follow_up, p.attempt_count, p.source or "",
                ),
            )

        self._status_var.set(f"{len(self._prospects)} prospects")

    def _update_counts(self) -> None:
        """Show population counts in the filter bar."""
        try:
            counts = self.db.get_population_counts()
            parts = [f"{p.value}: {counts.get(p, 0)}" for p in Population]
            self._counts_var.set("  |  ".join(parts))
        except Exception:
            self._counts_var.set("")

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------

    def _sort_by(self, column: str) -> None:
        """Sort by a column header click."""
        if column == self._sort_col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = column
            self._sort_reverse = column == "score"
        self.apply_filters()

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    def bulk_move(self, population: str) -> None:
        """Bulk move selected prospects to a population."""
        selected = self._tree.selection()
        if not selected:
            messagebox.showinfo("No Selection", "Select one or more prospects first.")
            return

        ids = [int(s) for s in selected]
        confirm = messagebox.askyesno(
            "Confirm Bulk Move",
            f"Move {len(ids)} prospect(s) to {population}?",
        )
        if not confirm:
            return

        try:
            target = Population(population)
            updated, skipped_dnc, skipped_invalid = self.db.bulk_update_population(
                ids, target, reason="Bulk move via Pipeline tab",
            )
            self._status_var.set(
                f"Moved {updated}, skipped {skipped_dnc} DNC, {skipped_invalid} invalid"
            )
            self.refresh()
        except Exception as e:
            messagebox.showerror("Error", f"Bulk move failed: {e}")

    def bulk_park(self, month: str) -> None:
        """Bulk park selected prospects to a month."""
        selected = self._tree.selection()
        if not selected:
            messagebox.showinfo("No Selection", "Select one or more prospects first.")
            return

        ids = [int(s) for s in selected]
        try:
            parked, skipped_dnc, skipped_invalid = self.db.bulk_park(ids, month)
            self._status_var.set(
                f"Parked {parked}, skipped {skipped_dnc} DNC, {skipped_invalid} invalid"
            )
            self.refresh()
        except Exception as e:
            messagebox.showerror("Error", f"Bulk park failed: {e}")

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_view(self) -> None:
        """Export the current filtered view to CSV."""
        if not self._prospects:
            messagebox.showinfo("Nothing to Export", "No prospects in the current view.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile="pipeline_export.csv",
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Name", "Company", "Population", "Stage", "Score",
                                 "Follow-up", "Attempts", "Source"])
                for item in self._tree.get_children():
                    writer.writerow(self._tree.item(item, "values"))
            self._status_var.set(f"Exported to {path}")
            logger.info("Pipeline exported", extra={"context": {"path": path}})
        except Exception as e:
            messagebox.showerror("Export Error", str(e))


def _safe_int(val: str) -> Optional[int]:
    """Parse int or return None."""
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
