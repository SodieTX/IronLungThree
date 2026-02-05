"""Disposition engine - WON / OUT / ALIVE.

Every prospect interaction ends with one of three outcomes:
    - WON: Deal closed (capture value, date, notes)
    - OUT: Dead/DNC, Lost, or Parked
    - ALIVE: Still in play (MUST have follow-up date)

No orphans: engaged prospects MUST have a follow-up date.
"""

from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional
from decimal import Decimal

from src.db.models import Population, LostReason
from src.core.logging import get_logger

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
    """

    outcome: str  # WON, OUT, ALIVE
    population: Population
    follow_up_date: Optional[datetime] = None
    deal_value: Optional[Decimal] = None
    close_date: Optional[date] = None
    close_notes: Optional[str] = None
    lost_reason: Optional[LostReason] = None
    lost_competitor: Optional[str] = None
    parked_month: Optional[str] = None
    notes: Optional[str] = None


def determine_disposition(conversation: list[dict]) -> Disposition:
    """Determine disposition from conversation."""
    raise NotImplementedError("Phase 4, Step 4.6")


def validate_disposition(disposition: Disposition) -> list[str]:
    """Validate disposition. Returns issues (empty = valid).

    Rules:
        - ALIVE must have follow_up_date
        - WON must have deal_value
        - PARKED must have parked_month
    """
    raise NotImplementedError("Phase 4, Step 4.6")


def apply_disposition(db, prospect_id: int, disposition: Disposition) -> bool:
    """Apply disposition to prospect."""
    raise NotImplementedError("Phase 4, Step 4.6")
