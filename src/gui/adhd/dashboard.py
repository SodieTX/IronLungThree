"""Glanceable dashboard - One-second progress read.

Small widget showing today's stats at a glance:
cards processed, calls, emails, demos, streak.

Data is gathered from the database (activities today)
and the dopamine engine (streak).
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import ActivityType

logger = get_logger(__name__)


@dataclass
class DashboardData:
    cards_processed: int
    cards_total: int
    calls_made: int
    emails_sent: int
    demos_scheduled: int
    current_streak: int


class DashboardService:
    """Gathers dashboard data from the database and dopamine engine.

    The service queries today's activities and combines them with
    the current streak for a single glanceable object.
    """

    def __init__(self, db: Database):
        self._db = db

    def get_dashboard_data(
        self,
        current_streak: int = 0,
        cards_total: int = 0,
        target_date: Optional[date] = None,
    ) -> DashboardData:
        """Get current dashboard stats for today.

        Args:
            current_streak: Current streak count from DopamineEngine
            cards_total: Total cards in today's queue
            target_date: Date to query (defaults to today)

        Returns:
            DashboardData with all stats
        """
        if target_date is None:
            target_date = date.today()

        conn = self._db._get_connection()

        # Count today's activities by type
        date_str = target_date.isoformat()
        rows = conn.execute(
            """SELECT activity_type, COUNT(*) as cnt
               FROM activities
               WHERE DATE(created_at) = ?
               GROUP BY activity_type""",
            (date_str,),
        ).fetchall()

        type_counts: dict[str, int] = {}
        for row in rows:
            type_counts[row["activity_type"]] = row["cnt"]

        # Cards processed = status changes + skips + defers
        cards_processed = (
            type_counts.get(ActivityType.STATUS_CHANGE.value, 0)
            + type_counts.get(ActivityType.SKIP.value, 0)
            + type_counts.get(ActivityType.DEFER.value, 0)
        )

        calls_made = type_counts.get(ActivityType.CALL.value, 0) + type_counts.get(
            ActivityType.VOICEMAIL.value, 0
        )

        emails_sent = type_counts.get(ActivityType.EMAIL_SENT.value, 0)

        demos_scheduled = type_counts.get(ActivityType.DEMO_SCHEDULED.value, 0)

        return DashboardData(
            cards_processed=cards_processed,
            cards_total=cards_total,
            calls_made=calls_made,
            emails_sent=emails_sent,
            demos_scheduled=demos_scheduled,
            current_streak=current_streak,
        )
