"""Today tab - Morning brief and card processing."""

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import Population, Prospect
from src.gui.cards import ProspectCard
from src.gui.tabs import TabBase

logger = get_logger(__name__)


class TodayTab(TabBase):
    """Today tab with queue processing.

    Loads the daily queue (UNENGAGED by score, ENGAGED by follow-up date)
    and presents one card at a time. Tracks progress with a counter.
    """

    def __init__(self, parent: tk.Widget, db: Database):
        super().__init__(parent, db)
        self._queue: list[Prospect] = []
        self._queue_index: int = 0
        self._build_ui()

    def _build_ui(self) -> None:
        self.frame = ttk.Frame(self.parent)  # type: ignore[assignment]

        # --- Header ---
        header = ttk.Frame(self.frame)
        header.pack(fill=tk.X, padx=10, pady=(10, 5))
        ttk.Label(header, text="Today", font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT)

        self._queue_label = ttk.Label(header, text="", style="Muted.TLabel")
        self._queue_label.pack(side=tk.RIGHT)

        # --- Progress bar ---
        self._progress = ttk.Progressbar(self.frame, mode="determinate", length=300)
        self._progress.pack(fill=tk.X, padx=10, pady=(0, 5))

        ttk.Separator(self.frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=2)

        # --- Card area ---
        card_frame = ttk.Frame(self.frame)
        card_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._card = ProspectCard(card_frame)
        self._card.pack(fill=tk.BOTH, expand=True)

        # --- Action buttons ---
        action_frame = ttk.Frame(self.frame)
        action_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(action_frame, text="Skip (Tab)", command=self._skip).pack(side=tk.LEFT, padx=4)
        ttk.Button(action_frame, text="Defer (Ctrl+D)", command=self._defer).pack(
            side=tk.LEFT, padx=4,
        )
        ttk.Button(action_frame, text="Deep Dive", command=self._deep_dive).pack(
            side=tk.LEFT, padx=4,
        )
        ttk.Button(action_frame, text="Call Mode", command=self._call_mode).pack(
            side=tk.LEFT, padx=4,
        )
        ttk.Button(
            action_frame, text="Next Card", style="Accent.TButton", command=self.next_card,
        ).pack(side=tk.RIGHT, padx=4)

        # --- Status ---
        self._status_var = tk.StringVar(value="Load the queue to start processing.")
        ttk.Label(self.frame, textvariable=self._status_var, style="Muted.TLabel").pack(
            fill=tk.X, padx=10, pady=(0, 10),
        )

    # ------------------------------------------------------------------
    # TabBase
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        self._load_queue()

    def on_activate(self) -> None:
        self.refresh()

    # ------------------------------------------------------------------
    # Queue
    # ------------------------------------------------------------------

    def _load_queue(self) -> None:
        """Build today's processing queue."""
        today = date.today()
        queue: list[Prospect] = []

        # Engaged prospects with follow-up due today or earlier
        try:
            engaged = self.db.get_prospects(
                population=Population.ENGAGED,
                sort_by="follow_up_date",
                sort_dir="ASC",
                limit=200,
            )
            for p in engaged:
                if p.follow_up_date and p.follow_up_date <= today:
                    queue.append(p)
        except Exception as e:
            logger.error("Failed to load engaged queue", extra={"context": {"error": str(e)}})

        # Unengaged prospects by score (top N)
        try:
            unengaged = self.db.get_prospects(
                population=Population.UNENGAGED,
                sort_by="prospect_score",
                sort_dir="DESC",
                limit=50,
            )
            queue.extend(unengaged)
        except Exception as e:
            logger.error("Failed to load unengaged queue", extra={"context": {"error": str(e)}})

        self._queue = queue
        self._queue_index = 0
        self._update_progress()
        self._show_current_card()

        logger.info("Today queue loaded", extra={"context": {"count": len(queue)}})

    def start_processing(self) -> None:
        """Start card processing loop."""
        self._queue_index = 0
        self._show_current_card()

    def next_card(self) -> None:
        """Move to next card in queue."""
        if self._queue_index < len(self._queue) - 1:
            self._queue_index += 1
            self._show_current_card()
            self._update_progress()
        else:
            self._card.clear()
            self._status_var.set("Queue complete. Nice work.")

    def show_morning_brief(self) -> None:
        """Display morning brief dialog."""
        from src.gui.dialogs.morning_brief import MorningBriefDialog

        # Generate brief content
        counts = self.db.get_population_counts()
        engaged = counts.get(Population.ENGAGED, 0)
        unengaged = counts.get(Population.UNENGAGED, 0)
        broken = counts.get(Population.BROKEN, 0)
        brief = (
            f"Pipeline: {engaged} engaged, {unengaged} unengaged, {broken} broken\n"
            f"Today's queue: {len(self._queue)} cards to process"
        )

        dialog = MorningBriefDialog(self.frame, brief, on_ready=self.start_processing)
        dialog.show()

    # ------------------------------------------------------------------
    # Card display
    # ------------------------------------------------------------------

    def _show_current_card(self) -> None:
        """Display the prospect at the current queue index."""
        if not self._queue or self._queue_index >= len(self._queue):
            self._card.clear()
            self._status_var.set("No cards in queue.")
            return

        p = self._queue[self._queue_index]
        company = self.db.get_company(p.company_id)
        activities = self.db.get_activities(p.id, limit=10) if p.id else []
        intel = self.db.get_intel_nuggets(p.id) if p.id else []

        from src.db.models import Company

        self._card.set_prospect(
            p,
            company or Company(id=0, name="Unknown", name_normalized="unknown"),
            activities,
            intel,
        )
        self._status_var.set(f"Card {self._queue_index + 1} of {len(self._queue)}")

    def _update_progress(self) -> None:
        """Update progress bar and queue label."""
        total = len(self._queue)
        self._queue_label.configure(text=f"{self._queue_index}/{total}")
        if total > 0:
            self._progress["maximum"] = total
            self._progress["value"] = self._queue_index
        else:
            self._progress["value"] = 0

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _skip(self) -> None:
        """Skip current card."""
        self.next_card()

    def _defer(self) -> None:
        """Defer current card (move to end of queue)."""
        if not self._queue or self._queue_index >= len(self._queue):
            return
        card = self._queue.pop(self._queue_index)
        self._queue.append(card)
        self._show_current_card()
        self._status_var.set("Card deferred to end of queue.")

    def _deep_dive(self) -> None:
        """Toggle deep dive view on current card."""
        if self._card._view_mode == "deep":
            self._card.set_view_mode("glance")
        else:
            self._card.set_view_mode("deep")

    def _call_mode(self) -> None:
        """Toggle call mode on current card."""
        if self._card._view_mode == "call":
            self._card.exit_call_mode()
        else:
            self._card.enter_call_mode()
