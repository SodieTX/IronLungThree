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
from src.db.models import Activity, ActivityType, Population, Prospect

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
    Uses the minimum days from the interval (conservative scheduling).

    Args:
        prospect_id: Prospect ID (for future personalization)
        last_attempt_date: Date of last attempt
        attempt_number: Current attempt count

    Returns:
        Suggested next contact date
    """
    interval = get_interval(attempt_number)
    return add_business_days(last_attempt_date, interval.min_days)


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
    prospect = db.get_prospect(prospect_id)
    if prospect is None:
        return False

    prospect.follow_up_date = follow_up_date
    db.update_prospect(prospect)

    # Log the follow-up activity
    activity = Activity(
        prospect_id=prospect_id,
        activity_type=ActivityType.REMINDER,
        follow_up_set=follow_up_date,
        notes=reason or f"Follow-up set for {follow_up_date}",
        created_by="user",
    )
    db.create_activity(activity)

    logger.info(
        "Follow-up set",
        extra={
            "context": {
                "prospect_id": prospect_id,
                "follow_up_date": str(follow_up_date),
            }
        },
    )

    return True


def get_orphaned_engaged(db: Database) -> list[int]:
    """Get engaged prospects with no follow-up date.

    Orphans are dangerous - engaged prospects without dates
    will fall through the cracks.

    Returns:
        List of prospect IDs
    """
    conn = db._get_connection()
    rows = conn.execute(
        """SELECT id FROM prospects
           WHERE population = ?
           AND (follow_up_date IS NULL OR follow_up_date = '')""",
        (Population.ENGAGED.value,),
    ).fetchall()
    return [row["id"] for row in rows]


def get_overdue(db: Database) -> list[Prospect]:
    """Get prospects with follow_up_date < today.

    These are missed follow-ups that need attention.

    Returns:
        List of overdue prospects, most overdue first
    """
    conn = db._get_connection()
    today = date.today().isoformat()
    rows = conn.execute(
        """SELECT * FROM prospects
           WHERE follow_up_date IS NOT NULL
           AND follow_up_date < ?
           AND population NOT IN (?, ?, ?)
           ORDER BY follow_up_date ASC""",
        (
            today,
            Population.DEAD_DNC.value,
            Population.CLOSED_WON.value,
            Population.LOST.value,
        ),
    ).fetchall()
    return [db._row_to_prospect(row) for row in rows]


def get_todays_follow_ups(db: Database) -> list[Prospect]:
    """Get prospects with follow_up_date = today.

    Returns:
        List of prospects due for follow-up today
    """
    conn = db._get_connection()
    today = date.today().isoformat()
    # Match follow-ups where the date portion matches today
    rows = conn.execute(
        """SELECT * FROM prospects
           WHERE follow_up_date IS NOT NULL
           AND DATE(follow_up_date) = DATE(?)
           AND population NOT IN (?, ?, ?)
           ORDER BY follow_up_date ASC""",
        (
            today,
            Population.DEAD_DNC.value,
            Population.CLOSED_WON.value,
            Population.LOST.value,
        ),
    ).fetchall()
    return [db._row_to_prospect(row) for row in rows]


def get_todays_queue(db: Database, energy: Optional[str] = None) -> list[Prospect]:
    """Get today's work queue.

    Includes:
        - Engaged follow-ups due today or overdue
        - Unengaged prospects due for next attempt

    Ordered by:
        Normal (HIGH energy):
            1. Engaged first (closing > post-demo > demo-scheduled > pre-demo)
            2. Overdue items within engaged group
            3. Unengaged by score
            4. Timezone-ordered within groups
        LOW energy:
            1. Highest-probability closes first (closing, then post-demo)
            2. Then engaged by score descending
            3. Unengaged deferred to end

    Args:
        db: Database instance
        energy: Energy level ("HIGH", "MEDIUM", "LOW"). None = normal ordering.

    Returns:
        Ordered list of prospects for today
    """
    conn = db._get_connection()
    today = date.today().isoformat()

    # Stage priority for sorting (higher = more urgent)
    stage_priority = {
        "closing": 4,
        "post_demo": 3,
        "demo_scheduled": 2,
        "pre_demo": 1,
    }

    # Timezone call order (East Coast first in morning)
    tz_priority = {
        "eastern": 1,
        "central": 2,
        "mountain": 3,
        "pacific": 4,
        "alaska": 5,
        "hawaii": 6,
    }

    queue: list[tuple[int, int, int, Prospect]] = []

    # Group 1: Engaged follow-ups due today or overdue
    engaged_rows = conn.execute(
        """SELECT p.*, c.timezone as company_tz FROM prospects p
           LEFT JOIN companies c ON p.company_id = c.id
           WHERE p.population = ?
           AND p.follow_up_date IS NOT NULL
           AND DATE(p.follow_up_date) <= DATE(?)
           ORDER BY p.follow_up_date ASC""",
        (Population.ENGAGED.value, today),
    ).fetchall()

    for row in engaged_rows:
        prospect = db._row_to_prospect(row)
        stage = row["engagement_stage"] or "pre_demo"
        s_priority = stage_priority.get(stage, 0)
        tz = row["company_tz"] or "central"
        t_priority = tz_priority.get(tz, 2)
        # Sort key: group=0 (engaged first), then stage priority (desc), then tz
        queue.append((0, -s_priority, t_priority, prospect))

    # Group 2: Unengaged prospects due for contact
    unengaged_rows = conn.execute(
        """SELECT p.*, c.timezone as company_tz FROM prospects p
           LEFT JOIN companies c ON p.company_id = c.id
           WHERE p.population = ?
           AND (
               p.follow_up_date IS NULL
               OR DATE(p.follow_up_date) <= DATE(?)
           )
           ORDER BY p.prospect_score DESC""",
        (Population.UNENGAGED.value, today),
    ).fetchall()

    for row in unengaged_rows:
        prospect = db._row_to_prospect(row)
        tz = row["company_tz"] or "central"
        t_priority = tz_priority.get(tz, 2)
        score = -(prospect.prospect_score or 0)  # Negate for ascending sort
        # Sort key: group=1 (after engaged), then score (desc), then tz
        queue.append((1, score, t_priority, prospect))

    # Sort by the tuple keys
    queue.sort(key=lambda x: (x[0], x[1], x[2]))

    prospects = [item[3] for item in queue]

    # Low energy reordering: surface highest-probability closes first,
    # push cold prospecting to the end
    if energy and energy.upper() == "LOW":
        closing_stage = {"closing", "post_demo"}

        def _low_energy_key(p: Prospect) -> tuple[int, int]:
            # Engaged closing/post_demo first, then engaged by score, then rest
            if p.population == Population.ENGAGED:
                stage = p.engagement_stage.value if p.engagement_stage else ""
                if stage in closing_stage:
                    return (0, -(p.prospect_score or 0))
                return (1, -(p.prospect_score or 0))
            return (2, -(p.prospect_score or 0))

        prospects.sort(key=_low_energy_key)

    return prospects
