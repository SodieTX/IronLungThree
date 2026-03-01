"""Today tab - Morning brief and card processing.

Primary work surface. Queue loads at morning brief start.
Cards display one at a time. User disposes each card, then next.
"""

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import (
    Activity,
    ActivityType,
    Company,
    Prospect,
)
from src.engine.cadence import get_todays_queue
from src.gui.cards import ProspectCard
from src.gui.dialogs.morning_brief import MorningBriefDialog
from src.gui.dialogs.quick_action import QuickActionDialog
from src.gui.tabs import TabBase
from src.gui.theme import COLORS, FONTS

logger = get_logger(__name__)


class TodayTab(TabBase):
    """Today tab with queue processing."""

    def __init__(self, parent: tk.Widget, db: Database):
        super().__init__(parent, db)
        self._queue: list[Prospect] = []
        self._queue_index: int = 0
        self._card: Optional[ProspectCard] = None
        self._card_frame: Optional[tk.Frame] = None
        self._status_label: Optional[tk.Label] = None
        self._queue_label: Optional[tk.Label] = None
        self._action_frame: Optional[tk.Frame] = None
        self._notes_text: Optional[tk.Text] = None
        self._search_var = tk.StringVar()
        self._brief_shown = False
        self._onboarding_frame: Optional[tk.Frame] = None
        self._create_ui()

    def _create_ui(self) -> None:
        """Create the Today tab UI."""
        if not self.frame:
            return

        # Top bar: queue info + search + brief button
        top = ttk.Frame(self.frame)
        top.pack(fill=tk.X, padx=8, pady=8)

        self._queue_label = tk.Label(
            top,
            text="Queue: 0 cards",
            font=FONTS["large"],
            bg=COLORS["bg"],
            fg=COLORS["fg"],
        )
        self._queue_label.pack(side=tk.LEFT, padx=8)

        # Quick search (Step 2.12)
        ttk.Label(top, text="Search:").pack(side=tk.LEFT, padx=(16, 4))
        search_entry = ttk.Entry(top, textvariable=self._search_var, width=24)
        search_entry.pack(side=tk.LEFT)
        search_entry.bind("<Return>", lambda e: self._quick_search())
        ttk.Button(top, text="Find", command=self._quick_search).pack(side=tk.LEFT, padx=4)

        # Re-read brief button
        ttk.Button(top, text="Today's Brief", command=self.show_morning_brief).pack(
            side=tk.RIGHT, padx=8
        )

        # Main content: card in center
        self._card_frame = tk.Frame(self.frame, bg=COLORS["bg"])
        self._card_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)

        # Action button bar (below the card)
        self._action_frame = tk.Frame(self._card_frame, bg=COLORS["bg"])
        # Starts hidden — built dynamically when a card is shown

        # Empty state message
        self._status_label = tk.Label(
            self._card_frame,
            text="No cards queued.\nClick 'Today's Brief' to load today's queue.",
            font=FONTS["large"],
            bg=COLORS["bg"],
            fg=COLORS["muted"],
        )
        self._status_label.pack(expand=True)

        # Check if we should show onboarding instead
        self._check_empty_state()

    def _check_empty_state(self) -> None:
        """If database is empty, show onboarding welcome instead of dead queue."""
        if not self._card_frame:
            return

        try:
            pop_counts = self.db.get_population_counts()
            total = sum(pop_counts.values())
        except Exception:
            total = 0

        if total > 0:
            # Database has data — make sure we're showing the normal UI
            if self._onboarding_frame is not None:
                self._onboarding_frame.destroy()
                self._onboarding_frame = None
                if self._status_label:
                    self._status_label.pack(expand=True)
                if self._action_frame:
                    self._action_frame.pack(fill=tk.X, padx=16, pady=(0, 8))
            return

        # Database is empty — hide the normal status label and action bar
        if self._status_label:
            self._status_label.pack_forget()
        if self._action_frame:
            self._action_frame.pack_forget()

        # Don't rebuild if already showing
        if self._onboarding_frame is not None:
            return

        self._onboarding_frame = tk.Frame(self._card_frame, bg=COLORS["bg"])
        self._onboarding_frame.pack(expand=True)

        # Welcome header
        tk.Label(
            self._onboarding_frame,
            text="Welcome to IronLung 3.",
            font=("Segoe UI", 20, "bold"),
            bg=COLORS["bg"],
            fg=COLORS["fg"],
        ).pack(pady=(40, 8))

        tk.Label(
            self._onboarding_frame,
            text="Your pipeline is empty. Let's get it loaded.",
            font=("Segoe UI", 13),
            bg=COLORS["bg"],
            fg=COLORS["muted"],
        ).pack(pady=(0, 32))

        # Action buttons frame
        actions = tk.Frame(self._onboarding_frame, bg=COLORS["bg"])
        actions.pack()

        # Import button (primary action)
        import_btn = tk.Button(
            actions,
            text="  ①  Import Contacts  ",
            font=("Segoe UI", 13, "bold"),
            bg=COLORS["accent"],
            fg="#ffffff",
            activebackground="#0052a3",
            activeforeground="#ffffff",
            relief="flat",
            cursor="hand2",
            padx=24,
            pady=12,
            command=self._go_to_import,
        )
        import_btn.pack(pady=8)

        tk.Label(
            actions,
            text="Load a CSV or Excel file to populate your pipeline",
            font=("Segoe UI", 10),
            bg=COLORS["bg"],
            fg=COLORS["muted"],
        ).pack(pady=(0, 20))

        # Sync from Trello button
        trello_btn = tk.Button(
            actions,
            text="  ②  Sync from Trello  ",
            font=("Segoe UI", 11),
            bg=COLORS["bg_alt"],
            fg=COLORS["fg"],
            activebackground=COLORS["bg"],
            activeforeground=COLORS["fg"],
            relief="solid",
            cursor="hand2",
            padx=20,
            pady=8,
            command=self._sync_from_trello,
        )
        trello_btn.pack(pady=4)

        tk.Label(
            actions,
            text="Pull cards from your Trello board into the pipeline",
            font=("Segoe UI", 10),
            bg=COLORS["bg"],
            fg=COLORS["muted"],
        ).pack(pady=(0, 8))

        # Settings button (tertiary action)
        settings_btn = tk.Button(
            actions,
            text="  ③  Configure Services  ",
            font=("Segoe UI", 11),
            bg=COLORS["bg_alt"],
            fg=COLORS["fg"],
            activebackground=COLORS["bg"],
            activeforeground=COLORS["fg"],
            relief="solid",
            cursor="hand2",
            padx=20,
            pady=8,
            command=self._go_to_settings,
        )
        settings_btn.pack(pady=4)

        tk.Label(
            actions,
            text="Set up Outlook, Claude AI, and other integrations",
            font=("Segoe UI", 10),
            bg=COLORS["bg"],
            fg=COLORS["muted"],
        ).pack(pady=(0, 32))

        # Bottom note
        tk.Label(
            self._onboarding_frame,
            text="Once you have prospects, this tab becomes your daily command center.",
            font=("Segoe UI", 10, "italic"),
            bg=COLORS["bg"],
            fg=COLORS["muted"],
        ).pack()

    def _go_to_import(self) -> None:
        """Navigate to the Import tab."""
        if self.app:
            self.app.switch_to_tab("Import")

    def _sync_from_trello(self) -> None:
        """Run Trello sync. refresh_data_tabs updates the empty state."""
        if self.app:
            self.app.run_trello_sync(parent=self.frame)

    def _go_to_settings(self) -> None:
        """Navigate to the Settings tab."""
        if self.app:
            self.app.switch_to_tab("Settings")

    def refresh(self) -> None:
        """Reload queue from database."""
        self._queue = get_todays_queue(self.db)
        self._queue_index = 0
        self._update_queue_label()
        self._show_current_card()

    def on_activate(self) -> None:
        """Called when this tab becomes visible."""
        # Check if database is empty — if so, show onboarding (not the brief)
        try:
            pop_counts = self.db.get_population_counts()
            total = sum(pop_counts.values())
        except Exception:
            total = 0

        if total == 0:
            # Database empty — show onboarding, not the brief
            self._check_empty_state()
            return

        # Database has data — tear down onboarding if present
        self._check_empty_state()

        if not self._brief_shown:
            self._brief_shown = True
            self.refresh()
            self.show_morning_brief()
        else:
            self._update_queue_label()

    def show_morning_brief(self) -> None:
        """Display morning brief dialog."""
        if not self.frame:
            return

        try:
            from src.content.morning_brief import generate_morning_brief

            brief = generate_morning_brief(self.db)
            dialog = MorningBriefDialog(self.frame, brief.full_text, on_ready=self.start_processing)
            dialog.show()
        except Exception as e:
            logger.error(f"Failed to generate morning brief: {e}")
            self.start_processing()

    def start_processing(self) -> None:
        """Start card processing loop."""
        self._queue = get_todays_queue(self.db)
        self._queue_index = 0
        self._update_queue_label()
        self._show_current_card()
        logger.info(f"Processing started: {len(self._queue)} cards in queue")

    def next_card(self) -> None:
        """Move to next card in queue."""
        # Save any notes for the current card
        self._save_current_notes()

        self._queue_index += 1
        if self._queue_index >= len(self._queue):
            self._show_queue_complete()
            return
        self._update_queue_label()
        self._show_current_card()

    def _show_current_card(self) -> None:
        """Display the current card from the queue.

        This is the core card renderer. It:
        1. Clears any existing card
        2. Checks for empty/complete states
        3. Loads full prospect data (company, activities, intel, contacts)
        4. Creates a ProspectCard and wires its callbacks
        5. Updates Anne's context so dictation knows which prospect is active
        6. Builds the action button bar below the card
        """
        if not self._card_frame:
            return

        # Clear existing card
        if self._card:
            self._card.destroy()
            self._card = None

        # Clear action frame contents
        if self._action_frame:
            for child in self._action_frame.winfo_children():
                child.destroy()

        if self._status_label:
            self._status_label.pack_forget()

        # --- Check for empty / end-of-queue states ---
        if not self._queue or self._queue_index >= len(self._queue):
            # Clear anne context — no active prospect
            if self.app:
                self.app.set_current_prospect(None)

            if self._action_frame:
                self._action_frame.pack_forget()

            if self._status_label:
                try:
                    from src.db.models import Population

                    pop_counts = self.db.get_population_counts()
                    broken = pop_counts.get(Population.BROKEN, 0)
                    parked = pop_counts.get(Population.PARKED, 0)
                    total = sum(pop_counts.values())
                    if total > 0 and broken > 0 and broken == total:
                        msg = (
                            f"You have {broken} contacts but they are all 'Broken'\n"
                            "(missing email or phone).\n\n"
                            "Go to the Broken tab to fix them,\n"
                            "or import new contacts from the Import tab."
                        )
                    elif total > 0 and parked > 0:
                        msg = (
                            "No cards due today.\n\n"
                            f"You have {parked} parked contacts waiting.\n"
                            "Check the Pipeline tab for your full list."
                        )
                    elif total > 0:
                        msg = "No cards due today.\n" "Check the Pipeline tab for your full list."
                    else:
                        msg = "No cards queued.\n" "Click 'Today's Brief' to load today's queue."
                except Exception:
                    msg = "No cards in queue."
                self._status_label.config(text=msg)
                self._status_label.pack(expand=True)

            # Also check empty state (onboarding)
            self._check_empty_state()
            return

        # --- We have a card to show ---
        prospect = self._queue[self._queue_index]

        # Load full data for the card
        company = self.db.get_company(prospect.company_id) if prospect.company_id else None
        if company is None:
            company = Company(name="Unknown", name_normalized="unknown")

        activities = self.db.get_activities(prospect.id, limit=20) if prospect.id else []
        intel = self.db.get_intel_nuggets(prospect.id) if prospect.id else []
        contact_methods = self.db.get_contact_methods(prospect.id) if prospect.id else []

        # Count other contacts at same company
        company_contacts = 0
        if prospect.company_id:
            others = self.db.get_prospects(company_id=prospect.company_id, limit=100)
            company_contacts = max(0, len(others) - 1)

        # Create and configure the card
        self._card = ProspectCard(
            self._card_frame,
            on_dial=self._on_card_dial,
        )
        self._card.set_prospect(
            prospect=prospect,
            company=company,
            activities=activities,
            intel=intel,
            contact_methods=contact_methods,
            company_contacts=company_contacts,
        )
        self._card.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # *** CRITICAL: Update Anne's context ***
        if self.app and prospect.id:
            self.app.set_current_prospect(prospect.id)

        # Clear notes field
        if self._notes_text:
            self._notes_text.delete("1.0", tk.END)

        # Build action buttons
        self._build_action_bar(prospect, contact_methods)

        logger.debug(
            f"Showing card {self._queue_index + 1}/{len(self._queue)}: "
            f"{prospect.first_name} {prospect.last_name}"
        )

    def _show_queue_complete(self) -> None:
        """Show queue complete message with end-of-day summary."""
        if self._card:
            self._card.destroy()
            self._card = None

        if self._card_frame:
            # Show "queue complete" message in the card area
            tk.Label(
                self._card_frame,
                text="Queue complete for today!",
                font=("Segoe UI", 16, "bold"),
                bg=COLORS["bg"],
                fg=COLORS["accent"],
            ).pack(expand=True, pady=40)

        if self._status_label:
            # Generate EOD summary
            try:
                from src.content.eod_summary import generate_eod_summary

                eod = generate_eod_summary(self.db)
                self._status_label.config(
                    text=eod.full_text,
                    justify=tk.LEFT,
                    anchor="nw",
                )
            except Exception as e:
                logger.warning(f"EOD summary failed: {e}")
                self._status_label.config(
                    text="Queue complete! Great work.\n\n" "Check the Calendar or Pipeline tabs."
                )
            self._status_label.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)

        self._update_queue_label()

        # Trigger EOD summary dialog after a brief delay
        try:
            if self.app and hasattr(self.app, "_show_eod_summary"):
                if self.frame:
                    self.frame.after(1500, self.app._show_eod_summary)
            else:
                # Reach through to dialog directly
                from src.gui.dialogs.eod_dialog import EODSummaryDialog

                if self.frame:
                    self.frame.after(
                        1500,
                        lambda: EODSummaryDialog(self.frame, self.db).show(),
                    )
        except Exception as e:
            logger.warning(f"Failed to trigger EOD from queue empty: {e}")

    def _update_queue_label(self) -> None:
        """Update the queue position label."""
        if not self._queue_label:
            return
        total = len(self._queue)
        current = min(self._queue_index + 1, total)
        self._queue_label.config(text=f"Queue: {current} / {total} cards")

    def _save_current_notes(self) -> None:
        """Save notes for the current card if any were entered."""
        if not self._notes_text:
            return
        notes = self._notes_text.get("1.0", tk.END).strip()
        if not notes:
            return

        if self._queue and self._queue_index < len(self._queue):
            prospect = self._queue[self._queue_index]
            if prospect.id:
                activity = Activity(
                    prospect_id=prospect.id,
                    activity_type=ActivityType.NOTE,
                    notes=notes,
                    created_by="user",
                )
                self.db.create_activity(activity)
                logger.info(f"Notes saved for prospect {prospect.id}")

    def _quick_action(self) -> None:
        """Open quick action dialog for current card."""
        if not self._queue or self._queue_index >= len(self._queue):
            return
        prospect = self._queue[self._queue_index]
        if not prospect.id or not self.frame:
            return

        dialog = QuickActionDialog(self.frame, prospect.id, db=self.db)
        if dialog.show():
            self.next_card()

    def _toggle_deep(self) -> None:
        """Toggle between glance and deep dive view."""
        if not self._card:
            return
        if self._card._view_mode == "deep":
            self._card.set_view_mode("glance")
        else:
            self._card.set_view_mode("deep")

    def _edit_prospect(self) -> None:
        """Open edit dialog for current card."""
        if not self._queue or self._queue_index >= len(self._queue):
            return
        prospect = self._queue[self._queue_index]
        if not prospect.id or not self.frame:
            return

        from src.gui.dialogs.edit_prospect import EditProspectDialog

        dialog = EditProspectDialog(self.frame, prospect)
        if dialog.show():
            updated = dialog.get_updated_prospect()
            self.db.update_prospect(updated)
            self._show_current_card()  # Refresh the card

    def _skip_card(self) -> None:
        """Skip current card without any action."""
        if not self._queue or self._queue_index >= len(self._queue):
            return
        prospect = self._queue[self._queue_index]
        if prospect.id:
            activity = Activity(
                prospect_id=prospect.id,
                activity_type=ActivityType.SKIP,
                notes="Skipped during queue processing",
                created_by="user",
            )
            self.db.create_activity(activity)
        self.next_card()

    def _build_action_bar(
        self,
        prospect: Prospect,
        contact_methods: list,
    ) -> None:
        """Build the action button bar below the current card.

        Provides one-click actions so Jeff doesn't have to type everything.
        Buttons: Skip | Call | Email | Park | Deep Dive | Quick Action
        """
        if not self._action_frame:
            # Create the action frame if it doesn't exist yet
            self._action_frame = tk.Frame(self._card_frame, bg=COLORS["bg"])

        # Clear any existing buttons
        for child in self._action_frame.winfo_children():
            child.destroy()

        # Ensure it's visible
        self._action_frame.pack(fill=tk.X, padx=16, pady=(0, 8))

        # --- Button definitions ---
        btn_style: dict[str, Any] = {
            "font": ("Segoe UI", 10),
            "bg": COLORS["bg_alt"],
            "fg": COLORS["fg"],
            "activebackground": COLORS["bg"],
            "activeforeground": COLORS["fg"],
            "relief": "flat",
            "cursor": "hand2",
            "padx": 12,
            "pady": 6,
        }

        # Skip
        tk.Button(
            self._action_frame,
            text="⏭ Skip",
            command=self._skip_card,
            **btn_style,
        ).pack(side=tk.LEFT, padx=2)

        # Call (only if phone exists)
        has_phone = any(m.type.value == "phone" for m in contact_methods)
        if has_phone:
            call_btn = tk.Button(
                self._action_frame,
                text="📞 Call",
                command=lambda: self._on_card_dial(prospect),
                bg=COLORS["accent"],
                fg="#ffffff",
                activebackground="#0052a3",
                activeforeground="#ffffff",
                font=("Segoe UI", 10, "bold"),
                relief="flat",
                cursor="hand2",
                padx=12,
                pady=6,
            )
            call_btn.pack(side=tk.LEFT, padx=2)

        # Email (only if email exists)
        has_email = any(m.type.value == "email" for m in contact_methods)
        if has_email:
            tk.Button(
                self._action_frame,
                text="✉️ Email",
                command=self._trigger_email,
                **btn_style,
            ).pack(side=tk.LEFT, padx=2)

        # Park
        tk.Button(
            self._action_frame,
            text="🅿️ Park",
            command=self._trigger_park,
            **btn_style,
        ).pack(side=tk.LEFT, padx=2)

        # Deep Dive toggle
        tk.Button(
            self._action_frame,
            text="🔍 Deep Dive",
            command=self._toggle_deep,
            **btn_style,
        ).pack(side=tk.LEFT, padx=2)

        # Quick Action (edit, move, etc.)
        tk.Button(
            self._action_frame,
            text="⚡ Actions",
            command=self._quick_action,
            **btn_style,
        ).pack(side=tk.LEFT, padx=2)

        # Right side: queue position indicator
        pos_text = f"{self._queue_index + 1} of {len(self._queue)}"
        tk.Label(
            self._action_frame,
            text=pos_text,
            font=("Segoe UI", 9),
            bg=COLORS["bg"],
            fg=COLORS["muted"],
        ).pack(side=tk.RIGHT, padx=8)

    def _on_card_dial(self, prospect: Optional[Prospect] = None) -> None:
        """Handle dial button or phone label click on card.

        Fires Bria dialer and switches card to call mode.
        """
        if prospect is None and self._queue and self._queue_index < len(self._queue):
            prospect = self._queue[self._queue_index]
        if not prospect or not prospect.id:
            return

        from src.integrations.bria import BriaDialer

        contact_methods = self.db.get_contact_methods(prospect.id)
        phone = next(
            (m.value for m in contact_methods if m.type.value == "phone"),
            None,
        )
        if not phone:
            messagebox.showinfo("No Phone", "No phone number on file.")
            return

        dialer = BriaDialer()
        dialed = dialer.dial(phone)

        # Switch to call mode on the card
        if self._card:
            self._card.enter_call_mode()

        if not dialed:
            messagebox.showinfo(
                "Copied",
                f"{phone} copied to clipboard.\n(Bria not detected)",
            )

    def _trigger_email(self) -> None:
        """Trigger email composition via dictation bar."""
        if self.app and hasattr(self.app, "_dictation_bar") and self.app._dictation_bar:
            bar = self.app._dictation_bar
            bar.focus_input()
            bar._entry.delete(0, tk.END)
            bar._entry.insert(0, "send him an email")
            bar._has_placeholder = False
            bar._entry.configure(foreground="black")
            bar._entry.icursor(tk.END)

    def _trigger_park(self) -> None:
        """Trigger park via dictation bar."""
        if self.app and hasattr(self.app, "_dictation_bar") and self.app._dictation_bar:
            bar = self.app._dictation_bar
            bar.focus_input()
            bar._entry.delete(0, tk.END)
            bar._entry.insert(0, "park him until ")
            bar._has_placeholder = False
            bar._entry.configure(foreground="black")
            bar._entry.icursor(tk.END)

    def _defer_card(self) -> None:
        """Defer current card to the end of the queue."""
        if not self._queue or self._queue_index >= len(self._queue):
            return

        prospect = self._queue[self._queue_index]

        # Move the prospect to the end of the queue
        self._queue.pop(self._queue_index)
        self._queue.append(prospect)

        # Don't increment index — the next card is now at current index
        self._update_queue_label()
        self._show_current_card()
        logger.info(f"Deferred prospect {prospect.id} to end of queue")

    def _quick_search(self) -> None:
        """Quick search for a prospect by name."""
        query = self._search_var.get().strip()
        if not query or not self.frame:
            return

        results = self.db.get_prospects(search_query=query, limit=10)
        if not results:
            messagebox.showinfo(
                "Search", f"No prospects found for '{query}'", parent=self.frame.winfo_toplevel()
            )
            return

        if len(results) == 1:
            # Single result — show it directly
            prospect = results[0]
            self._show_search_result(prospect)
        else:
            # Multiple results — show picker
            self._show_search_picker(results)

    def _show_search_result(self, prospect: Prospect) -> None:
        """Show a single search result in a detail dialog."""
        if not self.frame:
            return

        from src.gui.dialogs.edit_prospect import EditProspectDialog

        dialog = EditProspectDialog(self.frame, prospect)
        dialog.show()

    def _show_search_picker(self, results: list[Prospect]) -> None:
        """Show a picker dialog for multiple search results."""
        if not self.frame:
            return

        dialog = tk.Toplevel(self.frame)
        dialog.title("Search Results")
        dialog.geometry("400x300")
        dialog.transient(self.frame.winfo_toplevel())
        dialog.grab_set()

        tree = ttk.Treeview(
            dialog, columns=("ID", "Name", "Population"), show="headings", selectmode="browse"
        )
        tree.heading("ID", text="ID")
        tree.heading("Name", text="Name")
        tree.heading("Population", text="Population")
        tree.column("ID", width=50)
        tree.column("Name", width=200)
        tree.column("Population", width=120)

        for p in results:
            pop = p.population.value if p.population else ""
            tree.insert("", tk.END, values=(p.id, p.full_name, pop))

        tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        def on_select(event: object) -> None:
            sel = tree.selection()
            if sel:
                item = tree.item(sel[0])
                pid = int(item["values"][0])
                prospect = self.db.get_prospect(pid)
                dialog.destroy()
                if prospect:
                    self._show_search_result(prospect)

        tree.bind("<Double-Button-1>", on_select)
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=8)
