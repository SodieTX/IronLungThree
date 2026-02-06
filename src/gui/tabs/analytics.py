"""Analytics tab - Performance metrics and reporting.

Step 7.8: Revenue tracking, commission earned, close rate,
cycle time, top sources, pipeline movement. Numbers + CSV export.
"""

import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import filedialog, ttk

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import Population
from src.engine.export import MonthlySummary, export_summary_csv, generate_monthly_summary
from src.gui.tabs import TabBase

logger = get_logger(__name__)


class AnalyticsTab(TabBase):
    """Performance analytics and monthly reporting."""

    def __init__(self, parent: tk.Widget, db: Database):
        super().__init__(parent, db)
        self._summary: MonthlySummary | None = None
        self._current_month: str = date.today().strftime("%Y-%m")
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the analytics tab UI."""
        self.frame = ttk.Frame(self.parent)  # type: ignore[assignment]

        # Header with month selector
        header = ttk.Frame(self.frame)
        header.pack(fill=tk.X, padx=10, pady=(10, 5))

        ttk.Label(header, text="Analytics", font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT)

        # Month selector
        month_frame = ttk.Frame(header)
        month_frame.pack(side=tk.RIGHT)

        ttk.Label(month_frame, text="Month:").pack(side=tk.LEFT, padx=(0, 5))
        self._month_var = tk.StringVar(value=self._current_month)
        month_entry = ttk.Entry(month_frame, textvariable=self._month_var, width=10)
        month_entry.pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(month_frame, text="Load", command=self._load_month).pack(
            side=tk.LEFT, padx=(0, 5)
        )
        ttk.Button(month_frame, text="Export CSV", command=self._export_csv).pack(side=tk.LEFT)

        # Separator
        ttk.Separator(self.frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=5)

        # Main content area with two columns
        content = ttk.Frame(self.frame)
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Left column - Key metrics
        left = ttk.LabelFrame(content, text="Key Metrics", padding=10)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        self._metrics_labels: dict[str, ttk.Label] = {}
        metrics = [
            ("deals_closed", "Deals Closed"),
            ("total_revenue", "Total Revenue"),
            ("commission", "Commission Earned"),
            ("avg_deal", "Avg Deal Size"),
            ("win_rate", "Win Rate"),
            ("avg_cycle", "Avg Cycle (days)"),
        ]
        for key, label_text in metrics:
            row = ttk.Frame(left)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=f"{label_text}:", width=20, anchor=tk.W).pack(side=tk.LEFT)
            val_label = ttk.Label(row, text="—", font=("Consolas", 11), anchor=tk.E)
            val_label.pack(side=tk.RIGHT)
            self._metrics_labels[key] = val_label

        # Right column - Activity metrics
        right = ttk.LabelFrame(content, text="Activity", padding=10)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        activity_metrics = [
            ("demos", "Demos Booked"),
            ("calls", "Calls Made"),
            ("emails", "Emails Sent"),
            ("added", "Pipeline Added"),
            ("engaged", "Newly Engaged"),
            ("lost", "Pipeline Lost"),
        ]
        for key, label_text in activity_metrics:
            row = ttk.Frame(right)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=f"{label_text}:", width=20, anchor=tk.W).pack(side=tk.LEFT)
            val_label = ttk.Label(row, text="—", font=("Consolas", 11), anchor=tk.E)
            val_label.pack(side=tk.RIGHT)
            self._metrics_labels[key] = val_label

        # Bottom - Pipeline snapshot
        bottom = ttk.LabelFrame(self.frame, text="Pipeline Snapshot", padding=10)
        bottom.pack(fill=tk.X, padx=10, pady=(5, 10))

        self._pipeline_labels: dict[str, ttk.Label] = {}
        pop_frame = ttk.Frame(bottom)
        pop_frame.pack(fill=tk.X)

        populations = [
            ("engaged", "Engaged"),
            ("unengaged", "Unengaged"),
            ("broken", "Broken"),
            ("parked", "Parked"),
            ("won", "Won"),
            ("lost_pop", "Lost"),
        ]
        for key, label_text in populations:
            col = ttk.Frame(pop_frame)
            col.pack(side=tk.LEFT, expand=True, padx=5)
            ttk.Label(col, text=label_text, font=("Segoe UI", 9)).pack()
            val = ttk.Label(col, text="0", font=("Consolas", 14, "bold"))
            val.pack()
            self._pipeline_labels[key] = val

    def refresh(self) -> None:
        """Reload analytics from database."""
        self._current_month = self._month_var.get().strip()
        try:
            self._summary = generate_monthly_summary(self.db, self._current_month)
        except Exception as e:
            logger.error(
                "Analytics refresh failed",
                extra={"context": {"month": self._current_month, "error": str(e)}},
            )
            self._summary = None
        self._update_display()

    def on_activate(self) -> None:
        """Called when tab becomes visible."""
        self.refresh()

    def _load_month(self) -> None:
        """Load a specific month's data."""
        self.refresh()

    def _update_display(self) -> None:
        """Update display with current summary data."""
        if not self._summary:
            for label in self._metrics_labels.values():
                label.configure(text="—")
            return

        s = self._summary

        # Key metrics
        self._metrics_labels["deals_closed"].configure(text=str(s.deals_closed))
        self._metrics_labels["total_revenue"].configure(
            text=f"${s.total_revenue:,.2f}" if s.total_revenue else "$0.00"
        )
        self._metrics_labels["commission"].configure(
            text=f"${s.commission_earned:,.2f}" if s.commission_earned else "$0.00"
        )
        self._metrics_labels["avg_deal"].configure(
            text=f"${s.avg_deal_size:,.2f}" if s.avg_deal_size else "—"
        )

        # Win rate
        total_outcomes = s.deals_closed + s.pipeline_lost
        if total_outcomes > 0:
            rate = round(s.deals_closed / total_outcomes * 100)
            self._metrics_labels["win_rate"].configure(text=f"{rate}%")
        else:
            self._metrics_labels["win_rate"].configure(text="—")

        self._metrics_labels["avg_cycle"].configure(
            text=str(round(s.avg_cycle_days)) if s.avg_cycle_days else "—"
        )

        # Activity metrics
        self._metrics_labels["demos"].configure(text=str(s.demos_booked))
        self._metrics_labels["calls"].configure(text=str(s.calls_made))
        self._metrics_labels["emails"].configure(text=str(s.emails_sent))
        self._metrics_labels["added"].configure(text=str(s.pipeline_added))
        self._metrics_labels["engaged"].configure(text=str(s.pipeline_engaged))
        self._metrics_labels["lost"].configure(text=str(s.pipeline_lost))

        # Pipeline snapshot (current, not month-specific)
        pop_counts = self.db.get_population_counts()
        pop_map = {
            "engaged": Population.ENGAGED,
            "unengaged": Population.UNENGAGED,
            "broken": Population.BROKEN,
            "parked": Population.PARKED,
            "won": Population.CLOSED_WON,
            "lost_pop": Population.LOST,
        }
        for key, pop in pop_map.items():
            count = pop_counts.get(pop, 0)
            self._pipeline_labels[key].configure(text=str(count))

    def generate_report(self, month: str) -> None:
        """Generate and export monthly report."""
        self._month_var.set(month)
        self.refresh()
        self._export_csv()

    def _export_csv(self) -> None:
        """Export current summary to CSV."""
        if not self._summary:
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile=f"ironlung_report_{self._current_month}.csv",
        )
        if not path:
            return

        try:
            export_summary_csv(self._summary, Path(path))
            logger.info(
                "Analytics report exported",
                extra={"context": {"path": path, "month": self._current_month}},
            )
        except Exception as e:
            logger.error(
                "Analytics export failed",
                extra={"context": {"error": str(e)}},
            )
