"""Data export functionality.

Provides:
    - Quick export: Current filter view to CSV
    - Monthly summary report
    - Revenue and commission tracking

Usage:
    from src.engine.export import export_prospects, generate_monthly_summary

    export_prospects(prospects, Path("export.csv"))
    summary = generate_monthly_summary(db, "2026-02")
"""

import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import ActivityType, Population, Prospect

logger = get_logger(__name__)

# Default columns for prospect export
DEFAULT_COLUMNS = [
    "id",
    "first_name",
    "last_name",
    "title",
    "company_id",
    "population",
    "engagement_stage",
    "prospect_score",
    "data_confidence",
    "follow_up_date",
    "last_contact_date",
    "attempt_count",
    "source",
    "notes",
]


@dataclass
class MonthlySummary:
    """Monthly summary report.

    Attributes:
        month: Month (YYYY-MM)
        demos_booked: Number of demos scheduled
        deals_closed: Number of deals won
        total_revenue: Total deal value
        commission_earned: Commission (total x rate)
        commission_rate: Commission rate used
        calls_made: Total calls
        emails_sent: Total emails sent
        pipeline_added: New prospects added
        pipeline_engaged: New engaged prospects
        pipeline_lost: Prospects lost
        avg_deal_size: Average deal value
        avg_cycle_days: Average days to close
    """

    month: str
    demos_booked: int = 0
    deals_closed: int = 0
    total_revenue: Decimal = Decimal("0")
    commission_earned: Decimal = Decimal("0")
    commission_rate: Decimal = Decimal("0.06")
    calls_made: int = 0
    emails_sent: int = 0
    pipeline_added: int = 0
    pipeline_engaged: int = 0
    pipeline_lost: int = 0
    avg_deal_size: Optional[Decimal] = None
    avg_cycle_days: Optional[float] = None


def export_prospects(
    prospects: list[Prospect],
    path: Path,
    columns: Optional[list[str]] = None,
) -> bool:
    """Export prospects to CSV.

    Writes a CSV file with the specified columns for each prospect.
    Enum values are exported as their string value.

    Args:
        prospects: Prospects to export
        path: Output file path
        columns: Columns to include (defaults to DEFAULT_COLUMNS if None)

    Returns:
        True if export successful
    """
    if not prospects:
        logger.warning("No prospects to export")
        return False

    cols = columns or DEFAULT_COLUMNS

    try:
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Write header
            writer.writerow(cols)

            # Write data rows
            for prospect in prospects:
                row: list[str] = []
                for col in cols:
                    value = getattr(prospect, col, None)
                    if value is None:
                        row.append("")
                    elif hasattr(value, "value"):
                        # Enum types
                        row.append(str(value.value))
                    elif hasattr(value, "isoformat"):
                        # datetime/date types
                        row.append(value.isoformat())
                    else:
                        row.append(str(value))
                writer.writerow(row)

        logger.info(
            f"Exported {len(prospects)} prospects to {path}",
            extra={
                "context": {
                    "count": len(prospects),
                    "path": str(path),
                    "columns": len(cols),
                }
            },
        )
        return True

    except OSError as e:
        logger.error(
            f"Failed to export prospects: {e}",
            extra={"context": {"path": str(path), "error": str(e)}},
        )
        return False


def generate_monthly_summary(
    db: Database,
    month: str,
    commission_rate: Decimal = Decimal("0.06"),
) -> MonthlySummary:
    """Generate monthly summary report.

    Queries the database for activity and prospect data within the
    specified month to build a comprehensive summary.

    Args:
        db: Database instance
        month: Month in YYYY-MM format (e.g., "2026-02")
        commission_rate: Commission rate (default 6%)

    Returns:
        Monthly summary with all metrics
    """
    conn = db._get_connection()

    # Date range for the month
    month_start = f"{month}-01"
    # Use next month start for exclusive upper bound
    parts = month.split("-")
    year = int(parts[0])
    mon = int(parts[1])
    if mon == 12:
        next_month_start = f"{year + 1}-01-01"
    else:
        next_month_start = f"{year}-{mon + 1:02d}-01"

    summary = MonthlySummary(
        month=month,
        commission_rate=commission_rate,
    )

    # Count demos booked (DEMO_SCHEDULED activities)
    row = conn.execute(
        """SELECT COUNT(*) as cnt FROM activities
           WHERE activity_type = ? AND created_at >= ? AND created_at < ?""",
        (ActivityType.DEMO_SCHEDULED.value, month_start, next_month_start),
    ).fetchone()
    summary.demos_booked = row["cnt"] if row else 0

    # Count calls made
    row = conn.execute(
        """SELECT COUNT(*) as cnt FROM activities
           WHERE activity_type = ? AND created_at >= ? AND created_at < ?""",
        (ActivityType.CALL.value, month_start, next_month_start),
    ).fetchone()
    summary.calls_made = row["cnt"] if row else 0

    # Count emails sent
    row = conn.execute(
        """SELECT COUNT(*) as cnt FROM activities
           WHERE activity_type = ? AND created_at >= ? AND created_at < ?""",
        (ActivityType.EMAIL_SENT.value, month_start, next_month_start),
    ).fetchone()
    summary.emails_sent = row["cnt"] if row else 0

    # Count deals closed (prospects with close_date in this month)
    row = conn.execute(
        """SELECT COUNT(*) as cnt, COALESCE(SUM(deal_value), 0) as total_val
           FROM prospects
           WHERE population = ? AND close_date >= ? AND close_date < ?""",
        (Population.CLOSED_WON.value, month_start, next_month_start),
    ).fetchone()
    if row:
        summary.deals_closed = row["cnt"]
        total_revenue = Decimal(str(row["total_val"])) if row["total_val"] else Decimal("0")
        summary.total_revenue = total_revenue
        summary.commission_earned = total_revenue * commission_rate
        if summary.deals_closed > 0:
            summary.avg_deal_size = total_revenue / summary.deals_closed

    # Count new prospects added this month
    row = conn.execute(
        """SELECT COUNT(*) as cnt FROM prospects
           WHERE created_at >= ? AND created_at < ?""",
        (month_start, next_month_start),
    ).fetchone()
    summary.pipeline_added = row["cnt"] if row else 0

    # Count prospects that became engaged this month (via STATUS_CHANGE activities)
    row = conn.execute(
        """SELECT COUNT(*) as cnt FROM activities
           WHERE activity_type = ? AND population_after = ?
           AND created_at >= ? AND created_at < ?""",
        (
            ActivityType.STATUS_CHANGE.value,
            Population.ENGAGED.value,
            month_start,
            next_month_start,
        ),
    ).fetchone()
    summary.pipeline_engaged = row["cnt"] if row else 0

    # Count prospects lost this month
    row = conn.execute(
        """SELECT COUNT(*) as cnt FROM activities
           WHERE activity_type = ? AND population_after = ?
           AND created_at >= ? AND created_at < ?""",
        (
            ActivityType.STATUS_CHANGE.value,
            Population.LOST.value,
            month_start,
            next_month_start,
        ),
    ).fetchone()
    summary.pipeline_lost = row["cnt"] if row else 0

    # Calculate average cycle days for deals closed this month
    rows = conn.execute(
        """SELECT close_date, created_at FROM prospects
           WHERE population = ? AND close_date >= ? AND close_date < ?
           AND created_at IS NOT NULL""",
        (Population.CLOSED_WON.value, month_start, next_month_start),
    ).fetchall()
    if rows:
        total_days = 0.0
        valid_count = 0
        for r in rows:
            if r["close_date"] and r["created_at"]:
                try:
                    # Parse dates - close_date is DATE, created_at is TIMESTAMP
                    close_str = str(r["close_date"])
                    created_str = str(r["created_at"])
                    # Handle both date and datetime formats
                    if "T" in close_str or " " in close_str:
                        close_parts = close_str.split("T")[0].split(" ")[0]
                    else:
                        close_parts = close_str
                    if "T" in created_str or " " in created_str:
                        created_parts = created_str.split("T")[0].split(" ")[0]
                    else:
                        created_parts = created_str

                    from datetime import date as date_type

                    close_y, close_m, close_d = close_parts.split("-")
                    created_y, created_m, created_d = created_parts.split("-")
                    close_dt = date_type(int(close_y), int(close_m), int(close_d))
                    created_dt = date_type(int(created_y), int(created_m), int(created_d))
                    days = (close_dt - created_dt).days
                    if days >= 0:
                        total_days += days
                        valid_count += 1
                except (ValueError, TypeError, IndexError):
                    continue
        if valid_count > 0:
            summary.avg_cycle_days = total_days / valid_count

    logger.info(
        f"Monthly summary generated for {month}",
        extra={
            "context": {
                "month": month,
                "demos": summary.demos_booked,
                "deals": summary.deals_closed,
                "revenue": str(summary.total_revenue),
            }
        },
    )

    return summary


def export_summary_csv(summary: MonthlySummary, path: Path) -> bool:
    """Export summary as CSV.

    Writes a two-column CSV with metric name and value.

    Args:
        summary: Monthly summary
        path: Output file path

    Returns:
        True if export successful
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Metric", "Value"])
            writer.writerow(["Month", summary.month])
            writer.writerow(["Demos Booked", summary.demos_booked])
            writer.writerow(["Deals Closed", summary.deals_closed])
            writer.writerow(["Total Revenue", str(summary.total_revenue)])
            writer.writerow(["Commission Rate", str(summary.commission_rate)])
            writer.writerow(["Commission Earned", str(summary.commission_earned)])
            writer.writerow(["Calls Made", summary.calls_made])
            writer.writerow(["Emails Sent", summary.emails_sent])
            writer.writerow(["Pipeline Added", summary.pipeline_added])
            writer.writerow(["Pipeline Engaged", summary.pipeline_engaged])
            writer.writerow(["Pipeline Lost", summary.pipeline_lost])
            writer.writerow(["Avg Deal Size", str(summary.avg_deal_size or "")])
            writer.writerow(["Avg Cycle Days", str(summary.avg_cycle_days or "")])

        logger.info(
            f"Summary CSV exported to {path}",
            extra={"context": {"path": str(path), "month": summary.month}},
        )
        return True

    except OSError as e:
        logger.error(
            f"Failed to export summary CSV: {e}",
            extra={"context": {"path": str(path), "error": str(e)}},
        )
        return False
