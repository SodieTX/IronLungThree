"""Main application window."""

import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, ttk
from typing import Any, Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import Activity, ActivityOutcome, ActivityType

logger = get_logger(__name__)


class IronLungApp:
    """Main application window."""

    def __init__(self, db: Database, seed_status: str = ""):
        self.db = db
        self._seed_status = seed_status
        self.root: Optional[tk.Tk] = None
        self._notebook: Optional[ttk.Notebook] = None
        self._today_tab: Any = None
        self._import_tab: Any = None
        self._pipeline_tab: Any = None
        self._calendar_tab: Any = None
        self._demos_tab: Any = None
        self._broken_tab: Any = None
        self._troubled_tab: Any = None
        self._settings_tab: Any = None
        self._status_label: Optional[ttk.Label] = None
        self._dictation_bar: Any = None
        self._anne: Any = None
        self._anne_context: Any = None
        self._pending_actions: list[dict] = []
        self._pending_disposition: Optional[str] = None
        self._undo_stack: list[dict] = []

    def run(self) -> None:
        """Start the application."""
        self._create_window()
        self._create_tabs()
        self._create_dictation_bar()
        self._create_status_bar()
        self._bind_shortcuts()
        self._init_anne()
        logger.info("IronLung 3 GUI launched")
        if self.root:
            # Schedule initial tab activation after the event loop starts.
            # The <<NotebookTabChanged>> event fires synchronously when the
            # first tab is added to the notebook, BEFORE the handler is bound,
            # so the Today tab's on_activate() never gets called on startup.
            self.root.after_idle(self._activate_initial_tab)
            # Show seed failure warning after event loop starts
            if self._seed_status:
                self.root.after(200, self._show_seed_warning)
            self.root.mainloop()

    def _create_window(self) -> None:
        """Create main window."""
        self.root = tk.Tk()
        self.root.title("IronLung 3")
        self.root.geometry("1200x800")
        self.root.minsize(800, 600)

        from src.gui.theme import apply_theme

        apply_theme(self.root)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        logger.info("Main window created")

    def _create_tabs(self) -> None:
        """Create tab notebook."""
        if not self.root:
            return
        self._notebook = ttk.Notebook(self.root)
        self._notebook.pack(fill=tk.BOTH, expand=True, padx=4, pady=(4, 0))

        # Today tab (primary work surface)
        from src.gui.tabs.today import TodayTab

        today_frame: tk.Widget = ttk.Frame(self._notebook)
        today_tab = TodayTab(today_frame, self.db)
        today_tab.frame = today_frame  # type: ignore[assignment]
        today_tab.app = self
        self._notebook.add(today_frame, text="Today")
        self._today_tab = today_tab

        # Import tab
        from src.gui.tabs.import_tab import ImportTab

        import_frame: tk.Widget = ttk.Frame(self._notebook)
        import_tab = ImportTab(import_frame, self.db)
        import_tab.frame = import_frame  # type: ignore[assignment]
        import_tab.app = self
        self._notebook.add(import_frame, text="Import")
        self._import_tab = import_tab

        # Pipeline tab
        from src.gui.tabs.pipeline import PipelineTab

        pipeline_frame: tk.Widget = ttk.Frame(self._notebook)
        pipeline_tab = PipelineTab(pipeline_frame, self.db)
        pipeline_tab.frame = pipeline_frame  # type: ignore[assignment]
        pipeline_tab.app = self
        self._notebook.add(pipeline_frame, text="Pipeline")
        self._pipeline_tab = pipeline_tab

        # Calendar tab
        from src.gui.tabs.calendar import CalendarTab

        calendar_frame: tk.Widget = ttk.Frame(self._notebook)
        calendar_tab = CalendarTab(calendar_frame, self.db)
        calendar_tab.frame = calendar_frame  # type: ignore[assignment]
        calendar_tab.app = self
        self._notebook.add(calendar_frame, text="Calendar")
        self._calendar_tab = calendar_tab

        # Demos tab
        from src.gui.tabs.demos import DemosTab

        demos_frame: tk.Widget = ttk.Frame(self._notebook)
        demos_tab = DemosTab(demos_frame, self.db)
        demos_tab.frame = demos_frame  # type: ignore[assignment]
        demos_tab.app = self
        self._notebook.add(demos_frame, text="Demos")
        self._demos_tab = demos_tab

        # Broken tab
        from src.gui.tabs.broken import BrokenTab

        broken_frame: tk.Widget = ttk.Frame(self._notebook)
        broken_tab = BrokenTab(broken_frame, self.db)
        broken_tab.frame = broken_frame  # type: ignore[assignment]
        broken_tab.app = self
        self._notebook.add(broken_frame, text="Broken")
        self._broken_tab = broken_tab

        # Troubled tab
        from src.gui.tabs.troubled import TroubledTab

        troubled_frame: tk.Widget = ttk.Frame(self._notebook)
        troubled_tab = TroubledTab(troubled_frame, self.db)
        troubled_tab.frame = troubled_frame  # type: ignore[assignment]
        troubled_tab.app = self
        self._notebook.add(troubled_frame, text="Troubled")
        self._troubled_tab = troubled_tab

        # Settings tab
        from src.gui.tabs.settings import SettingsTab

        settings_frame: tk.Widget = ttk.Frame(self._notebook)
        settings_tab = SettingsTab(settings_frame, self.db)
        settings_tab.frame = settings_frame  # type: ignore[assignment]
        settings_tab.app = self
        self._notebook.add(settings_frame, text="Settings")
        self._settings_tab = settings_tab

        # Bind tab change event
        self._notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        logger.info(
            "Tab notebook created with Today, Import, Pipeline, Calendar, "
            "Demos, Broken, Troubled, and Settings tabs"
        )

    def _create_dictation_bar(self) -> None:
        """Create the dictation bar (Anne's input interface)."""
        if not self.root:
            return
        from src.gui.dictation_bar import DictationBar

        self._dictation_bar = DictationBar(
            self.root,
            on_submit=self._on_dictation_submit,
        )
        self._dictation_bar.pack(fill=tk.X, side=tk.BOTTOM, before=None)
        logger.info("Dictation bar created")

    def _init_anne(self) -> None:
        """Initialize Anne (conversational AI)."""
        try:
            from src.ai.anne import Anne, ConversationContext

            self._anne = Anne(self.db)
            self._anne_context = ConversationContext()

            if not self._anne.is_available():
                if self._dictation_bar:
                    self._dictation_bar.set_manual_mode(True)
                logger.info("Anne offline — manual mode active")
            else:
                logger.info("Anne online")
        except Exception as e:
            logger.warning(f"Failed to initialize Anne: {e}")

    def set_current_prospect(self, prospect_id: Optional[int]) -> None:
        """Update Anne's conversation context with the current prospect.

        Called by TodayTab whenever a new card is displayed, so the
        dictation bar → Anne → execute pipeline always knows which
        prospect we're talking about.
        """
        if self._anne_context:
            self._anne_context.current_prospect_id = prospect_id
            logger.debug(f"Anne context updated: prospect_id={prospect_id}")

    def _on_dictation_submit(self, text: str) -> None:
        """Handle dictation bar input.

        This is the central nervous system of card processing:
        1. User types/dictates into the bar
        2. Anne parses intent and returns response + suggested actions
        3. Non-confirmation actions auto-execute against current prospect
        4. Navigation actions (skip/defer) advance the card
        5. Special actions (dial, send_email) trigger integrations
        6. Card advances after successful processing
        """
        if not self._anne or not self._dictation_bar:
            return

        # --- Manual mode: bypass Anne entirely ---
        if self._dictation_bar.is_manual_mode:
            self._handle_manual_input(text)
            return

        try:
            response = self._anne.respond(text, self._anne_context)
            self._dictation_bar.show_response(response.message)

            # Track conversation history
            self._anne_context.recent_messages.append({"role": "user", "content": text})
            self._anne_context.recent_messages.append(
                {"role": "assistant", "content": response.message}
            )

            if not response.suggested_actions:
                return

            # --- Handle navigation actions (no prospect_id needed) ---
            first_action = response.suggested_actions[0].get("action", "")

            if first_action == "skip":
                if self._today_tab:
                    self._today_tab._skip_card()
                return

            if first_action == "defer":
                if self._today_tab:
                    self._today_tab._defer_card()
                return

            if first_action == "undo":
                self._handle_undo()
                return

            if first_action == "execute_pending":
                # User confirmed a pending action — execute what we stored
                self._execute_pending_actions()
                return

            if first_action == "deep_dive":
                if self._today_tab and self._today_tab._card:
                    self._today_tab._toggle_deep()
                return

            # --- Actions that require a prospect ---
            prospect_id = self._anne_context.current_prospect_id
            if not prospect_id:
                logger.warning("No current prospect — cannot execute actions")
                self._dictation_bar.show_response("No card is active. Load the queue first.")
                return

            # Stamp prospect_id onto every action
            for action in response.suggested_actions:
                action["prospect_id"] = prospect_id

            # --- Confirmation-required actions: store, don't execute ---
            if response.requires_confirmation:
                self._pending_actions = response.suggested_actions
                self._pending_disposition = response.disposition
                return

            # --- Auto-execute non-confirmation actions ---

            # Special: dial → fire Bria + enter call mode
            if first_action == "dial":
                self._handle_dial(prospect_id)
                return

            # Special: send_email → goes through Outlook
            if first_action == "send_email":
                self._handle_send_email(prospect_id, response.suggested_actions[0])
                return

            # Standard actions: execute via Anne, then advance card
            results = self._anne.execute_actions(response.suggested_actions)
            logger.info(f"Actions executed: {results['executed']}, " f"failed: {results['failed']}")

            # Push onto undo stack
            self._push_undo(prospect_id, response.suggested_actions, results)

            # Advance to next card after successful processing
            if results["executed"] and self._today_tab:
                self._today_tab.next_card()

        except Exception as e:
            logger.error(f"Dictation processing failed: {e}")
            self._dictation_bar.show_response(f"Error: {e}")

    def _handle_manual_input(self, text: str) -> None:
        """Handle input when Anne is offline (manual mode).

        Reads the manual dropdown and date field from the dictation bar
        to determine what action to take.
        """
        prospect_id = self._anne_context.current_prospect_id if self._anne_context else None
        if not prospect_id:
            if self._dictation_bar:
                self._dictation_bar.show_response("No card active. Notes need a prospect.")
            return

        bar = self._dictation_bar
        action = bar.manual_action if bar else "note"
        follow_up_str = bar.manual_follow_up_date if bar else ""

        # Map manual action to activity type
        activity_type_map = {
            "note": ActivityType.NOTE,
            "left_voicemail": ActivityType.CALL,
            "no_answer": ActivityType.CALL,
            "spoke_with": ActivityType.CALL,
            "skip": ActivityType.SKIP,
        }

        outcome_map: dict[str, ActivityOutcome] = {
            "left_voicemail": ActivityOutcome.LEFT_VM,
            "no_answer": ActivityOutcome.NO_ANSWER,
            "spoke_with": ActivityOutcome.SPOKE_WITH,
        }

        if action == "skip":
            if self._today_tab:
                self._today_tab._skip_card()
            return

        if action == "park":
            # Park requires a month — use follow_up_str or default to next month
            from src.db.models import Population
            from src.engine.populations import transition_prospect

            prospect = self.db.get_prospect(prospect_id)
            if prospect:
                park_month = follow_up_str or None
                if park_month:
                    prospect.parked_month = park_month
                    self.db.update_prospect(prospect)
                transition_prospect(
                    self.db,
                    prospect_id,
                    Population.PARKED,
                    reason=f"Manual: parked (month={park_month})",
                )
            if bar:
                bar.show_response(f"📦 Parked. Notes: {text[:60]}")
            if self._today_tab:
                self._today_tab.next_card()
            return

        # Log the activity
        act_type = activity_type_map.get(action, ActivityType.NOTE)
        outcome = outcome_map.get(action)

        activity = Activity(
            prospect_id=prospect_id,
            activity_type=act_type,
            outcome=outcome,
            notes=text,
            created_by="user_manual",
        )
        self.db.create_activity(activity)

        # Update attempt count and last_contact_date for call types
        if action in ("left_voicemail", "no_answer", "spoke_with"):
            prospect = self.db.get_prospect(prospect_id)
            if prospect:
                prospect.attempt_count = (prospect.attempt_count or 0) + 1
                prospect.last_contact_date = date.today()
                self.db.update_prospect(prospect)

        # Set follow-up if provided
        if follow_up_str:
            try:
                from src.engine.cadence import set_follow_up

                fu_dt = datetime.fromisoformat(follow_up_str)
                set_follow_up(self.db, prospect_id, fu_dt, reason="Manual follow-up")
                if bar:
                    bar.show_response(f"📝 Logged ({action}). Follow-up: {follow_up_str}")
            except ValueError:
                if bar:
                    bar.show_response(f"📝 Logged ({action}). ⚠️ Invalid date: {follow_up_str}")
        else:
            if bar:
                bar.show_response(f"📝 Logged: {action}. Notes saved.")

        # Advance card
        if self._today_tab:
            self._today_tab.next_card()

        logger.info(f"Manual action '{action}' for prospect {prospect_id}")

    def _handle_dial(self, prospect_id: int) -> None:
        """Handle dial action: fire Bria + switch card to call mode."""
        from src.integrations.bria import BriaDialer

        contact_methods = self.db.get_contact_methods(prospect_id)
        phone = next(
            (m.value for m in contact_methods if m.type.value == "phone"),
            None,
        )
        if not phone:
            if self._dictation_bar:
                self._dictation_bar.show_response("No phone number on file for this prospect.")
            return

        dialer = BriaDialer()
        dialed = dialer.dial(phone)

        # Switch card to call mode
        if self._today_tab and self._today_tab._card:
            self._today_tab._card.enter_call_mode()

        if dialed:
            if self._dictation_bar:
                self._dictation_bar.show_response(
                    f"📞 Dialing {phone}...\n"
                    "Card switched to call mode. Dictate notes as you talk."
                )
        else:
            if self._dictation_bar:
                self._dictation_bar.show_response(
                    f"📋 {phone} copied to clipboard (Bria not available).\n"
                    "Card switched to call mode."
                )

    def _handle_send_email(self, prospect_id: int, action: dict) -> None:
        """Handle email send via Outlook."""
        draft_body = action.get("draft", "")
        if not draft_body:
            if self._dictation_bar:
                self._dictation_bar.show_response("No email draft to send.")
            return

        # Get recipient email
        contact_methods = self.db.get_contact_methods(prospect_id)
        email_addr = next(
            (m.value for m in contact_methods if m.type.value == "email"),
            None,
        )
        if not email_addr:
            if self._dictation_bar:
                self._dictation_bar.show_response("No email address on file for this prospect.")
            return

        # Try Outlook
        try:
            from src.integrations.outlook import OutlookClient

            outlook = OutlookClient()
            if not outlook.is_configured():
                if self._dictation_bar:
                    self._dictation_bar.show_response(
                        "Outlook not configured. Go to Settings to add credentials."
                    )
                return

            prospect = self.db.get_prospect(prospect_id)
            subject = f"Following up — {prospect.first_name if prospect else 'Hello'}"

            outlook.send_email(
                to=email_addr,
                subject=subject,
                body=draft_body,
                html=False,
            )

            # Log the email as an activity
            activity = Activity(
                prospect_id=prospect_id,
                activity_type=ActivityType.EMAIL_SENT,
                email_subject=subject,
                email_body=draft_body[:500],
                notes=f"Email sent to {email_addr}",
                created_by="anne",
            )
            self.db.create_activity(activity)

            if self._dictation_bar:
                self._dictation_bar.show_response(f"✉️ Email sent to {email_addr}.")

            # Advance card
            if self._today_tab:
                self._today_tab.next_card()

        except Exception as e:
            logger.error(f"Email send failed: {e}")
            if self._dictation_bar:
                self._dictation_bar.show_response(f"Email send failed: {e}")

    def _execute_pending_actions(self) -> None:
        """Execute actions that were waiting for user confirmation."""
        if not hasattr(self, "_pending_actions") or not self._pending_actions:
            if self._dictation_bar:
                self._dictation_bar.show_response("Nothing pending to execute.")
            return

        actions = self._pending_actions
        self._pending_actions = []

        prospect_id = self._anne_context.current_prospect_id if self._anne_context else None

        # Check for special actions that need custom handling
        first_action = actions[0].get("action", "") if actions else ""

        if first_action == "send_email" and prospect_id:
            self._handle_send_email(prospect_id, actions[0])
            return

        if first_action == "dial" and prospect_id:
            self._handle_dial(prospect_id)
            return

        # Check for WON disposition — show ClosedWonDialog
        disposition = getattr(self, "_pending_disposition", None)
        if disposition == "WON" and prospect_id:
            self._show_closed_won_dialog(prospect_id, actions)
            return

        # Standard execution
        if self._anne:
            results = self._anne.execute_actions(actions)
            if prospect_id:
                self._push_undo(prospect_id, actions, results)

            executed = ", ".join(results["executed"]) if results["executed"] else "none"
            if self._dictation_bar:
                self._dictation_bar.show_response(f"Done. ({executed})")

            # Advance card after confirmed action
            if results["executed"] and self._today_tab:
                self._today_tab.next_card()

        self._pending_disposition = None

    def _show_closed_won_dialog(self, prospect_id: int, actions: list[dict]) -> None:
        """Show the Closed Won dialog to capture deal details."""
        if not self.root:
            return
        try:
            from src.gui.dialogs.closed_won import ClosedWonDialog

            dialog = ClosedWonDialog(self.root, prospect_id, db=self.db)
            result = dialog.show()
            if result:
                # Dialog handled the DB updates (deal_value, close_date, etc.)
                # Now also execute the population change
                if self._anne:
                    self._anne.execute_actions(actions)
                if self._dictation_bar:
                    self._dictation_bar.show_response("🎉 Deal closed! Congratulations!")
                if self._today_tab:
                    self._today_tab.next_card()
            else:
                if self._dictation_bar:
                    self._dictation_bar.show_response("Closed Won cancelled.")
        except ImportError:
            logger.warning("ClosedWonDialog not available, executing directly")
            if self._anne:
                self._anne.execute_actions(actions)
            if self._today_tab:
                self._today_tab.next_card()

    # ------------------------------------------------------------------
    # UNDO STACK
    # ------------------------------------------------------------------

    def _push_undo(
        self,
        prospect_id: int,
        actions: list[dict],
        results: dict,
    ) -> None:
        """Push an action set onto the undo stack."""
        # Capture the state BEFORE the action so we can restore it
        # For simplicity, we store the prospect snapshot
        prospect = self.db.get_prospect(prospect_id)
        if prospect:
            self._undo_stack.append(
                {
                    "prospect_id": prospect_id,
                    "actions": actions,
                    "results": results,
                    "prospect_snapshot": prospect,
                    "timestamp": datetime.now(),
                }
            )
            # Keep stack manageable
            if len(self._undo_stack) > 20:
                self._undo_stack.pop(0)

    def _handle_undo(self) -> None:
        """Undo the last action by restoring prospect state."""
        if not hasattr(self, "_undo_stack") or not self._undo_stack:
            if self._dictation_bar:
                self._dictation_bar.show_response("Nothing to undo.")
            return

        entry = self._undo_stack.pop()

        # Special case: DNC reversal within grace period
        actions = entry.get("actions", [])
        was_dnc = any(
            a.get("action") == "population_change"
            and a.get("population") == "dead_dnc"
            for a in actions
        )
        if was_dnc:
            try:
                from src.db.models import Population
                from src.engine.populations import can_reverse_dnc, reverse_dnc

                if can_reverse_dnc(self.db, entry["prospect_id"]):
                    snapshot = entry.get("prospect_snapshot")
                    restore_pop = (
                        Population(snapshot.population.value)
                        if snapshot and snapshot.population
                        else Population.UNENGAGED
                    )
                    reverse_dnc(
                        self.db,
                        entry["prospect_id"],
                        restore_to=restore_pop,
                        reason="Undo by user",
                    )
                    self._update_status_bar()
                    if self._dictation_bar:
                        self._dictation_bar.show_response(
                            "DNC reversed within grace period."
                        )
                    if self._today_tab:
                        self._today_tab._queue_index = max(
                            0, self._today_tab._queue_index - 1
                        )
                        self._today_tab._show_current_card()
                        self._today_tab._update_queue_label()
                    return
            except Exception as e:
                logger.warning(f"DNC reversal failed: {e}")

        snapshot = entry.get("prospect_snapshot")
        if snapshot:
            self.db.update_prospect(snapshot)
            if self._dictation_bar:
                self._dictation_bar.show_response(
                    f"↩️ Undone. Restored {snapshot.first_name} {snapshot.last_name} "
                    f"to previous state."
                )
            # Re-show the same card (go back one)
            if self._today_tab:
                self._today_tab._queue_index = max(0, self._today_tab._queue_index - 1)
                self._today_tab._show_current_card()
                self._today_tab._update_queue_label()
        else:
            if self._dictation_bar:
                self._dictation_bar.show_response("Undo failed — no snapshot available.")

    def _create_status_bar(self) -> None:
        """Create status bar."""
        if not self.root:
            return
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self._status_label = ttk.Label(status_frame, text="Ready", anchor=tk.W)
        self._status_label.pack(fill=tk.X, padx=4, pady=2)
        self._update_status_bar()
        logger.info("Status bar created")

    def _bind_shortcuts(self) -> None:
        """Bind keyboard shortcuts.

        Wires all shortcuts defined in shortcuts.py to actual handlers.
        Each handler checks whether the Today tab is active before
        performing card-specific actions.
        """
        if not self.root:
            return

        from src.gui.shortcuts import bind_shortcuts

        handlers = {
            "quick_lookup": self._focus_search,
            "skip": self._shortcut_skip,
            "defer": self._shortcut_defer,
            "undo": lambda: self._handle_undo(),
            "confirm": self._shortcut_confirm,
            "cancel": self._shortcut_cancel,
            "demo_invite": self._shortcut_demo_invite,
            "send_email": self._shortcut_send_email,
            "command_palette": self._shortcut_command_palette,
            "focus_mode": self._shortcut_focus_mode,
        }
        bind_shortcuts(self.root, handlers)
        self.root.bind("<Control-q>", lambda e: self.close())
        self.root.bind("<Control-w>", lambda e: self.close())
        self.root.bind("<Control-e>", lambda e: self._show_eod_summary())
        self.root.bind("<Control-n>", lambda e: self._show_nurture_queue())
        logger.info("Keyboard shortcuts bound")

    def _is_today_active(self) -> bool:
        """Check if Today tab is currently selected."""
        if not self._notebook:
            return False
        try:
            current = self._notebook.index(self._notebook.select())
            return bool(current == 0)  # Today is first tab
        except Exception:
            return False

    def _shortcut_skip(self) -> None:
        """Tab key: skip current card."""
        if self._is_today_active() and self._today_tab:
            self._today_tab._skip_card()

    def _shortcut_defer(self) -> None:
        """Ctrl+D: defer current card to end of queue."""
        if self._is_today_active() and self._today_tab:
            self._today_tab._defer_card()

    def _shortcut_confirm(self) -> None:
        """Enter key: confirm pending action (when not in text entry)."""
        # Only fire if focus is NOT in the dictation bar entry
        if not self.root:
            return
        focused = self.root.focus_get()
        if focused and isinstance(focused, (tk.Entry, tk.Text)):
            return  # Let the widget handle Enter naturally
        self._execute_pending_actions()

    def _shortcut_cancel(self) -> None:
        """Escape key: cancel pending action."""
        if hasattr(self, "_pending_actions"):
            self._pending_actions = []
        if self._dictation_bar:
            self._dictation_bar.clear_response()
            self._dictation_bar.show_response("Cancelled.")

    def _shortcut_demo_invite(self) -> None:
        """Ctrl+M: open demo invite dialog."""
        if not self._is_today_active() or not self._today_tab:
            return
        prospect_id = self._anne_context.current_prospect_id if self._anne_context else None
        if not prospect_id or not self.root:
            return
        try:
            from src.gui.dialogs.demo_invite import DemoInviteDialog

            dialog = DemoInviteDialog(self.root, prospect_id, db=self.db)
            dialog.show()
        except ImportError:
            logger.warning("DemoInviteDialog not available")

    def _shortcut_send_email(self) -> None:
        """Ctrl+E: trigger email composition for current card."""
        if self._dictation_bar and self._is_today_active():
            self._dictation_bar.focus_input()
            # Pre-fill with email command
            self._dictation_bar._entry.delete(0, tk.END)
            self._dictation_bar._entry.insert(0, "send him an email")
            self._dictation_bar._has_placeholder = False
            self._dictation_bar._entry.configure(foreground="black")
            self._dictation_bar._entry.icursor(tk.END)

    def _shortcut_command_palette(self) -> None:
        """Ctrl+K: open command palette."""
        if not self.root:
            return
        try:
            from src.gui.dialogs.command_palette import CommandPalette

            palette = CommandPalette(self.root, db=self.db, app=self)
            palette.show()
        except ImportError:
            logger.warning("CommandPalette not available")

    def _shortcut_focus_mode(self) -> None:
        """Ctrl+Shift+F: toggle focus mode."""
        try:
            from src.gui.adhd.focus import FocusManager

            fm = FocusManager()
            fm.toggle()
        except (ImportError, Exception) as e:
            logger.warning(f"Focus mode unavailable: {e}")

    def _focus_search(self) -> None:
        """Focus the Today tab search field (Ctrl+F)."""
        if self._notebook and self._today_tab:
            self._notebook.select(0)  # Switch to Today tab
            if hasattr(self._today_tab, "_search_var"):
                self._today_tab._search_var.set("")

    def _show_seed_warning(self) -> None:
        """Show a warning dialog when auto-seed failed at startup."""
        from tkinter import messagebox

        if self._seed_status.startswith("seed_error"):
            messagebox.showwarning(
                "Data Loading Issue",
                "IronLung could not auto-load sample data on startup.\n\n"
                f"Details: {self._seed_status}\n\n"
                "You can load data manually from the Import tab,\n"
                "or use Settings → 'Reset & Re-seed Database' to retry.",
            )
        elif self._seed_status == "seed_no_csv":
            messagebox.showwarning(
                "Sample Data Missing",
                "The sample contacts file (data/sample_contacts.csv) was not found.\n\n"
                "You can load your own data from the Import tab.",
            )
        elif self._seed_status in ("seed_empty", "seed_zero"):
            messagebox.showwarning(
                "Data Loading Issue",
                "Auto-seed ran but imported 0 records.\n\n"
                "Try using Settings → 'Reset & Re-seed Database',\n"
                "or load data manually from the Import tab.",
            )

    def _activate_initial_tab(self) -> None:
        """Activate whichever tab is initially selected.

        The <<NotebookTabChanged>> event fires synchronously when the first
        tab is added via notebook.add(), but the Python handler isn't bound
        yet at that point — so the initial activation is missed.  This method
        is scheduled via after_idle() to run once the event loop starts.
        """
        self._on_tab_changed(None)

    def _on_tab_changed(self, event: object) -> None:
        """Handle tab change event."""
        if not self._notebook:
            return
        current_tab = self._notebook.index(self._notebook.select())
        tabs = [
            self._today_tab,
            self._import_tab,
            self._pipeline_tab,
            self._calendar_tab,
            self._demos_tab,
            self._broken_tab,
            self._troubled_tab,
            self._settings_tab,
        ]
        if current_tab < len(tabs) and tabs[current_tab]:
            tabs[current_tab].on_activate()
        self._update_status_bar()

    def _update_status_bar(self) -> None:
        """Update status bar with database statistics and backup info."""
        if not self._status_label:
            return
        try:
            from src.db.models import Population

            pop_counts = self.db.get_population_counts()
            total = sum(pop_counts.values())
            unengaged = pop_counts.get(Population.UNENGAGED, 0)
            engaged = pop_counts.get(Population.ENGAGED, 0)
            status_text = f"{total} prospects | {unengaged} unengaged | {engaged} engaged"

            # Add backup info
            try:
                from datetime import datetime

                from src.db.backup import BackupManager

                backups = BackupManager().list_backups()
                if backups:
                    age = datetime.now() - backups[0].timestamp
                    hours = age.total_seconds() / 3600
                    if hours < 1:
                        backup_str = "Last backup: <1h ago"
                    elif hours < 24:
                        backup_str = f"Last backup: {hours:.0f}h ago"
                    else:
                        days = hours / 24
                        backup_str = f"Last backup: {days:.0f}d ago"
                else:
                    backup_str = "No backups"
                status_text += f" | {backup_str}"
            except Exception:
                pass  # Don't let backup check break the status bar

            self._status_label.config(text=status_text)
        except Exception as e:
            logger.warning(f"Failed to update status bar: {e}")
            self._status_label.config(text="Ready")

    def close(self) -> None:
        """Close application gracefully. Shows EOD summary if cards were worked today."""
        logger.info("Closing IronLung 3...")

        # Show EOD summary if any cards were processed today
        try:
            from src.content.eod_summary import generate_eod_summary

            summary = generate_eod_summary(self.db)
            if summary.cards_processed > 0 and self.root:
                from src.gui.dialogs.eod_dialog import EODSummaryDialog

                dialog = EODSummaryDialog(self.root, self.db)
                dialog.show()
                # Wait for dialog to close before destroying app
                if dialog._dialog:
                    self.root.wait_window(dialog._dialog)
        except Exception as e:
            logger.warning(f"EOD summary failed (non-fatal): {e}")

        self.db.close()
        if self.root:
            self.root.destroy()
            self.root = None
        logger.info("IronLung 3 closed")

    def _show_eod_summary(self) -> None:
        """Manually trigger EOD summary (Ctrl+E)."""
        if not self.root:
            return
        try:
            from src.gui.dialogs.eod_dialog import EODSummaryDialog

            dialog = EODSummaryDialog(self.root, self.db)
            dialog.show()
        except Exception as e:
            logger.warning(f"Failed to show EOD summary: {e}")

    def _show_nurture_queue(self) -> None:
        """Open the nurture email approval queue."""
        if not self.root:
            return
        try:
            from src.gui.dialogs.nurture_queue import NurtureQueueDialog

            dialog = NurtureQueueDialog(self.root, self.db)
            dialog.show()
        except Exception as e:
            logger.warning(f"Failed to open nurture queue: {e}")

    def switch_to_tab(self, tab_name: str) -> None:
        """Switch to a tab by name.

        Args:
            tab_name: One of 'Today', 'Import', 'Pipeline', 'Calendar',
                      'Demos', 'Broken', 'Troubled', 'Settings'
        """
        if not self._notebook:
            return
        for i in range(self._notebook.index("end")):
            if self._notebook.tab(i, "text") == tab_name:
                self._notebook.select(i)
                return
        logger.warning(f"Tab not found: {tab_name}")

    def run_trello_sync(self, parent: Optional[tk.Widget] = None) -> bool:
        """Run Trello-to-pipeline sync. Callable from any tab.

        Returns True if sync completed successfully, False otherwise.
        """
        from src.gui.service_guard import check_service

        if not check_service("trello", parent=parent):
            return False

        try:
            from src.integrations.trello_sync import TrelloPipelineSync

            sync = TrelloPipelineSync(self.db)
            result = sync.sync()
            self.refresh_data_tabs()
            if isinstance(parent, tk.Misc):
                messagebox.showinfo("Trello Sync Complete", result.summary, parent=parent)
            else:
                messagebox.showinfo("Trello Sync Complete", result.summary)
            logger.info(f"Trello sync: {result.created} created, {result.updated} updated")
            return True
        except Exception as e:
            logger.error(f"Trello sync failed: {e}")
            if isinstance(parent, tk.Misc):
                messagebox.showerror("Trello Sync Error", f"Sync failed: {e}", parent=parent)
            else:
                messagebox.showerror("Trello Sync Error", f"Sync failed: {e}")
            return False

    def refresh_data_tabs(self) -> None:
        """Refresh all tabs that display prospect data.

        Call after import, Trello sync, or bulk operations so data
        appears correctly without switching tabs.
        """
        for tab in (
            self._today_tab,
            self._pipeline_tab,
            self._broken_tab,
            self._troubled_tab,
            self._calendar_tab,
            self._demos_tab,
        ):
            if tab and hasattr(tab, "refresh"):
                try:
                    tab.refresh()
                except Exception as e:
                    logger.warning(f"Tab refresh failed: {e}")
