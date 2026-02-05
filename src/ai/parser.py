"""Voice/text parser for structured action extraction.

Understands:
    - Sales vocabulary: "LV" = left voicemail
    - Relative dates: "next week" = Monday
    - Population transitions: "interested" → engaged
    - Intel extraction: "she does fix and flip" → loan type
    - Navigation: "skip", "next", "undo"
    - Actions: "send intro email", "dial him"
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional

from src.core.logging import get_logger
from src.db.models import EngagementStage, Population

logger = get_logger(__name__)


@dataclass
class ParseResult:
    """Result of parsing user input.

    Attributes:
        action: Identified action type
        parameters: Action parameters
        confidence: Parse confidence 0-1
        raw_input: Original input
    """

    action: str
    parameters: dict[str, Any]
    confidence: float
    raw_input: str


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


def parse(input_text: str, context: ParserContext) -> ParseResult:
    """Parse user input into structured action."""
    raise NotImplementedError("Phase 4, Step 4.2")


def parse_relative_date(text: str) -> Optional[date]:
    """Parse relative date from text.

    Examples:
        "tomorrow" → tomorrow
        "next week" → next Monday
        "in a few days" → +3 days
        "in March" → parked month
    """
    raise NotImplementedError("Phase 4, Step 4.2")


def parse_population_signal(text: str) -> Optional[Population]:
    """Parse population transition signal.

    Examples:
        "interested" → ENGAGED
        "hard no" → DEAD_DNC
        "not now" + timeframe → PARKED
    """
    raise NotImplementedError("Phase 4, Step 4.2")


def extract_intel(text: str, prospect_id: int) -> list[dict]:
    """Extract intel nuggets from conversation."""
    raise NotImplementedError("Phase 4, Step 4.2")
