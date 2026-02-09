"""Pipeline tab - Full database view with filtering."""

import csv
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from src.core.logging import get_logger
from src.gui.tabs import TabBase

logger = get_logger(__name__)


class PipelineTab(TabBase):
    """Full pipeline view with filtering and bulk operations."""

    def __init__(self, parent: tk.Widget, db: object):
        super().__init__(parent, db)
        self._tree: Optional[ttk.Treeview] = None
        self._population_filter: Optional[str] = None
        self._search_var = tk.StringVar()
        self._population_var = tk.StringVar(value="All")
        self._bulk_move_var = tk.StringVar(value="")
        self._bulk_park_var = tk.StringVar(value="")
        self._create_ui()

    def _create_ui(self) -> None:
        """Create pipeline tab UI."""
        if not self.frame:
            return

        # Top toolbar
        toolbar = ttk.Frame(self.frame)
        toolbar.pack(fill=tk.X, padx=5, pady=5)

        # Population filter
        ttk.Label(toolbar, text="Population:").pack(side=tk.LEFT, padx=5)

        from src.db.models import Population

        population_values = ["All"] + [p.value for p in Population]

        population_combo = ttk.Combobox(
            toolbar,
            textvariable=self._population_var,
            values=population_values,
            state="readonly",
            width=15,
        )
        population_combo.pack(side=tk.LEFT, padx=5)
        population_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())

        # Search box
        ttk.Label(toolbar, text="Search:").pack(side=tk.LEFT, padx=5)
        search_entry = ttk.Entry(toolbar, textvariable=self._search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)
        search_entry.bind("<KeyRelease>", lambda e: self.apply_filters())

        # Export button
        export_btn = ttk.Button(toolbar, text="Export View", command=self.export_view)
        export_btn.pack(side=tk.RIGHT, padx=5)

        # Treeview with scrollbars
        tree_frame = ttk.Frame(self.frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create treeview
        self._tree = ttk.Treeview(
            tree_frame,
            columns=("ID", "Name", "Population", "Title", "Score"),
            show="headings",
            selectmode="extended",
        )

        # Configure columns
        self._tree.heading("ID", text="ID", command=lambda: self._sort_column("ID"))
        self._tree.heading("Name", text="Name", command=lambda: self._sort_column("Name"))
        self._tree.heading(
            "Population", text="Population", command=lambda: self._sort_column("Population")
        )
        self._tree.heading("Title", text="Title", command=lambda: self._sort_column("Title"))
        self._tree.heading("Score", text="Score", command=lambda: self._sort_column("Score"))

        self._tree.column("ID", width=50, anchor="center")
        self._tree.column("Name", width=200, anchor="w")
        self._tree.column("Population", width=120, anchor="w")
        self._tree.column("Title", width=200, anchor="w")
        self._tree.column("Score", width=80, anchor="center")

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Grid layout
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        # Double-click to view details
        self._tree.bind("<Double-Button-1>", self._on_double_click)

        # Bulk actions toolbar
        bulk_frame = ttk.Frame(self.frame)
        bulk_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(bulk_frame, text="Bulk Actions:").pack(side=tk.LEFT, padx=5)

        # Bulk move
        ttk.Label(bulk_frame, text="Move to:").pack(side=tk.LEFT, padx=5)
        bulk_move_combo = ttk.Combobox(
            bulk_frame,
            textvariable=self._bulk_move_var,
            values=[p.value for p in Population],
            state="readonly",
            width=15,
        )
        bulk_move_combo.pack(side=tk.LEFT, padx=5)

        move_btn = ttk.Button(
            bulk_frame,
            text="Apply Move",
            command=self._apply_bulk_move,
        )
        move_btn.pack(side=tk.LEFT, padx=5)

        # Bulk park
        ttk.Label(bulk_frame, text="Park in:").pack(side=tk.LEFT, padx=5)

        # Generate next 12 months
        from datetime import datetime

        current = datetime.now()
        months = []
        for i in range(12):
            month = (current.month + i - 1) % 12 + 1
            year = current.year + (current.month + i - 1) // 12
            months.append(f"{year:04d}-{month:02d}")

        bulk_park_combo = ttk.Combobox(
            bulk_frame,
            textvariable=self._bulk_park_var,
            values=months,
            state="readonly",
            width=10,
        )
        bulk_park_combo.pack(side=tk.LEFT, padx=5)

        park_btn = ttk.Button(
            bulk_frame,
            text="Apply Park",
            command=self._apply_bulk_park,
        )
        park_btn.pack(side=tk.LEFT, padx=5)

        # Selection info
        self._selection_label = ttk.Label(bulk_frame, text="0 selected")
        self._selection_label.pack(side=tk.RIGHT, padx=5)

        self._tree.bind("<<TreeviewSelect>>", self._on_selection_changed)

    def refresh(self) -> None:
        """Reload pipeline data from database."""
        if self._tree is None:
            return

        # Clear existing items
        self._tree.delete(*self._tree.get_children())

        # Get filter value
        from src.db.models import Population

        population_filter = None
        if self._population_var.get() != "All":
            try:
                population_filter = Population(self._population_var.get())
            except ValueError:
                pass

        # Get prospects
        try:
            prospects = self.db.get_prospects(population=population_filter, limit=10000)

            # Apply search filter
            search_term = self._search_var.get().lower()
            if search_term:
                prospects = [
                    p
                    for p in prospects
                    if search_term in p.full_name.lower()
                    or (p.title and search_term in p.title.lower())
                    or (p.population and search_term in p.population.value.lower())
                ]

            # Insert into tree
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
        except Exception as e:
            logger.error(f"Failed to refresh pipeline: {e}")
            messagebox.showerror("Error", f"Failed to load prospects: {e}")

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

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["ID", "Name", "Population", "Title", "Score"])
                for row_id in self._tree.get_children():
                    writer.writerow(self._tree.item(row_id)["values"])

            messagebox.showinfo("Export Complete", f"Exported to {file_path}")
            logger.info(f"Pipeline exported to {file_path}")
        except Exception as e:
            logger.error(f"Export failed: {e}")
            messagebox.showerror("Error", f"Export failed: {e}")

    def _apply_bulk_move(self) -> None:
        """Apply bulk move to selected prospects."""
        target_population = self._bulk_move_var.get()
        if not target_population:
            messagebox.showwarning("Warning", "Please select a target population")
            return

        from src.db.models import Population

        try:
            population = Population(target_population)
            self.bulk_move(population.value)
        except ValueError:
            messagebox.showerror("Error", f"Invalid population: {target_population}")

    def _apply_bulk_park(self) -> None:
        """Apply bulk park to selected prospects."""
        target_month = self._bulk_park_var.get()
        if not target_month:
            messagebox.showwarning("Warning", "Please select a target month")
            return

        self.bulk_park(target_month)

    def bulk_move(self, population: str) -> None:
        """Bulk move selected to population."""
        if self._tree is None:
            return

        selected = self._tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "No prospects selected")
            return

        prospect_ids = [self._tree.item(item)["values"][0] for item in selected]

        if not messagebox.askyesno(
            "Confirm Move", f"Move {len(selected)} prospects to {population}?"
        ):
            return

        try:
            self.db.bulk_update_population(prospect_ids, population)
            messagebox.showinfo("Success", f"Moved {len(selected)} prospects to {population}")
            logger.info(f"Bulk moved {len(selected)} prospects to {population}")
            self.refresh()
        except Exception as e:
            logger.error(f"Bulk move failed: {e}")
            messagebox.showerror("Error", f"Bulk move failed: {e}")

    def bulk_park(self, month: str) -> None:
        """Bulk park selected to month."""
        if self._tree is None:
            return

        selected = self._tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "No prospects selected")
            return

        prospect_ids = [self._tree.item(item)["values"][0] for item in selected]

        if not messagebox.askyesno(
            "Confirm Park", f"Park {len(selected)} prospects until {month}?"
        ):
            return

        try:
            self.db.bulk_park(prospect_ids, month)
            messagebox.showinfo("Success", f"Parked {len(selected)} prospects until {month}")
            logger.info(f"Bulk parked {len(selected)} prospects to {month}")
            self.refresh()
        except Exception as e:
            logger.error(f"Bulk park failed: {e}")
            messagebox.showerror("Error", f"Bulk park failed: {e}")

    def _on_double_click(self, event: object) -> None:
        """Handle double-click on tree item."""
        if self._tree is None:
            return

        selection = self._tree.selection()
        if not selection:
            return

        item = self._tree.item(selection[0])
        prospect_id = item["values"][0]

        # Show simple details dialog
        self._show_prospect_details(int(prospect_id))

    def _show_prospect_details(self, prospect_id: int) -> None:
        """Show prospect details dialog."""
        try:
            prospect = self.db.get_prospect(prospect_id)
            if not prospect:
                messagebox.showerror("Error", f"Prospect {prospect_id} not found")
                return

            # Create dialog
            dialog = tk.Toplevel(self.frame)
            dialog.title(f"Prospect Details - {prospect.full_name}")
            dialog.geometry("500x400")

            # Details frame
            details_frame = ttk.Frame(dialog, padding=10)
            details_frame.pack(fill=tk.BOTH, expand=True)

            # Create text widget
            text = tk.Text(details_frame, wrap=tk.WORD)
            text.pack(fill=tk.BOTH, expand=True)

            # Add prospect details
            text.insert(tk.END, f"ID: {prospect.id}\n")
            text.insert(tk.END, f"Name: {prospect.full_name}\n")
            text.insert(tk.END, f"Title: {prospect.title or 'N/A'}\n")
            pop_val = prospect.population.value if prospect.population else "N/A"
            text.insert(tk.END, f"Population: {pop_val}\n")
            text.insert(tk.END, f"Score: {prospect.prospect_score or 'N/A'}\n")
            text.insert(tk.END, f"\nNotes:\n{prospect.notes or 'No notes'}\n")

            # Get company info
            if prospect.company_id:
                company = self.db.get_company(prospect.company_id)
                if company:
                    text.insert(tk.END, f"\nCompany: {company.name}\n")
                    if company.state:
                        text.insert(tk.END, f"State: {company.state}\n")

            text.config(state="disabled")

            # Close button
            ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

        except Exception as e:
            logger.error(f"Failed to show prospect details: {e}")
            messagebox.showerror("Error", f"Failed to load prospect details: {e}")

    def _on_selection_changed(self, event: object) -> None:
        """Update selection count label."""
        if self._tree is None:
            return
        selected = self._tree.selection()
        self._selection_label.config(text=f"{len(selected)} selected")

    def _sort_column(self, col: str) -> None:
        """Sort treeview by column."""
        if self._tree is None:
            return

        # Get all items
        items = [(self._tree.item(item)["values"], item) for item in self._tree.get_children()]

        # Determine column index
        columns = ["ID", "Name", "Population", "Title", "Score"]
        col_index = columns.index(col)

        # Sort items with proper handling of empty values
        def sort_key(item: tuple) -> tuple:
            value = item[0][col_index]

            # Handle empty or None values
            if value is None or value == "":
                # Empty values sort last
                return (1, "")

            # Try numeric sort for ID and Score
            if col in ["ID", "Score"]:
                try:
                    return (0, int(value))
                except (ValueError, TypeError):
                    # If conversion fails, treat as string
                    return (0, str(value))

            # Text columns sort alphabetically
            return (0, str(value).lower())

        items.sort(key=sort_key)

        # Rearrange items
        for index, (values, item) in enumerate(items):
            self._tree.move(item, "", index)
