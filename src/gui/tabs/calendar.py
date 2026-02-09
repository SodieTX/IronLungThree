"""Calendar tab - Day/week views and follow-ups."""

import tkinter as tk
from datetime import date, timedelta
from tkinter import ttk

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import Population, Prospect
from src.gui.tabs import TabBase

logger = get_logger(__name__)


class CalendarTab(TabBase):
    """Calendar view with follow-ups and demos."""

    def __init__(self, parent: tk.Widget, db: Database):
        super().__init__(parent, db)
        self._view = "week"  # week | month
        self._build_ui()

    def _build_ui(self) -> None:
        self.frame = ttk.Frame(self.parent)  # type: ignore[assignment]

        # --- Header ---
        header = ttk.Frame(self.frame)
        header.pack(fill=tk.X, padx=10, pady=(10, 5))
        ttk.Label(header, text="Calendar", font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT)

        view_frame = ttk.Frame(header)
        view_frame.pack(side=tk.RIGHT)
        ttk.Button(view_frame, text="Week", command=self.show_week_view, style="Small.TButton").pack(
            side=tk.LEFT, padx=2,
        )
        ttk.Button(
            view_frame, text="Parked", command=self.show_monthly_buckets, style="Small.TButton",
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(view_frame, text="Refresh", command=self.refresh, style="Small.TButton").pack(
            side=tk.LEFT, padx=2,
        )

        ttk.Separator(self.frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=5)

        # --- Content area ---
        self._content = ttk.Frame(self.frame)
        self._content.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Status
        self._status_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self._status_var, style="Muted.TLabel").pack(
            fill=tk.X, padx=10, pady=(0, 10),
        )

    # ------------------------------------------------------------------
    # TabBase
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        if self._view == "week":
            self.show_week_view()
        else:
            self.show_monthly_buckets()

    def on_activate(self) -> None:
        self.refresh()

    # ------------------------------------------------------------------
    # Views
    # ------------------------------------------------------------------

    def show_day_view(self) -> None:
        """Show hour-by-hour day view (alias for week with 1 col)."""
        self.show_week_view()

    def show_week_view(self) -> None:
        """Show seven-column week view with follow-ups."""
        self._view = "week"
        for child in self._content.winfo_children():
            child.destroy()

        today = date.today()
        start = today - timedelta(days=today.weekday())  # Monday

        # Fetch engaged + unengaged with follow-up dates
        prospects: list[Prospect] = []
        for pop in [Population.ENGAGED, Population.UNENGAGED]:
            try:
                prospects.extend(
                    self.db.get_prospects(
                        population=pop, sort_by="follow_up_date", sort_dir="ASC", limit=300,
                    )
                )
            except Exception:
                pass

        # Bucket by day
        day_buckets: dict[date, list[Prospect]] = {start + timedelta(days=i): [] for i in range(7)}
        overdue: list[Prospect] = []

        for p in prospects:
            if not p.follow_up_date:
                continue
            if p.follow_up_date < start:
                overdue.append(p)
            elif p.follow_up_date in day_buckets:
                day_buckets[p.follow_up_date].append(p)

        # Render columns
        cols_frame = ttk.Frame(self._content)
        cols_frame.pack(fill=tk.BOTH, expand=True)

        if overdue:
            col = self._make_day_column(cols_frame, "Overdue", overdue)
            col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

        for day_offset in range(7):
            d = start + timedelta(days=day_offset)
            label = d.strftime("%a %m/%d")
            if d == today:
                label += " (today)"
            bucket = day_buckets[d]
            col = self._make_day_column(cols_frame, label, bucket)
            col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

        total = sum(len(b) for b in day_buckets.values()) + len(overdue)
        self._status_var.set(f"{total} follow-ups this week, {len(overdue)} overdue")

    def show_monthly_buckets(self) -> None:
        """Show parked contacts by month."""
        self._view = "month"
        for child in self._content.winfo_children():
            child.destroy()

        try:
            parked = self.db.get_prospects(
                population=Population.PARKED, sort_by="follow_up_date", sort_dir="ASC", limit=500,
            )
        except Exception:
            parked = []

        # Group by parked_month
        buckets: dict[str, list[Prospect]] = {}
        for p in parked:
            month = p.parked_month or "Unspecified"
            buckets.setdefault(month, []).append(p)

        if not buckets:
            ttk.Label(self._content, text="No parked contacts.", style="Muted.TLabel").pack(pady=20)
            return

        for month, prospects in sorted(buckets.items()):
            col = self._make_day_column(self._content, f"Parked: {month}", prospects)
            col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

        self._status_var.set(f"{len(parked)} parked contacts across {len(buckets)} months")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_day_column(
        self, parent: tk.Widget, heading: str, prospects: list[Prospect],
    ) -> ttk.Frame:
        """Create a single day/bucket column."""
        col = ttk.LabelFrame(parent, text=f"{heading} ({len(prospects)})", padding=4)

        for p in prospects[:20]:  # cap display
            company = self.db.get_company(p.company_id)
            company_name = company.name if company else ""
            text = f"{p.full_name}\n{company_name}"
            lbl = tk.Label(
                col, text=text, font=("Segoe UI", 8), anchor=tk.W, justify=tk.LEFT,
                bg="#ffffff", relief=tk.RIDGE, padx=4, pady=2,
            )
            lbl.pack(fill=tk.X, pady=1)

        if len(prospects) > 20:
            ttk.Label(col, text=f"+{len(prospects) - 20} more", style="Muted.TLabel").pack()

        return col
