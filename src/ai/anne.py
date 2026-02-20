"""Anne - The conversational AI assistant.

Anne is the product. She:
    - Presents cards with context and recommendations
    - Discusses prospects with Jeff
    - Takes obsessive notes
    - Drafts emails in Jeff's voice
    - Can disagree when warranted
    - Executes after confirmation

Usage:
    from src.ai.anne import Anne

    anne = Anne(db)
    presentation = anne.present_card(prospect_id)
    response = anne.respond(user_input, context)
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

from src.ai.claude_client import ClaudeClientMixin
from src.core.config import CLAUDE_MODEL, get_config
from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import (
    Activity,
    ActivityType,
    AttemptType,
    Company,
    IntelCategory,
    IntelNugget,
    Population,
    Prospect,
)

logger = get_logger(__name__)

# Anne's system prompt — defines her personality and role
_SYSTEM_PROMPT = """\
You are Anne, the AI sales assistant for Jeff Soderstrom at Nexys LLC.
Jeff sells lending technology (loan origination software) to mortgage companies.

Your personality:
- Direct and conversational, never corporate or stiff
- You've done your homework on every card before Jeff sees it
- You can suggest, push back, and even disagree when warranted
- You're obsessive about details — every nugget gets noted
- You care about Jeff's ADHD — keep things focused, one thing at a time

Your rules:
1. Always present the card first: name, company, context, history, your recommendation
2. Never execute without Jeff's explicit confirmation
3. You're allowed to disagree: "Are you sure? He's showing buying signals."
4. Draft emails in Jeff's voice (see style examples if provided)
5. No orphan engaged leads — engaged prospects MUST have a follow-up date
6. DNC is permanent, absolute, no exceptions
7. Keep responses concise — Jeff processes dozens of cards per session

Response format:
- When presenting a card: Give the story, your analysis, and ask what to do
- When responding to input: Acknowledge, state what you'll do, ask for confirmation
- When executing: Confirm what was done, move to next card
"""


@dataclass
class AnneResponse:
    """Anne's response to user input.

    Attributes:
        message: Anne's spoken/displayed message
        suggested_actions: Actions Anne suggests
        requires_confirmation: Whether to wait for confirm
        disposition: Suggested disposition if any
    """

    message: str
    suggested_actions: Optional[list[dict]] = None
    requires_confirmation: bool = False
    disposition: Optional[str] = None


@dataclass
class ConversationContext:
    """Context for Anne's conversation.

    Attributes:
        current_prospect_id: Current card being discussed
        recent_messages: Recent conversation history
        mode: Current mode (processing, copilot, etc.)
    """

    current_prospect_id: Optional[int] = None
    recent_messages: list[dict] = field(default_factory=list)
    mode: str = "processing"


class Anne(ClaudeClientMixin):
    """Anne - The conversational AI assistant."""

    def __init__(self, db: Database):
        """Initialize Anne."""
        self.db = db
        self._config = get_config()
        self._client: Optional[object] = None
        self._pre_generated: dict[int, str] = {}

    def _get_claude_config(self):
        return self._config

    def present_card(self, prospect_id: int) -> str:
        """Generate card presentation with context and recommendation.

        If a pre-generated presentation exists, returns it.
        If Claude API is available, generates via AI.
        Falls back to local-only presentation.
        """
        # Check pre-generated cache
        if prospect_id in self._pre_generated:
            presentation = self._pre_generated.pop(prospect_id)
            return presentation

        # Build context
        context = self._build_prospect_context(prospect_id)
        if not context:
            return "I can't find that prospect."

        # Try AI-enhanced presentation
        if self.is_available():
            try:
                return self._ai_present_card(context)
            except Exception as e:
                logger.warning(f"AI presentation failed, using local: {e}")

        # Local-only fallback
        return self._local_present_card(context)

    def respond(self, user_input: str, context: ConversationContext) -> AnneResponse:
        """Process user input and respond.

        Parses the input, determines intent, and returns Anne's response.
        May suggest actions that require confirmation.
        """
        from src.ai.parser import parse

        parsed = parse(user_input)

        # Handle confirmation/denial
        if parsed.action == "confirm":
            return AnneResponse(
                message="Got it. Executing.",
                suggested_actions=[{"action": "execute_pending"}],
            )

        if parsed.action == "deny":
            return AnneResponse(message="Okay, cancelled. What would you like to do instead?")

        # Handle navigation
        if parsed.action == "skip":
            return AnneResponse(
                message="Skipping. Next card.",
                suggested_actions=[{"action": "skip"}],
            )

        if parsed.action == "undo":
            return AnneResponse(
                message="Undoing last action.",
                suggested_actions=[{"action": "undo"}],
            )

        if parsed.action == "defer":
            return AnneResponse(
                message="Deferred. Moving to end of queue.",
                suggested_actions=[{"action": "defer"}],
            )

        # Handle sales vocab
        if parsed.action == "voicemail":
            return AnneResponse(
                message="Left voicemail. I'll log it and set follow-up. Next card?",
                suggested_actions=[
                    {
                        "action": "log_activity",
                        "type": "voicemail",
                        "outcome": "left_vm",
                    }
                ],
            )

        if parsed.action == "call":
            outcome = parsed.parameters.get("outcome", "no_answer")
            outcome_label = outcome.replace("_", " ")
            return AnneResponse(
                message=f"Call logged: {outcome_label}.",
                suggested_actions=[
                    {
                        "action": "log_activity",
                        "type": "call",
                        "outcome": outcome,
                    }
                ],
            )

        # Handle email action
        if parsed.action == "send_email":
            if self.is_available() and context.current_prospect_id:
                try:
                    draft = self._draft_email(context.current_prospect_id, user_input)
                    return AnneResponse(
                        message=f"Here's the draft:\n\n{draft}\n\nSend it?",
                        suggested_actions=[
                            {
                                "action": "send_email",
                                "draft": draft,
                            }
                        ],
                        requires_confirmation=True,
                    )
                except Exception as e:
                    logger.warning(f"Email draft failed: {e}")
            return AnneResponse(
                message="I'll draft an email. What should it say?",
                requires_confirmation=True,
            )

        # Handle dial
        if parsed.action == "dial":
            return AnneResponse(
                message="Dialing now.",
                suggested_actions=[{"action": "dial"}],
            )

        # Handle park — with potential disagreement
        if parsed.action == "park":
            parked_month = parsed.parameters.get("parked_month")
            if parked_month:
                # Check if Anne should push back
                disagreement = self._should_disagree_with_park(context.current_prospect_id)
                if disagreement:
                    return AnneResponse(
                        message=(
                            f"{disagreement['reason']}\n\n"
                            f"Instead of parking, I'd suggest: {disagreement['alternative']}\n\n"
                            f"Say 'park anyway' to park until {parked_month}, "
                            f"or 'ok' to try my suggestion."
                        ),
                        suggested_actions=[
                            {
                                "action": "park",
                                "parked_month": parked_month,
                            }
                        ],
                        requires_confirmation=True,
                        disposition="OUT",
                    )
                return AnneResponse(
                    message=f"Parking until {parked_month}. Confirm?",
                    suggested_actions=[
                        {
                            "action": "park",
                            "parked_month": parked_month,
                        }
                    ],
                    requires_confirmation=True,
                    disposition="OUT",
                )
            return AnneResponse(
                message="Park until when? Give me a month.",
            )

        # Handle demo scheduling
        if parsed.action == "schedule_demo":
            date_str = str(parsed.date) if parsed.date else "TBD"
            return AnneResponse(
                message=f"Demo scheduled for {date_str}. I'll log it and move to demo_scheduled. Confirm?",
                suggested_actions=[
                    {
                        "action": "schedule_demo",
                        "date": date_str,
                    }
                ],
                requires_confirmation=True,
            )

        # Handle follow-up
        if parsed.action == "set_follow_up":
            fu_date_str = str(parsed.date) if parsed.date else None
            if fu_date_str:
                return AnneResponse(
                    message=f"Follow-up set for {fu_date_str}.",
                    suggested_actions=[
                        {
                            "action": "set_follow_up",
                            "date": fu_date_str,
                        }
                    ],
                )
            return AnneResponse(message="Follow up when? Give me a date.")

        # Handle population change
        if parsed.action == "population_change":
            pop = parsed.parameters.get("population", "")
            if pop == Population.DEAD_DNC.value:
                return AnneResponse(
                    message="Marking as DNC. This is permanent. Are you sure?",
                    suggested_actions=[{"action": "population_change", "population": pop}],
                    requires_confirmation=True,
                    disposition="OUT",
                )
            if pop == Population.ENGAGED.value:
                return AnneResponse(
                    message=(
                        "Moving to engaged. "
                        "When should we follow up? "
                        "(Engaged prospects need a follow-up date.)"
                    ),
                    suggested_actions=[{"action": "population_change", "population": pop}],
                )
            return AnneResponse(
                message=f"Moving to {pop}. Confirm?",
                suggested_actions=[{"action": "population_change", "population": pop}],
                requires_confirmation=True,
            )

        # Handle flag suspect
        if parsed.action == "flag_suspect":
            field_name = parsed.parameters.get("field", "unknown")
            return AnneResponse(
                message=f"Flagging {field_name} as suspect. I'll mark it.",
                suggested_actions=[
                    {
                        "action": "flag_suspect",
                        "field": field_name,
                    }
                ],
            )

        # If we have AI and it's a conversational note, use Anne's brain
        if self.is_available() and context.current_prospect_id:
            try:
                return self._ai_respond(user_input, context)
            except Exception as e:
                logger.warning(f"AI response failed: {e}")

        # Default: log as note
        return AnneResponse(
            message="Noted.",
            suggested_actions=[
                {
                    "action": "log_note",
                    "text": user_input,
                }
            ],
        )

    def execute_actions(self, actions: list[dict]) -> dict:
        """Execute confirmed actions.

        Returns dict with results of each action.
        """
        results: dict[str, Any] = {"executed": [], "failed": []}

        for action in actions:
            action_type = action.get("action", "")
            try:
                if action_type == "log_activity":
                    self._execute_log_activity(action)
                    results["executed"].append(action_type)

                elif action_type == "log_note":
                    self._execute_log_note(action)
                    results["executed"].append(action_type)

                elif action_type == "set_follow_up":
                    self._execute_set_follow_up(action)
                    results["executed"].append(action_type)

                elif action_type == "park":
                    self._execute_park(action)
                    results["executed"].append(action_type)

                elif action_type == "population_change":
                    self._execute_population_change(action)
                    results["executed"].append(action_type)

                elif action_type == "schedule_demo":
                    self._execute_schedule_demo(action)
                    results["executed"].append(action_type)

                elif action_type == "dial":
                    self._execute_dial(action)
                    results["executed"].append(action_type)

                elif action_type == "flag_suspect":
                    self._execute_flag_suspect(action)
                    results["executed"].append(action_type)

                else:
                    results["failed"].append({"action": action_type, "error": "Unknown action"})

            except Exception as e:
                logger.error(f"Action failed: {action_type}: {e}")
                results["failed"].append({"action": action_type, "error": str(e)})

        return results

    def pre_generate_cards(self, prospect_ids: list[int]) -> dict[int, str]:
        """Batch-generate card presentations for queue.

        Generates presentations for upcoming cards and caches them.
        Used during nightly cycle or between cards for low latency.
        """
        generated: dict[int, str] = {}

        for pid in prospect_ids:
            try:
                context = self._build_prospect_context(pid)
                if not context:
                    continue

                if self.is_available():
                    try:
                        presentation = self._ai_present_card(context)
                    except Exception:
                        logger.debug(
                            f"AI pre-generation failed for {pid}, using local", exc_info=True
                        )
                        presentation = self._local_present_card(context)
                else:
                    presentation = self._local_present_card(context)

                generated[pid] = presentation
                self._pre_generated[pid] = presentation

            except Exception as e:
                logger.warning(f"Pre-generation failed for {pid}: {e}")

        logger.info(f"Pre-generated {len(generated)} card presentations")
        return generated

    def take_notes(self, prospect_id: int, conversation: str) -> str:
        """Generate obsessive notes from conversation.

        Anne logs every detail: what happened, what was said,
        personal details, impressions, next steps.
        """
        if self.is_available():
            try:
                return self._ai_take_notes(prospect_id, conversation)
            except Exception as e:
                logger.warning(f"AI note-taking failed: {e}")

        # Local fallback: just clean up and return
        return f"[{date.today().isoformat()}] {conversation.strip()}"

    def extract_intel(self, prospect_id: int, notes: str) -> list[dict]:
        """Extract intel nuggets from notes.

        Scans for pain points, competitors, loan types,
        decision timelines, and key facts.
        """
        from src.ai.parser import extract_intel as parser_extract

        nuggets = parser_extract(notes, prospect_id)

        # Store nuggets in database
        for nugget_data in nuggets:
            try:
                nugget = IntelNugget(
                    prospect_id=nugget_data["prospect_id"],
                    category=IntelCategory(nugget_data["category"]),
                    content=nugget_data["content"],
                )
                self.db.create_intel_nugget(nugget)
            except Exception as e:
                logger.warning(f"Failed to store intel nugget: {e}")

        return nuggets

    # =========================================================================
    # PRIVATE: Context Building
    # =========================================================================

    def _build_prospect_context(self, prospect_id: int) -> Optional[dict]:
        """Build full context for a prospect."""
        full = self.db.get_prospect_full(prospect_id)
        if not full:
            return None

        from src.ai.card_story import generate_story

        story = generate_story(self.db, prospect_id)
        nuggets = self.db.get_intel_nuggets(prospect_id)

        return {
            "prospect": full.prospect,
            "company": full.company,
            "activities": full.activities,
            "contact_methods": full.contact_methods,
            "tags": full.tags,
            "story": story,
            "nuggets": nuggets,
        }

    def _format_context_for_prompt(self, context: dict) -> str:
        """Format prospect context into a prompt string."""
        p: Prospect = context["prospect"]
        company: Optional[Company] = context["company"]
        story: str = context["story"]
        nuggets: list[IntelNugget] = context["nuggets"]
        activities = context["activities"]

        parts = [
            f"Prospect: {p.full_name}",
            f"Company: {company.name if company else 'Unknown'}",
            f"Title: {p.title or 'Unknown'}",
            f"Population: {p.population.value}",
            f"Score: {p.prospect_score}/100",
            f"Attempts: {p.attempt_count}",
        ]

        if p.engagement_stage:
            parts.append(f"Stage: {p.engagement_stage.value}")
        if p.follow_up_date:
            parts.append(f"Follow-up: {p.follow_up_date}")
        if p.parked_month:
            parts.append(f"Parked until: {p.parked_month}")

        parts.append(f"\nStory:\n{story}")

        if nuggets:
            parts.append("\nIntel:")
            for n in nuggets[:10]:
                parts.append(f"  [{n.category.value}] {n.content}")

        if activities:
            parts.append(f"\nRecent activity ({len(activities)} total):")
            for act in activities[:5]:
                act_date = str(act.created_at)[:10] if act.created_at else ""
                notes_str = f": {act.notes[:60]}" if act.notes else ""
                parts.append(f"  {act_date} {act.activity_type.value}{notes_str}")

        return "\n".join(parts)

    # =========================================================================
    # PRIVATE: AI Methods
    # =========================================================================

    def _ai_present_card(self, context: dict) -> str:
        """Generate AI-enhanced card presentation."""
        client = self._get_client()
        context_str = self._format_context_for_prompt(context)

        prompt = (
            "Present this prospect card to Jeff. Include:\n"
            "1. Who they are and what they do\n"
            "2. History — what's happened so far\n"
            "3. Your analysis — is this worth pursuing? What's working/not working?\n"
            "4. Your recommendation — what should Jeff do next?\n\n"
            "Keep it conversational and concise (under 150 words).\n\n"
            f"Prospect context:\n{context_str}"
        )

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        self._track_usage(
            "anne",
            CLAUDE_MODEL,
            response.usage.input_tokens,
            response.usage.output_tokens,
        )
        return str(response.content[0].text)

    def _ai_respond(self, user_input: str, context: ConversationContext) -> AnneResponse:
        """Use Claude for conversational response."""
        client = self._get_client()

        # Build conversation history
        messages: list[dict[str, str]] = []

        # Add recent conversation context
        for msg in context.recent_messages[-10:]:
            messages.append(msg)

        # Add current input
        messages.append({"role": "user", "content": user_input})

        # Add prospect context if available
        system = _SYSTEM_PROMPT
        if context.current_prospect_id:
            prospect_context = self._build_prospect_context(context.current_prospect_id)
            if prospect_context:
                context_str = self._format_context_for_prompt(prospect_context)
                system += f"\n\nCurrent prospect:\n{context_str}"

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=512,
            system=system,
            messages=messages,
        )
        self._track_usage(
            "anne",
            CLAUDE_MODEL,
            response.usage.input_tokens,
            response.usage.output_tokens,
        )
        text = str(response.content[0].text)

        return AnneResponse(
            message=text,
            suggested_actions=[{"action": "log_note", "text": user_input}],
        )

    def _ai_take_notes(self, prospect_id: int, conversation: str) -> str:
        """Use Claude to generate obsessive notes."""
        client = self._get_client()

        prompt = (
            "Generate detailed notes from this sales conversation. Include:\n"
            "- What happened (call, email, meeting)\n"
            "- What was said (key points, not verbatim)\n"
            "- Personal details mentioned (names, preferences)\n"
            "- Jeff's impressions or strategic observations\n"
            "- Next steps agreed upon\n"
            "- Any intel nuggets (pain points, competitors, timelines)\n\n"
            "Be thorough but concise. These notes are the enduring memory.\n\n"
            f"Conversation:\n{conversation}"
        )

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        self._track_usage(
            "anne",
            CLAUDE_MODEL,
            response.usage.input_tokens,
            response.usage.output_tokens,
        )
        return str(response.content[0].text)

    def _draft_email(self, prospect_id: int, instruction: str) -> str:
        """Draft an email using Jeff's voice."""
        client = self._get_client()

        # Get style examples
        from src.ai.style_learner import get_style_prompt

        style_prompt = get_style_prompt()

        # Get prospect context
        context = self._build_prospect_context(prospect_id)
        context_str = ""
        if context:
            context_str = self._format_context_for_prompt(context)

        prompt = (
            f"Draft a short email based on Jeff's instruction.\n\n"
            f"Instruction: {instruction}\n\n"
            f"Prospect context:\n{context_str}\n\n"
            f"Style guide:\n{style_prompt}\n\n"
            "Write ONLY the email body (no subject line unless asked). "
            "Keep it short and in Jeff's voice."
        )

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        self._track_usage(
            "anne",
            CLAUDE_MODEL,
            response.usage.input_tokens,
            response.usage.output_tokens,
        )
        return str(response.content[0].text)

    # =========================================================================
    # PRIVATE: Local Fallback
    # =========================================================================

    def _should_disagree_with_park(self, prospect_id: Optional[int]) -> Optional[dict]:
        """Check if Anne should push back on parking this prospect.

        Returns a dict with 'reason' and 'alternative' if she disagrees, else None.
        """
        if not prospect_id:
            return None

        prospect = self.db.get_prospect(prospect_id)
        if not prospect:
            return None

        signals: list[str] = []

        # High score = promising prospect
        if prospect.prospect_score >= 60:
            signals.append(f"score is {prospect.prospect_score}/100")

        # Already engaged = deal in progress
        if prospect.population == Population.ENGAGED:
            signals.append("they're in your engaged pipeline")

        # Recent activity = momentum
        if prospect.id:
            activities = self.db.get_activities(prospect.id, limit=5)
            recent_positive = [
                a for a in activities
                if a.activity_type.value in ("email_received", "demo", "demo_completed")
                and a.created_at
            ]
            if recent_positive:
                signals.append("they've had recent positive activity")

            # Check for interested replies
            interested_replies = [
                a for a in activities
                if a.activity_type.value == "email_received"
                and a.outcome
                and a.outcome.value in ("interested", "replied")
            ]
            if interested_replies:
                signals.append("they replied showing interest")

        if len(signals) < 2:
            return None  # Not enough to disagree

        reason = f"Hold on — {', '.join(signals)}. This one's still warm."

        # Generate alternative based on context
        if prospect.population == Population.ENGAGED:
            alternative = (
                "Send a quick check-in email this week. "
                "If no response in 7 days, then park."
            )
        else:
            alternative = (
                "Call them one more time before parking. "
                "If you get voicemail, then park."
            )

        # If AI is available, try to generate a draft email as the alternative
        if self.is_available() and prospect.id:
            try:
                draft = self._draft_email(
                    prospect.id,
                    "Write a short, casual check-in. Don't be pushy. "
                    "Just asking if they had any questions or if timing is better now.",
                )
                alternative = f"Here's a quick check-in I'd send:\n\n{draft}"
            except Exception:
                pass  # Fall back to the text suggestion above

        return {"reason": reason, "alternative": alternative}

    def _local_present_card(self, context: dict) -> str:
        """Generate local-only card presentation (no AI)."""
        return str(context["story"])

    # =========================================================================
    # PRIVATE: Action Execution
    # =========================================================================

    def _execute_log_activity(self, action: dict) -> None:
        """Log a call/voicemail activity."""
        from src.db.models import ActivityOutcome

        prospect_id = action.get("prospect_id")
        if not prospect_id:
            return

        activity_type_str = action.get("type", "call")
        outcome_str = action.get("outcome")

        activity_type = ActivityType(activity_type_str)
        outcome = ActivityOutcome(outcome_str) if outcome_str else None

        activity = Activity(
            prospect_id=prospect_id,
            activity_type=activity_type,
            outcome=outcome,
            attempt_type=AttemptType.PERSONAL,
            notes=action.get("notes", ""),
            created_by="anne",
        )
        self.db.create_activity(activity)

        # Increment attempt count
        prospect = self.db.get_prospect(prospect_id)
        if prospect:
            prospect.attempt_count += 1
            prospect.last_contact_date = date.today()
            self.db.update_prospect(prospect)

    def _execute_log_note(self, action: dict) -> None:
        """Log a note."""
        prospect_id = action.get("prospect_id")
        if not prospect_id:
            return

        activity = Activity(
            prospect_id=prospect_id,
            activity_type=ActivityType.NOTE,
            notes=action.get("text", ""),
            created_by="anne",
        )
        self.db.create_activity(activity)

    def _execute_set_follow_up(self, action: dict) -> None:
        """Set follow-up date."""
        prospect_id = action.get("prospect_id")
        date_str = action.get("date")
        if not prospect_id or not date_str:
            return

        from src.engine.cadence import set_follow_up

        # Handle both date-only ("2026-01-15") and datetime strings
        try:
            follow_up_dt = datetime.fromisoformat(date_str)
        except ValueError:
            from datetime import date as date_cls

            follow_up_dt = datetime.combine(date_cls.fromisoformat(date_str), datetime.min.time())
        set_follow_up(self.db, prospect_id, follow_up_dt, reason="Anne: follow-up set")

    def _execute_park(self, action: dict) -> None:
        """Park a prospect."""
        prospect_id = action.get("prospect_id")
        parked_month = action.get("parked_month")
        if not prospect_id or not parked_month:
            return

        from src.engine.populations import transition_prospect

        prospect = self.db.get_prospect(prospect_id)
        if prospect:
            prospect.parked_month = parked_month
            self.db.update_prospect(prospect)
            transition_prospect(
                self.db,
                prospect_id,
                Population.PARKED,
                reason=f"Anne: parked until {parked_month}",
            )

    def _execute_population_change(self, action: dict) -> None:
        """Change prospect population."""
        prospect_id = action.get("prospect_id")
        pop_str = action.get("population")
        if not prospect_id or not pop_str:
            return

        from src.engine.populations import transition_prospect

        target = Population(pop_str)
        transition_prospect(
            self.db,
            prospect_id,
            target,
            reason=f"Anne: moved to {pop_str}",
        )

    def _execute_schedule_demo(self, action: dict) -> None:
        """Schedule a demo."""
        prospect_id = action.get("prospect_id")
        if not prospect_id:
            return

        from src.db.models import EngagementStage
        from src.engine.populations import transition_prospect

        activity = Activity(
            prospect_id=prospect_id,
            activity_type=ActivityType.DEMO_SCHEDULED,
            notes=f"Demo scheduled for {action.get('date', 'TBD')}",
            created_by="anne",
        )
        self.db.create_activity(activity)

        # Move to engaged/demo_scheduled if not already
        prospect = self.db.get_prospect(prospect_id)
        if prospect and prospect.population != Population.ENGAGED:
            transition_prospect(
                self.db,
                prospect_id,
                Population.ENGAGED,
                reason="Anne: demo scheduled",
                to_stage=EngagementStage.DEMO_SCHEDULED,
            )
        elif prospect and prospect.population == Population.ENGAGED:
            prospect.engagement_stage = EngagementStage.DEMO_SCHEDULED
            self.db.update_prospect(prospect)

    def _execute_dial(self, action: dict) -> None:
        """Trigger phone dial via Bria."""
        prospect_id = action.get("prospect_id")
        if not prospect_id:
            return

        from src.integrations.bria import BriaDialer

        contact_methods = self.db.get_contact_methods(prospect_id)
        phone = next(
            (m.value for m in contact_methods if m.type.value == "phone"),
            None,
        )
        if phone:
            dialer = BriaDialer()
            dialer.dial(phone)

    def _execute_flag_suspect(self, action: dict) -> None:
        """Flag a contact method as suspect."""
        prospect_id = action.get("prospect_id")
        field_name = action.get("field", "phone")
        if not prospect_id:
            return

        contact_methods = self.db.get_contact_methods(prospect_id)
        for method in contact_methods:
            if method.type.value == field_name:
                method.is_suspect = True
                self.db.update_contact_method(method)
                break
