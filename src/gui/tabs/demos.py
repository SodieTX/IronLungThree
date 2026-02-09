"""Demos tab - Demo invite creation and tracking."""

import tkinter as tk
from tkinter import messagebox, ttk

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import ActivityType, EngagementStage, Population, Prospect
from src.gui.tabs import TabBase

logger = get_logger(__name__)


class DemosTab(TabBase):
    """Demo management — upcoming and completed demos."""

    def __init__(self, parent: tk.Widget, db: Database):
        super().__init__(parent, db)
        self._upcoming: list[Prospect] = []
        self._completed: list[Prospect] = []
        self._build_ui()

    def _build_ui(self) -> None:
        self.frame = ttk.Frame(self.parent)  # type: ignore[assignment]

        # --- Header ---
        header = ttk.Frame(self.frame)
        header.pack(fill=tk.X, padx=10, pady=(10, 5))
        ttk.Label(header, text="Demos", font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Upcoming", command=self.show_upcoming,
                   style="Small.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Completed", command=self.show_completed,
                   style="Small.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Refresh", command=self.refresh).pack(side=tk.LEFT, padx=2)

        ttk.Separator(self.frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=5)

        # --- Treeview ---
        tree_frame = ttk.Frame(self.frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ("name", "company", "stage", "follow_up", "score")
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        self._tree.heading("name", text="Name")
        self._tree.heading("company", text="Company")
        self._tree.heading("stage", text="Stage")
        self._tree.heading("follow_up", text="Demo Date")
        self._tree.heading("score", text="Score")
        self._tree.column("name", width=160)
        self._tree.column("company", width=160)
        self._tree.column("stage", width=120)
        self._tree.column("follow_up", width=100)
        self._tree.column("score", width=60)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Status
        self._status_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self._status_var, style="Muted.TLabel").pack(
            fill=tk.X, padx=10, pady=(0, 10),
        )

    # ------------------------------------------------------------------
    # TabBase
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        try:
            engaged = self.db.get_prospects(
                population=Population.ENGAGED,
                sort_by="follow_up_date",
                sort_dir="ASC",
                limit=300,
            )
        except Exception:
            engaged = []

        self._upcoming = [
            p for p in engaged if p.engagement_stage == EngagementStage.DEMO_SCHEDULED
        ]
        self._completed = [
            p for p in engaged if p.engagement_stage == EngagementStage.POST_DEMO
        ]
        self.show_upcoming()

    def on_activate(self) -> None:
        self.refresh()

    # ------------------------------------------------------------------
    # Views
    # ------------------------------------------------------------------

    def create_invite(self) -> None:
        """Open demo invite creator."""
        messagebox.showinfo(
            "Demo Invite",
            "Select a prospect in the Pipeline tab and use Ctrl+M to schedule a demo.",
        )

    def show_upcoming(self) -> None:
        """Show upcoming demos."""
        self._populate_tree(self._upcoming)
        self._status_var.set(f"{len(self._upcoming)} upcoming demos")

    def show_completed(self) -> None:
        """Show completed demos."""
        self._populate_tree(self._completed)
        self._status_var.set(f"{len(self._completed)} completed demos")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _populate_tree(self, prospects: list[Prospect]) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)

        for p in prospects:
            company = self.db.get_company(p.company_id)
            company_name = company.name if company else ""
            stage = p.engagement_stage.value if p.engagement_stage else ""
            follow_up = str(p.follow_up_date) if p.follow_up_date else ""

            self._tree.insert(
                "", tk.END, iid=str(p.id),
                values=(p.full_name, company_name, stage, follow_up, p.prospect_score),
            )
