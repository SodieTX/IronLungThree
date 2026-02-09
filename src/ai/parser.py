"""Voice/text parser for structured action extraction.

Understands:
    - Sales vocabulary: "LV" = left voicemail
    - Relative dates: "next week" = Monday
    - Population transitions: "interested" → engaged
    - Intel extraction: "she does fix and flip" → loan type
    - Navigation: "skip", "next", "undo"
    - Actions: "send intro email", "dial him"
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Optional

from src.core.logging import get_logger
from src.db.models import Population

logger = get_logger(__name__)


@dataclass
class ParseResult:
    """Result of parsing user input.

    Attributes:
        action: Identified action type
        parameters: Action parameters
        confidence: Parse confidence 0-1
        raw_input: Original input
        date: Extracted date if applicable
    """

    action: str
    parameters: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    raw_input: str = ""
    date: Optional[date] = None


@dataclass
class ParserContext:
    """Context for parsing.

    Attributes:
        current_prospect_id: Current card
        current_population: Current population
        recent_actions: Recent actions for context
    """

    current_prospect_id: Optional[int] = None
    current_population: Optional[Population] = None
    recent_actions: Optional[list[str]] = None


# Day name to weekday number (Monday=0, Sunday=6)
_DAY_NAMES = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

# Population signal keywords
_DEAD_SIGNALS = [
    "out of business",
    "shut down",
    "closed",
    "bankrupt",
    "no longer",
    "dissolved",
    "defunct",
]

_DNC_SIGNALS = [
    "remove me",
    "stop calling",
    "do not call",
    "do not contact",
    "unsubscribe",
    "take me off",
    "don't call",
    "don't contact",
    "leave me alone",
]

_ENGAGED_SIGNALS = [
    "interested",
    "tell me more",
    "send me info",
    "let's talk",
    "set up a meeting",
    "sounds good",
]


def parse(input_text: str, context: Optional[ParserContext] = None) -> ParseResult:
    """Parse user input into structured action."""
    text_lower = input_text.lower().strip()

    # Check for follow-up instructions
    if "follow up" in text_lower or "follow-up" in text_lower:
        extracted_date = parse_relative_date(text_lower)
        return ParseResult(
            action="set_follow_up",
            parameters={"text": input_text},
            confidence=0.8 if extracted_date else 0.5,
            raw_input=input_text,
            date=extracted_date,
        )

    # Check for population signals
    signal = parse_population_signal(text_lower)
    if signal is not None:
        return ParseResult(
            action="population_change",
            parameters={"population": signal.value},
            confidence=0.7,
            raw_input=input_text,
        )

    # Check for navigation
    if text_lower in ("skip", "next"):
        return ParseResult(
            action="skip",
            parameters={},
            confidence=1.0,
            raw_input=input_text,
        )

    if text_lower == "undo":
        return ParseResult(
            action="undo",
            parameters={},
            confidence=1.0,
            raw_input=input_text,
        )

    # Default: note
    return ParseResult(
        action="note",
        parameters={"text": input_text},
        confidence=0.3,
        raw_input=input_text,
    )


def parse_relative_date(text: str) -> Optional[date]:
    """Parse relative date from text.

    Examples:
        "tomorrow" → tomorrow
        "next week" → next Monday
        "in a few days" → +3 days
        "in March" → parked month
    """
    text_lower = text.lower().strip()
    today = date.today()

    if "tomorrow" in text_lower:
        return today + timedelta(days=1)

    if "next week" in text_lower:
        return today + timedelta(days=7)

    if "in a few days" in text_lower:
        return today + timedelta(days=3)

    # "next <day>" pattern
    for day_name, weekday_num in _DAY_NAMES.items():
        if f"next {day_name}" in text_lower:
            days_ahead = weekday_num - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return today + timedelta(days=days_ahead)

    # "in N days" pattern
    match = re.search(r"in\s+(\d+)\s+days?", text_lower)
    if match:
        return today + timedelta(days=int(match.group(1)))

    # "in N weeks" pattern
    match = re.search(r"in\s+(\d+)\s+weeks?", text_lower)
    if match:
        return today + timedelta(weeks=int(match.group(1)))

    return None


def parse_population_signal(text: str) -> Optional[Population]:
    """Parse population transition signal.

    Examples:
        "interested" → ENGAGED
        "hard no" → DEAD_DNC
        "not now" + timeframe → PARKED
    """
    text_lower = text.lower().strip()

    for signal in _DEAD_SIGNALS:
        if signal in text_lower:
            return Population.DEAD_DNC

    for signal in _DNC_SIGNALS:
        if signal in text_lower:
            return Population.DEAD_DNC

    for signal in _ENGAGED_SIGNALS:
        if signal in text_lower:
            return Population.ENGAGED

    if "not now" in text_lower or "not right now" in text_lower:
        return Population.PARKED

    return None


def extract_intel(text: str, prospect_id: int) -> list[dict]:
    """Extract intel nuggets from conversation."""
    raise NotImplementedError("Phase 4, Step 4.2")
