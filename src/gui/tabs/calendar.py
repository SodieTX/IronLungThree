"""Calendar tab - Day/week views and follow-ups.

Provides visual calendar showing follow-ups, demos, and
monthly parked buckets. Not a list of dates — a real calendar.
"""

import calendar
import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import ttk
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import Population
from src.gui.tabs import TabBase
from src.gui.theme import COLORS, FONTS

logger = get_logger(__name__)


class CalendarTab(TabBase):
    """Calendar view with follow-ups and demos."""

    def __init__(self, parent: tk.Widget, db: Database):
        super().__init__(parent, db)
        self._view_mode = "week"  # week, day, buckets
        self._current_date = date.today()
        self._content_frame: Optional[tk.Frame] = None
        self._create_ui()

    def _create_ui(self) -> None:
        """Create calendar tab UI."""
        if not self.frame:
            return

        # Top toolbar: view switcher + navigation
        toolbar = ttk.Frame(self.frame)
        toolbar.pack(fill=tk.X, padx=8, pady=8)

        ttk.Button(toolbar, text="< Prev", command=self._prev_period).pack(side=tk.LEFT, padx=4)
        ttk.Button(toolbar, text="Today", command=self._go_today).pack(side=tk.LEFT, padx=4)
        ttk.Button(toolbar, text="Next >", command=self._next_period).pack(side=tk.LEFT, padx=4)

        self._date_label = ttk.Label(toolbar, text="", font=FONTS["large"])
        self._date_label.pack(side=tk.LEFT, padx=16)

        # View mode buttons (right side)
        ttk.Button(toolbar, text="Day", command=self.show_day_view).pack(side=tk.RIGHT, padx=4)
        ttk.Button(toolbar, text="Week", command=self.show_week_view).pack(side=tk.RIGHT, padx=4)
        ttk.Button(toolbar, text="Parked Buckets", command=self.show_monthly_buckets).pack(
            side=tk.RIGHT, padx=4
        )

        # Content area
        self._content_frame = tk.Frame(self.frame, bg=COLORS["bg_alt"])
        self._content_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

    def refresh(self) -> None:
        """Reload calendar data."""
        if self._view_mode == "week":
            self._render_week()
        elif self._view_mode == "day":
            self._render_day()
        elif self._view_mode == "buckets":
            self._render_buckets()

    def on_activate(self) -> None:
        """Called when this tab becomes visible."""
        self.refresh()

    def show_day_view(self) -> None:
        """Show hour-by-hour day view."""
        self._view_mode = "day"
        self._render_day()

    def show_week_view(self) -> None:
        """Show seven-column week view."""
        self._view_mode = "week"
        self._render_week()

    def show_monthly_buckets(self) -> None:
        """Show parked contacts by month."""
        self._view_mode = "buckets"
        self._render_buckets()

    def _prev_period(self) -> None:
        """Navigate to previous period."""
        if self._view_mode == "day":
            self._current_date -= timedelta(days=1)
        elif self._view_mode == "week":
            self._current_date -= timedelta(weeks=1)
        elif self._view_mode == "buckets":
            # Move back 1 month
            m = self._current_date.month - 1
            y = self._current_date.year
            if m < 1:
                m = 12
                y -= 1
            self._current_date = self._current_date.replace(year=y, month=m, day=1)
        self.refresh()

    def _next_period(self) -> None:
        """Navigate to next period."""
        if self._view_mode == "day":
            self._current_date += timedelta(days=1)
        elif self._view_mode == "week":
            self._current_date += timedelta(weeks=1)
        elif self._view_mode == "buckets":
            m = self._current_date.month + 1
            y = self._current_date.year
            if m > 12:
                m = 1
                y += 1
            self._current_date = self._current_date.replace(year=y, month=m, day=1)
        self.refresh()

    def _go_today(self) -> None:
        """Jump to today."""
        self._current_date = date.today()
        self.refresh()

    def _clear_content(self) -> None:
        """Clear the content frame."""
        if self._content_frame:
            for w in self._content_frame.winfo_children():
                w.destroy()

    def _update_date_label(self) -> None:
        """Update the date display in toolbar."""
        if not hasattr(self, "_date_label"):
            return
        if self._view_mode == "day":
            self._date_label.config(text=self._current_date.strftime("%A, %B %d, %Y"))
        elif self._view_mode == "week":
            # Show week range
            monday = self._current_date - timedelta(days=self._current_date.weekday())
            friday = monday + timedelta(days=4)
            self._date_label.config(
                text=f"Week of {monday.strftime('%b %d')} - {friday.strftime('%b %d, %Y')}"
            )
        elif self._view_mode == "buckets":
            self._date_label.config(text=self._current_date.strftime("%B %Y"))

    # ------------------------------------------------------------------
    # WEEK VIEW
    # ------------------------------------------------------------------

    def _render_week(self) -> None:
        """Render the week view — 5 columns (Mon-Fri)."""
        self._clear_content()
        self._update_date_label()

        if not self._content_frame:
            return

        monday = self._current_date - timedelta(days=self._current_date.weekday())
        conn = self.db._get_connection()

        for col, day_offset in enumerate(range(5)):
            day = monday + timedelta(days=day_offset)
            day_iso = day.isoformat()
            is_today = day == date.today()

            # Column frame
            col_frame = tk.Frame(
                self._content_frame,
                bg=COLORS["bg_alt"] if not is_today else "#e6f0ff",
                bd=1,
                relief="solid",
            )
            col_frame.grid(row=0, column=col, sticky="nsew", padx=1, pady=1)
            self._content_frame.columnconfigure(col, weight=1)
            self._content_frame.rowconfigure(0, weight=1)

            # Day header
            header_text = day.strftime("%a %m/%d")
            header_bg = COLORS["accent"] if is_today else COLORS["muted"]
            tk.Label(
                col_frame,
                text=header_text,
                font=("Segoe UI", 10, "bold"),
                bg=header_bg,
                fg="#ffffff",
                anchor="center",
            ).pack(fill=tk.X)

            # Get follow-ups for this day
            rows = conn.execute(
                """SELECT p.id, p.first_name, p.last_name, p.population,
                          p.engagement_stage, c.timezone as company_tz
                   FROM prospects p
                   LEFT JOIN companies c ON p.company_id = c.id
                   WHERE DATE(p.follow_up_date) = DATE(?)
                   AND p.population NOT IN (?, ?, ?)
                   ORDER BY p.prospect_score DESC""",
                (
                    day_iso,
                    Population.DEAD_DNC.value,
                    Population.CLOSED_WON.value,
                    Population.LOST.value,
                ),
            ).fetchall()

            if not rows:
                tk.Label(
                    col_frame,
                    text="—",
                    font=FONTS["small"],
                    bg=col_frame["bg"],
                    fg=COLORS["muted"],
                ).pack(pady=8)
                continue

            # Scrollable list for this day
            canvas = tk.Canvas(col_frame, bg=col_frame["bg"], highlightthickness=0)
            canvas.pack(fill=tk.BOTH, expand=True)
            inner = tk.Frame(canvas, bg=col_frame["bg"])
            canvas.create_window((0, 0), window=inner, anchor="nw")
            inner.bind(
                "<Configure>",
                lambda e, c=canvas: c.configure(scrollregion=c.bbox("all")),  # type: ignore[misc]
            )

            for row in rows:
                name = f"{row['first_name']} {row['last_name']}"
                pop = row["population"] or ""
                stage = row["engagement_stage"] or ""
                tz = row["company_tz"] or ""

                entry_text = name
                if stage:
                    entry_text += f" [{stage}]"
                if tz:
                    entry_text += f" ({tz[:3].upper()})"

                color = COLORS["success"] if pop == "engaged" else COLORS["accent"]
                tk.Label(
                    inner,
                    text=entry_text,
                    font=FONTS["small"],
                    bg=col_frame["bg"],
                    fg=color,
                    anchor="w",
                    wraplength=140,
                ).pack(fill=tk.X, padx=4, pady=1)

    # ------------------------------------------------------------------
    # DAY VIEW
    # ------------------------------------------------------------------

    def _render_day(self) -> None:
        """Render the day view — list of follow-ups for one day."""
        self._clear_content()
        self._update_date_label()

        if not self._content_frame:
            return

        day_iso = self._current_date.isoformat()
        conn = self.db._get_connection()

        rows = conn.execute(
            """SELECT p.id, p.first_name, p.last_name, p.title, p.population,
                      p.engagement_stage, p.prospect_score, p.follow_up_date,
                      c.name as company_name, c.timezone as company_tz
               FROM prospects p
               LEFT JOIN companies c ON p.company_id = c.id
               WHERE DATE(p.follow_up_date) = DATE(?)
               AND p.population NOT IN (?, ?, ?)
               ORDER BY c.timezone ASC, p.prospect_score DESC""",
            (
                day_iso,
                Population.DEAD_DNC.value,
                Population.CLOSED_WON.value,
                Population.LOST.value,
            ),
        ).fetchall()

        if not rows:
            tk.Label(
                self._content_frame,
                text="No follow-ups scheduled for this day.",
                font=FONTS["large"],
                bg=COLORS["bg_alt"],
                fg=COLORS["muted"],
            ).pack(expand=True)
            return

        # Header
        tk.Label(
            self._content_frame,
            text=f"{len(rows)} follow-up(s) scheduled",
            font=FONTS["large"],
            bg=COLORS["bg_alt"],
            fg=COLORS["fg"],
        ).pack(padx=12, pady=(8, 4), anchor="w")

        # Follow-up list
        tree = ttk.Treeview(
            self._content_frame,
            columns=("Name", "Company", "Population", "Stage", "TZ", "Score"),
            show="headings",
            selectmode="browse",
        )
        tree.heading("Name", text="Name")
        tree.heading("Company", text="Company")
        tree.heading("Population", text="Population")
        tree.heading("Stage", text="Stage")
        tree.heading("TZ", text="TZ")
        tree.heading("Score", text="Score")

        tree.column("Name", width=180)
        tree.column("Company", width=160)
        tree.column("Population", width=100)
        tree.column("Stage", width=100)
        tree.column("TZ", width=70)
        tree.column("Score", width=60)

        for row in rows:
            name = f"{row['first_name']} {row['last_name']}"
            tree.insert(
                "",
                tk.END,
                values=(
                    name,
                    row["company_name"] or "",
                    row["population"] or "",
                    row["engagement_stage"] or "",
                    (row["company_tz"] or "")[:3].upper(),
                    row["prospect_score"] or "",
                ),
            )

        tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    # ------------------------------------------------------------------
    # MONTHLY BUCKETS
    # ------------------------------------------------------------------

    def _render_buckets(self) -> None:
        """Render parked contacts grouped by month."""
        self._clear_content()
        self._update_date_label()

        if not self._content_frame:
            return

        conn = self.db._get_connection()

        # Get all parked prospects grouped by month
        rows = conn.execute(
            """SELECT p.parked_month, COUNT(*) as cnt,
                      GROUP_CONCAT(p.first_name || ' ' || p.last_name, ', ') as names
               FROM prospects p
               WHERE p.population = ?
               AND p.parked_month IS NOT NULL
               GROUP BY p.parked_month
               ORDER BY p.parked_month ASC""",
            (Population.PARKED.value,),
        ).fetchall()

        if not rows:
            tk.Label(
                self._content_frame,
                text="No parked prospects.",
                font=FONTS["large"],
                bg=COLORS["bg_alt"],
                fg=COLORS["muted"],
            ).pack(expand=True)
            return

        tk.Label(
            self._content_frame,
            text="PARKED PROSPECTS BY MONTH",
            font=("Segoe UI", 12, "bold"),
            bg=COLORS["bg_alt"],
            fg=COLORS["accent"],
        ).pack(padx=12, pady=(12, 8), anchor="w")

        for row in rows:
            month = row["parked_month"]
            count = row["cnt"]
            names = row["names"] or ""

            # Parse month for display
            try:
                year, mon = month.split("-")
                month_name = calendar.month_name[int(mon)]
                display = f"{month_name} {year}"
            except (ValueError, IndexError):
                display = month

            # Month card
            card = tk.Frame(self._content_frame, bg=COLORS["bg_alt"], bd=1, relief="solid")
            card.pack(fill=tk.X, padx=12, pady=4)

            tk.Label(
                card,
                text=f"{display}: {count} prospect(s)",
                font=("Segoe UI", 11, "bold"),
                bg=COLORS["bg_alt"],
                fg=COLORS["fg"],
                anchor="w",
            ).pack(fill=tk.X, padx=8, pady=(6, 2))

            # Show first few names
            name_list = names.split(", ")[:5]
            preview = ", ".join(name_list)
            if count > 5:
                preview += f" ... and {count - 5} more"
            tk.Label(
                card,
                text=preview,
                font=FONTS["small"],
                bg=COLORS["bg_alt"],
                fg=COLORS["muted"],
                anchor="w",
                wraplength=500,
            ).pack(fill=tk.X, padx=8, pady=(0, 6))
