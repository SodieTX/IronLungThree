"""Compassionate messages - No guilt trips. Ever.

Every message the system shows should be encouraging, never shaming.
Context-aware: knows how long Jeff's been away, how his day is going,
and what needs attention without making him feel bad.
"""

import random
from datetime import datetime, timedelta
from typing import Callable, Optional

from src.core.logging import get_logger

logger = get_logger(__name__)


# Message pools — curated, never generic
_WELCOME_FRESH = [
    "Good morning. Let's get after it.",
    "Ready when you are.",
    "New day, clean slate. Here's what's on deck.",
]

_WELCOME_BACK_SHORT = [
    "Welcome back. Picking up where you left off.",
    "Back at it. Here's what matters most.",
    "Good to see you. Let's keep the momentum going.",
]

_WELCOME_BACK_LONG = [
    "Welcome back. Here are the 3 most important things.",
    "Hey. A few things need attention. Nothing we can't handle.",
    "It's been a minute. Here's a quick catch-up — no stress.",
]

_ENCOURAGEMENT_EARLY = [
    "Strong start.",
    "You're building momentum.",
    "Good pace. Keep it rolling.",
]

_ENCOURAGEMENT_MID = [
    "You're in the zone.",
    "Solid work today.",
    "Pipeline is moving.",
]

_ENCOURAGEMENT_LATE = [
    "Still grinding. Nice.",
    "Impressive stamina.",
    "Late push pays off.",
]

_ENCOURAGEMENT_STREAK = [
    "Streak going! Don't stop now.",
    "On a roll.",
    "This is what a hot streak feels like.",
]

_BREAK_SUGGESTIONS = [
    "You've been at it a while. Step away for 5 minutes — you've earned it.",
    "Quick break? Your brain will thank you.",
    "Good stopping point. Stretch, hydrate, come back sharp.",
    "Consider a breather. Everything will still be here.",
]

_QUEUE_EMPTY = [
    "Queue clear. You crushed it. Take a break.",
    "Everything's handled. Nice work.",
    "That's a wrap. Nothing left in the queue.",
]

_MISSED_FOLLOWUPS = [
    "A few things slipped. Let's catch them up.",
    "Some follow-ups need attention. Here's the quick list.",
    "A couple overdue items. Nothing catastrophic.",
]

_LOW_PRODUCTIVITY = [
    "Some days are harder. Here's what matters most.",
    "Not every day is a record-setter. That's fine.",
    "Rough one? Let's just knock out the essentials.",
]

_RESCUE_INTROS = [
    "Bad day? Here are just 3 things. That's it.",
    "Low energy mode. Only the must-do items.",
    "Simplified view. Do these and you're done for today.",
]


class CompassionEngine:
    """Generates context-aware compassionate messages.

    No guilt. No shame. Just clear, kind guidance.
    """

    def __init__(self, now_fn: Optional[Callable] = None):
        self._now_fn = now_fn or datetime.now

    def get_welcome_message(
        self,
        last_session_end: Optional[datetime] = None,
        missed_followups: int = 0,
    ) -> str:
        """Get appropriate welcome message based on context.

        Args:
            last_session_end: When the last session ended (None = first session)
            missed_followups: Number of overdue follow-ups
        """
        now = self._now_fn()

        if last_session_end is None:
            return random.choice(_WELCOME_FRESH)

        gap = now - last_session_end
        if gap < timedelta(hours=4):
            msg = random.choice(_WELCOME_BACK_SHORT)
        else:
            msg = random.choice(_WELCOME_BACK_LONG)

        if missed_followups > 0:
            msg += f" {missed_followups} follow-up{'s' if missed_followups != 1 else ''} to catch up on."

        return msg

    def get_encouragement(
        self,
        cards_processed: int = 0,
        current_streak: int = 0,
    ) -> str:
        """Get contextual encouragement based on progress and time.

        Args:
            cards_processed: Cards processed this session
            current_streak: Current streak count
        """
        now = self._now_fn()
        hour = now.hour

        if current_streak >= 5:
            return random.choice(_ENCOURAGEMENT_STREAK)

        if hour < 12:
            pool = _ENCOURAGEMENT_EARLY
        elif hour < 16:
            pool = _ENCOURAGEMENT_MID
        else:
            pool = _ENCOURAGEMENT_LATE

        return random.choice(pool)

    def get_break_suggestion(self, session_minutes: int = 0) -> Optional[str]:
        """Suggest a break if warranted.

        Returns None if a break isn't warranted yet.
        """
        if session_minutes < 45:
            return None
        return random.choice(_BREAK_SUGGESTIONS)

    def get_queue_empty_message(self) -> str:
        """Message when queue is empty."""
        return random.choice(_QUEUE_EMPTY)

    def get_missed_followup_message(self, count: int) -> str:
        """Message about missed follow-ups — no guilt."""
        return random.choice(_MISSED_FOLLOWUPS)

    def get_low_productivity_message(self) -> str:
        """Message for a slow day — no shame."""
        return random.choice(_LOW_PRODUCTIVITY)

    def get_rescue_intro(self) -> str:
        """Get intro for rescue mode — zero guilt."""
        return random.choice(_RESCUE_INTROS)
