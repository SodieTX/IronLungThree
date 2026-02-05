"""Dual cadence system for follow-up timing.

Two completely different systems based on who controls timing:
    1. System-Paced (Unengaged): System calculates next contact date
    2. Prospect-Paced (Engaged): Prospect said when to call, we honor it

Usage:
    from src.engine.cadence import calculate_next_contact, get_orphaned_engaged

    next_date = calculate_next_contact(prospect_id, last_attempt, attempt_num)
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import Population, Prospect

logger = get_logger(__name__)


# =============================================================================
# UNENGAGED CADENCE CONFIGURATION
# =============================================================================


@dataclass
class CadenceInterval:
    """Interval configuration for an attempt.

    Attributes:
        min_days: Minimum business days before next attempt
        max_days: Maximum business days before next attempt
        channel: Suggested channel (call, email, combo)
    """

    min_days: int
    max_days: int
    channel: str


# Default intervals by attempt number
DEFAULT_INTERVALS = {
    1: CadenceInterval(3, 5, "call"),
    2: CadenceInterval(5, 7, "call"),
    3: CadenceInterval(7, 10, "email"),
    4: CadenceInterval(10, 14, "combo"),
}


def get_interval(attempt_number: int) -> CadenceInterval:
    """Get cadence interval for attempt number.

    Args:
        attempt_number: Which attempt this will be

    Returns:
        CadenceInterval for this attempt
    """
    if attempt_number in DEFAULT_INTERVALS:
        return DEFAULT_INTERVALS[attempt_number]
    # After attempt 4, use longer intervals
    return CadenceInterval(14, 21, "combo")


def calculate_next_contact(
    prospect_id: int,
    last_attempt_date: date,
    attempt_number: int,
) -> date:
    """Calculate next contact date for unengaged prospect.

    Uses configurable intervals based on attempt number.

    Args:
        prospect_id: Prospect ID (for future personalization)
        last_attempt_date: Date of last attempt
        attempt_number: Current attempt count

    Returns:
        Suggested next contact date
    """
    raise NotImplementedError("Phase 2, Step 2.3")


def add_business_days(start_date: date, business_days: int) -> date:
    """Add business days to a date (skip weekends).

    Args:
        start_date: Starting date
        business_days: Number of business days to add

    Returns:
        Resulting date
    """
    result = start_date
    days_added = 0

    while days_added < business_days:
        result += timedelta(days=1)
        # Skip weekends (5 = Saturday, 6 = Sunday)
        if result.weekday() < 5:
            days_added += 1

    return result


# =============================================================================
# ENGAGED CADENCE (PROSPECT-PACED)
# =============================================================================


def set_follow_up(
    db: Database,
    prospect_id: int,
    follow_up_date: datetime,
    reason: Optional[str] = None,
) -> bool:
    """Set follow-up date for prospect.

    This is for engaged (prospect-paced) cadence.
    The date is exactly what the prospect specified.

    Args:
        db: Database instance
        prospect_id: Prospect to update
        follow_up_date: Exact follow-up datetime
        reason: Why this date was chosen

    Returns:
        True if updated
    """
    raise NotImplementedError("Phase 2, Step 2.3")


def get_orphaned_engaged(db: Database) -> list[int]:
    """Get engaged prospects with no follow-up date.

    Orphans are dangerous - engaged prospects without dates
    will fall through the cracks.

    Returns:
        List of prospect IDs
    """
    raise NotImplementedError("Phase 2, Step 2.3")


def get_overdue(db: Database) -> list[Prospect]:
    """Get prospects with follow_up_date < today.

    These are missed follow-ups that need attention.

    Returns:
        List of overdue prospects
    """
    raise NotImplementedError("Phase 2, Step 2.3")


def get_todays_queue(db: Database) -> list[Prospect]:
    """Get today's work queue.

    Includes:
        - Engaged follow-ups due today or overdue
        - Unengaged prospects due for next attempt

    Ordered by:
        1. Engaged first (closing > post-demo > demo-scheduled > pre-demo)
        2. Overdue items within engaged group
        3. Unengaged by score
        4. Timezone-ordered within groups

    Returns:
        Ordered list of prospects for today
    """
    raise NotImplementedError("Phase 2, Step 2.4")
