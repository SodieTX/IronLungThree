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
from datetime import date, timedelta
from typing import Any, Optional

from src.core.logging import get_logger
from src.db.models import IntelCategory, Population

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
    "wed": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

# Month names to numbers
_MONTH_NAMES = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
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
    "hard no",
]

_ENGAGED_SIGNALS = [
    "interested",
    "tell me more",
    "send me info",
    "let's talk",
    "set up a meeting",
    "sounds good",
    "wants a demo",
    "demo set",
    "callback",
    "called back",
    "she's interested",
    "he's interested",
    "they're interested",
]

# Sales vocabulary shortcuts
_SALES_VOCAB = {
    "lv": ("voicemail", {"outcome": "left_vm"}),
    "left voicemail": ("voicemail", {"outcome": "left_vm"}),
    "left vm": ("voicemail", {"outcome": "left_vm"}),
    "left a voicemail": ("voicemail", {"outcome": "left_vm"}),
    "voicemail": ("voicemail", {"outcome": "left_vm"}),
    "vm": ("voicemail", {"outcome": "left_vm"}),
    "no answer": ("call", {"outcome": "no_answer"}),
    "na": ("call", {"outcome": "no_answer"}),
    "spoke with": ("call", {"outcome": "spoke_with"}),
    "spoke to": ("call", {"outcome": "spoke_with"}),
    "talked to": ("call", {"outcome": "spoke_with"}),
    "connected": ("call", {"outcome": "spoke_with"}),
    "ooo": ("note", {"outcome": "ooo", "text": "Out of office"}),
    "out of office": ("note", {"outcome": "ooo", "text": "Out of office"}),
    "bounced": ("note", {"outcome": "bounced", "text": "Email bounced"}),
    "email bounced": ("note", {"outcome": "bounced", "text": "Email bounced"}),
    "referral": ("note", {"outcome": "referral"}),
    "wrong number": ("flag_suspect", {"field": "phone", "text": "Wrong number"}),
    "bad number": ("flag_suspect", {"field": "phone", "text": "Bad number"}),
    "bad email": ("flag_suspect", {"field": "email", "text": "Bad email"}),
}

# Action patterns
_EMAIL_PATTERNS = [
    r"send (?:him|her|them) an? email",
    r"send (?:an? )?(?:intro )?email",
    r"email (?:him|her|them)",
    r"draft (?:an? )?email",
    r"write (?:an? )?email",
]

_DIAL_PATTERNS = [
    r"dial (?:him|her|them)",
    r"call (?:him|her|them)",
    r"ring (?:him|her|them)",
    r"give (?:him|her|them) a call",
]

_PARK_PATTERNS = [
    r"park (?:him|her|them|this)",
    r"park (?:until|til|till) (.+)",
    r"put (?:him|her|them) on hold",
    r"shelve (?:him|her|them|this|it)",
]

_DEMO_PATTERNS = [
    r"(?:schedule|set|book) (?:a )?demo",
    r"demo (?:set|scheduled|booked)",
    r"(?:set|schedule) (?:a )?(?:demo|meeting)",
]

_CONFIRM_PATTERNS = [
    r"^(?:yes|yeah|yep|yup|do it|send it|go|confirmed?|ok|okay|sure|absolutely)$",
]

_DENY_PATTERNS = [
    r"^(?:no|nah|nope|cancel|don't|nevermind|never mind|stop)$",
]


def parse(input_text: str, context: Optional[ParserContext] = None) -> ParseResult:
    """Parse user input into structured action."""
    text_lower = input_text.lower().strip()

    if not text_lower:
        return ParseResult(action="empty", parameters={}, confidence=0.0, raw_input=input_text)

    # Confirmation / denial (highest priority in conversation flow)
    for pattern in _CONFIRM_PATTERNS:
        if re.match(pattern, text_lower):
            return ParseResult(
                action="confirm",
                parameters={},
                confidence=1.0,
                raw_input=input_text,
            )
    for pattern in _DENY_PATTERNS:
        if re.match(pattern, text_lower):
            return ParseResult(
                action="deny",
                parameters={},
                confidence=1.0,
                raw_input=input_text,
            )

    # Navigation
    if text_lower in ("skip", "next", "next card"):
        return ParseResult(action="skip", parameters={}, confidence=1.0, raw_input=input_text)
    if text_lower in ("undo", "undo that"):
        return ParseResult(action="undo", parameters={}, confidence=1.0, raw_input=input_text)
    if text_lower in ("defer", "later"):
        return ParseResult(action="defer", parameters={}, confidence=1.0, raw_input=input_text)

    # Sales vocab shortcuts
    for phrase, (action, params) in _SALES_VOCAB.items():
        if text_lower == phrase or text_lower.startswith(phrase + " "):
            return ParseResult(
                action=action,
                parameters={**params, "text": input_text},
                confidence=0.9,
                raw_input=input_text,
            )

    # Email action
    for pattern in _EMAIL_PATTERNS:
        if re.search(pattern, text_lower):
            return ParseResult(
                action="send_email",
                parameters={"text": input_text},
                confidence=0.85,
                raw_input=input_text,
            )

    # Dial action
    for pattern in _DIAL_PATTERNS:
        if re.search(pattern, text_lower):
            return ParseResult(
                action="dial",
                parameters={"text": input_text},
                confidence=0.9,
                raw_input=input_text,
            )

    # Park action
    for pattern in _PARK_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            park_date = None
            parked_month = None
            # Check for month in the text
            for month_name, month_num in _MONTH_NAMES.items():
                if month_name in text_lower:
                    year = date.today().year
                    if month_num <= date.today().month:
                        year += 1
                    parked_month = f"{year}-{month_num:02d}"
                    break
            if not parked_month:
                park_date = parse_relative_date(text_lower)
            return ParseResult(
                action="park",
                parameters={
                    "text": input_text,
                    "parked_month": parked_month,
                },
                confidence=0.8,
                raw_input=input_text,
                date=park_date,
            )

    # Demo scheduling
    for pattern in _DEMO_PATTERNS:
        if re.search(pattern, text_lower):
            extracted_date = parse_relative_date(text_lower)
            return ParseResult(
                action="schedule_demo",
                parameters={"text": input_text},
                confidence=0.85,
                raw_input=input_text,
                date=extracted_date,
            )

    # Follow-up instructions
    if "follow up" in text_lower or "follow-up" in text_lower:
        extracted_date = parse_relative_date(text_lower)
        return ParseResult(
            action="set_follow_up",
            parameters={"text": input_text},
            confidence=0.8 if extracted_date else 0.5,
            raw_input=input_text,
            date=extracted_date,
        )

    # Population signals
    signal = parse_population_signal(text_lower)
    if signal is not None:
        return ParseResult(
            action="population_change",
            parameters={"population": signal.value, "text": input_text},
            confidence=0.7,
            raw_input=input_text,
        )

    # Park to month (standalone month reference: "in March", "til June")
    for month_name, month_num in _MONTH_NAMES.items():
        if re.search(rf"\b(?:in|til|till|until)\s+{month_name}\b", text_lower):
            year = date.today().year
            if month_num <= date.today().month:
                year += 1
            return ParseResult(
                action="park",
                parameters={
                    "text": input_text,
                    "parked_month": f"{year}-{month_num:02d}",
                },
                confidence=0.7,
                raw_input=input_text,
            )

    # Default: treat as note/conversation
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

    if "in a couple days" in text_lower or "in a couple of days" in text_lower:
        return today + timedelta(days=2)

    # "next <day>" pattern
    for day_name, weekday_num in _DAY_NAMES.items():
        if f"next {day_name}" in text_lower or text_lower.endswith(day_name):
            days_ahead = weekday_num - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return today + timedelta(days=days_ahead)

    # "<day>" standalone (e.g., "wednesday")
    for day_name, weekday_num in _DAY_NAMES.items():
        if re.search(rf"\b{day_name}\b", text_lower):
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

    for signal in _DNC_SIGNALS:
        if signal in text_lower:
            return Population.DEAD_DNC

    for signal in _DEAD_SIGNALS:
        if signal in text_lower:
            return Population.DEAD_DNC

    for signal in _ENGAGED_SIGNALS:
        if signal in text_lower:
            return Population.ENGAGED

    if "not now" in text_lower or "not right now" in text_lower:
        return Population.PARKED

    return None


def extract_intel(text: str, prospect_id: int) -> list[dict]:
    """Extract intel nuggets from conversation text.

    Scans for patterns indicating:
    - Pain points
    - Competitor mentions
    - Loan types
    - Decision timelines
    - Key facts
    """
    nuggets: list[dict] = []
    text_lower = text.lower()

    # Pain point patterns
    pain_patterns = [
        r"(?:struggling with|pain point|problem with|frustrated by|issue with|hate|manual)\s+(.{10,60})",
        r"(?:need|looking for|want)\s+(?:a |an |better |new )?(.{10,60})",
    ]
    for pattern in pain_patterns:
        match = re.search(pattern, text_lower)
        if match:
            nuggets.append(
                {
                    "prospect_id": prospect_id,
                    "category": IntelCategory.PAIN_POINT.value,
                    "content": match.group(1).strip().rstrip("."),
                }
            )
            break  # One pain point per parse

    # Competitor patterns
    competitor_patterns = [
        r"(?:using|with|evaluating|looking at|comparing|considering)\s+([\w\s]+?)(?:\s+(?:right now|currently|too|also|already))",
        r"(?:competitor|vendor|alternative)\s+(?:is\s+)?(\w[\w\s]{3,30})",
    ]
    for pattern in competitor_patterns:
        match = re.search(pattern, text_lower)
        if match:
            nuggets.append(
                {
                    "prospect_id": prospect_id,
                    "category": IntelCategory.COMPETITOR.value,
                    "content": match.group(1).strip(),
                }
            )
            break

    # Loan type patterns
    loan_keywords = [
        "bridge",
        "fix and flip",
        "fix-and-flip",
        "construction",
        "commercial",
        "residential",
        "conventional",
        "fha",
        "va",
        "jumbo",
        "hard money",
        "private money",
        "dscr",
        "ground up",
        "multifamily",
        "mixed use",
        "rehab",
    ]
    found_types: list[str] = []
    for keyword in loan_keywords:
        if keyword in text_lower:
            found_types.append(keyword)
    if found_types:
        nuggets.append(
            {
                "prospect_id": prospect_id,
                "category": IntelCategory.LOAN_TYPE.value,
                "content": ", ".join(found_types),
            }
        )

    # Decision timeline patterns
    timeline_patterns = [
        r"(?:deciding|decision|choose|pick)\s+(?:by|in|before)\s+(.{5,40})",
        r"(?:board meeting|committee|review)\s+(?:in|on|by)\s+(.{5,30})",
        r"(?:budget|funding)\s+(?:in|for)\s+(?:q[1-4]|(?:january|february|march|april|may|june|july|august|september|october|november|december))",
    ]
    for pattern in timeline_patterns:
        match = re.search(pattern, text_lower)
        if match:
            nuggets.append(
                {
                    "prospect_id": prospect_id,
                    "category": IntelCategory.DECISION_TIMELINE.value,
                    "content": match.group(0).strip(),
                }
            )
            break

    return nuggets
