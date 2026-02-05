"""Daily cockpit data generation.

Real-time status bar data for the GUI. Lightweight queries
designed to run frequently without performance impact.

Usage:
    from src.content.daily_cockpit import get_cockpit_data

    data = get_cockpit_data(db)
    status_bar.update(data)
"""

from dataclasses import dataclass
from datetime import date

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import Population

logger = get_logger(__name__)


@dataclass
class CockpitData:
    """Real-time cockpit metrics."""

    queue_remaining: int
    queue_total: int
    engaged_count: int
    demos_today: int
    overdue_count: int
    total_prospects: int = 0
    broken_count: int = 0


def get_cockpit_data(db: Database) -> CockpitData:
    """Get current cockpit data.

    Args:
        db: Database instance

    Returns:
        CockpitData with real-time metrics
    """
    conn = db._get_connection()
    today = date.today().isoformat()

    # Population counts
    pop_counts = db.get_population_counts()
    total = sum(pop_counts.values())
    engaged_count = pop_counts.get(Population.ENGAGED, 0)
    broken_count = pop_counts.get(Population.BROKEN, 0)

    # Overdue follow-ups
    overdue_row = conn.execute(
        """SELECT COUNT(*) as cnt FROM prospects
           WHERE follow_up_date IS NOT NULL
           AND follow_up_date < ?
           AND population NOT IN (?, ?, ?)""",
        (
            today,
            Population.DEAD_DNC.value,
            Population.CLOSED_WON.value,
            Population.LOST.value,
        ),
    ).fetchone()
    overdue_count = overdue_row["cnt"] if overdue_row else 0

    # Today's engaged follow-ups
    today_row = conn.execute(
        """SELECT COUNT(*) as cnt FROM prospects
           WHERE population = ?
           AND follow_up_date IS NOT NULL
           AND DATE(follow_up_date) = DATE(?)""",
        (Population.ENGAGED.value, today),
    ).fetchone()
    engaged_today = today_row["cnt"] if today_row else 0

    # Demos today
    demos_row = conn.execute(
        """SELECT COUNT(*) as cnt FROM prospects
           WHERE population = ?
           AND engagement_stage = 'demo_scheduled'
           AND follow_up_date IS NOT NULL
           AND DATE(follow_up_date) = DATE(?)""",
        (Population.ENGAGED.value, today),
    ).fetchone()
    demos_today = demos_row["cnt"] if demos_row else 0

    # Queue total and remaining
    queue_total = engaged_today + overdue_count + pop_counts.get(
        Population.UNENGAGED, 0
    )

    # Cards already worked today
    from datetime import datetime

    start_of_day = datetime(
        int(today[:4]), int(today[5:7]), int(today[8:10]), 0, 0, 0
    ).strftime("%Y-%m-%d %H:%M:%S")
    worked_row = conn.execute(
        """SELECT COUNT(DISTINCT prospect_id) as cnt
           FROM activities
           WHERE created_at >= ?""",
        (start_of_day,),
    ).fetchone()
    worked_today = worked_row["cnt"] if worked_row else 0
    queue_remaining = max(0, queue_total - worked_today)

    return CockpitData(
        queue_remaining=queue_remaining,
        queue_total=queue_total,
        engaged_count=engaged_count,
        demos_today=demos_today,
        overdue_count=overdue_count,
        total_prospects=total,
        broken_count=broken_count,
    )
