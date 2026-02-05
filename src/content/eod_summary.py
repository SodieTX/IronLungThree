"""End-of-day summary generation.

Produces a summary of today's activity:
    - Cards processed count
    - Calls made, emails sent
    - Demos scheduled, deals closed
    - Pipeline movement
    - Tomorrow preview

Usage:
    from src.content.eod_summary import generate_eod_summary

    summary = generate_eod_summary(db)
    print(summary.full_text)
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import ActivityType, Population

logger = get_logger(__name__)


@dataclass
class EODSummary:
    """End-of-day summary."""

    date: str
    cards_processed: int
    calls_made: int
    emails_sent: int
    demos_scheduled: int
    deals_closed: int
    status_changes: int
    tomorrow_preview: str
    full_text: str = ""


def generate_eod_summary(db: Database) -> EODSummary:
    """Generate end-of-day summary.

    Args:
        db: Database instance

    Returns:
        EODSummary with today's stats
    """
    today = date.today()
    today_str = today.strftime("%A, %B %d, %Y")

    conn = db._get_connection()
    start_of_day = datetime(today.year, today.month, today.day, 0, 0, 0).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    # Count today's activities by type
    activity_counts = conn.execute(
        """SELECT activity_type, COUNT(*) as cnt
           FROM activities
           WHERE created_at >= ?
           GROUP BY activity_type""",
        (start_of_day,),
    ).fetchall()

    counts: dict[str, int] = {}
    for row in activity_counts:
        counts[row["activity_type"]] = row["cnt"]

    calls_made = counts.get(ActivityType.CALL.value, 0) + counts.get(
        ActivityType.VOICEMAIL.value, 0
    )
    emails_sent = counts.get(ActivityType.EMAIL_SENT.value, 0)
    demos_scheduled = counts.get(ActivityType.DEMO_SCHEDULED.value, 0)
    status_changes = counts.get(ActivityType.STATUS_CHANGE.value, 0)

    # Cards processed = total activities for unique prospects today
    cards_row = conn.execute(
        """SELECT COUNT(DISTINCT prospect_id) as cnt
           FROM activities
           WHERE created_at >= ?""",
        (start_of_day,),
    ).fetchone()
    cards_processed = cards_row["cnt"] if cards_row else 0

    # Deals closed today
    deals_row = conn.execute(
        """SELECT COUNT(*) as cnt FROM prospects
           WHERE population = ? AND close_date = ?""",
        (Population.CLOSED_WON.value, today.isoformat()),
    ).fetchone()
    deals_closed = deals_row["cnt"] if deals_row else 0

    # Tomorrow preview
    tomorrow = today + timedelta(days=1)
    # Skip to Monday if tomorrow is weekend
    while tomorrow.weekday() >= 5:
        tomorrow += timedelta(days=1)

    tomorrow_iso = tomorrow.isoformat()
    tomorrow_follow_ups = conn.execute(
        """SELECT COUNT(*) as cnt FROM prospects
           WHERE follow_up_date IS NOT NULL
           AND DATE(follow_up_date) = DATE(?)
           AND population NOT IN (?, ?, ?)""",
        (
            tomorrow_iso,
            Population.DEAD_DNC.value,
            Population.CLOSED_WON.value,
            Population.LOST.value,
        ),
    ).fetchone()
    tomorrow_count = tomorrow_follow_ups["cnt"] if tomorrow_follow_ups else 0

    tomorrow_preview = f"{tomorrow.strftime('%A')}: {tomorrow_count} follow-ups scheduled"

    # Build full text
    full_lines = [
        "IRONLUNG 3 - END OF DAY",
        today_str,
        "",
        "--- TODAY'S ACTIVITY ---",
        f"  Cards worked: {cards_processed}",
        f"  Calls made: {calls_made}",
        f"  Emails sent: {emails_sent}",
    ]

    if demos_scheduled > 0:
        full_lines.append(f"  Demos scheduled: {demos_scheduled}")
    if deals_closed > 0:
        full_lines.append(f"  DEALS CLOSED: {deals_closed}")
    if status_changes > 0:
        full_lines.append(f"  Pipeline moves: {status_changes}")

    full_lines.append("")
    full_lines.append("--- TOMORROW ---")
    full_lines.append(f"  {tomorrow_preview}")
    full_lines.append("")

    if cards_processed == 0:
        full_lines.append("No cards processed today. Tomorrow is a new day.")
    elif cards_processed >= 20:
        full_lines.append(f"{cards_processed} cards processed. Strong day.")
    else:
        full_lines.append(f"{cards_processed} cards processed. Good work.")

    full_text = "\n".join(full_lines)

    return EODSummary(
        date=today_str,
        cards_processed=cards_processed,
        calls_made=calls_made,
        emails_sent=emails_sent,
        demos_scheduled=demos_scheduled,
        deals_closed=deals_closed,
        status_changes=status_changes,
        tomorrow_preview=tomorrow_preview,
        full_text=full_text,
    )
