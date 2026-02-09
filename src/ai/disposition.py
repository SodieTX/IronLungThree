"""Disposition engine - WON / OUT / ALIVE.

Every prospect interaction ends with one of three outcomes:
    - WON: Deal closed (capture value, date, notes)
    - OUT: Dead/DNC, Lost, or Parked
    - ALIVE: Still in play (MUST have follow-up date)

No orphans: engaged prospects MUST have a follow-up date.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from src.core.logging import get_logger
from src.db.models import LostReason, Population

logger = get_logger(__name__)


@dataclass
class Disposition:
    """Prospect disposition.

    Attributes:
        outcome: WON, OUT, or ALIVE
        population: Target population
        follow_up_date: Required for ALIVE
        deal_value: For WON
        close_date: For WON
        close_notes: For WON
        lost_reason: For OUT/LOST
        lost_competitor: For OUT/LOST
        parked_month: For OUT/PARKED
        notes: Activity notes
        reason: Short reason code
    """

    outcome: str  # WON, OUT, ALIVE
    population: Population = Population.UNENGAGED
    follow_up_date: Optional[datetime] = None
    deal_value: Optional[Decimal] = None
    close_date: Optional[date] = None
    close_notes: Optional[str] = None
    lost_reason: Optional[LostReason] = None
    lost_competitor: Optional[str] = None
    parked_month: Optional[str] = None
    notes: Optional[str] = None
    reason: Optional[str] = None


# Signal patterns for disposition detection
_WON_SIGNALS = [
    "signed",
    "contract",
    "closed",
    "deal done",
    "won",
    "we got it",
    "accepted",
]

_DEAD_SIGNALS = {
    "shut down": "company_closed",
    "out of business": "company_closed",
    "closed down": "company_closed",
    "bankrupt": "company_closed",
    "dissolved": "company_closed",
    "defunct": "company_closed",
    "no longer operating": "company_closed",
}

_LOST_SIGNALS = [
    "went with competitor",
    "chose someone else",
    "not buying",
    "not interested",
    "hard no",
    "lost",
]


def determine_disposition(conversation: str | list[dict]) -> Disposition:
    """Determine disposition from conversation text or history."""
    if isinstance(conversation, list):
        text = " ".join(
            entry.get("content", "") if isinstance(entry, dict) else str(entry)
            for entry in conversation
        )
    else:
        text = conversation

    text_lower = text.lower()

    # Check for WON signals
    for signal in _WON_SIGNALS:
        if signal in text_lower:
            return Disposition(
                outcome="WON",
                population=Population.CLOSED_WON,
            )

    # Check for DEAD signals
    for signal, reason in _DEAD_SIGNALS.items():
        if signal in text_lower:
            return Disposition(
                outcome="OUT",
                population=Population.DEAD_DNC,
                reason=reason,
            )

    # Check for LOST signals
    for signal in _LOST_SIGNALS:
        if signal in text_lower:
            return Disposition(
                outcome="OUT",
                population=Population.LOST,
            )

    # Default: ALIVE
    return Disposition(
        outcome="ALIVE",
        population=Population.UNENGAGED,
    )


def validate_disposition(disposition: Disposition) -> tuple[bool, list[str]]:
    """Validate disposition. Returns (is_valid, issues).

    Rules:
        - ALIVE must have follow_up_date
        - WON must have deal_value
        - PARKED must have parked_month
        - LOST must have lost_reason or reason
    """
    issues: list[str] = []

    if disposition.outcome == "ALIVE" and disposition.follow_up_date is None:
        issues.append("ALIVE disposition requires follow_up_date")

    if disposition.outcome == "WON" and disposition.deal_value is None:
        issues.append("WON disposition requires deal_value")

    if disposition.population == Population.PARKED and disposition.parked_month is None:
        issues.append("PARKED disposition requires parked_month")

    if (
        disposition.population == Population.LOST
        and disposition.lost_reason is None
        and disposition.reason is None
    ):
        issues.append("LOST disposition requires lost_reason or reason")

    is_valid = len(issues) == 0
    return is_valid, issues


def apply_disposition(db: object, prospect_id: int, disposition: Disposition) -> bool:
    """Apply disposition to prospect."""
    raise NotImplementedError("Phase 4, Step 4.6")
