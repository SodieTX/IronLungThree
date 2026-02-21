"""Engagement velocity tracking — deal momentum analysis.

Tracks how fast deals move through the pipeline:
    - Days in current stage vs historical average
    - Response time trends (getting slower = deal cooling)
    - Acceleration/deceleration signals

Usage:
    from src.engine.engagement_velocity import EngagementVelocity

    velocity = EngagementVelocity(db)
    report = velocity.analyze()
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import ActivityType, EngagementStage, Population

logger = get_logger(__name__)


@dataclass
class DealMomentum:
    """Momentum signal for a single prospect.

    Attributes:
        prospect_id: Prospect ID
        prospect_name: Full name
        company_name: Company name
        current_stage: Current engagement stage
        days_in_stage: Days spent in current stage
        avg_days_in_stage: Historical average for this stage
        momentum: 'accelerating', 'normal', 'decelerating', 'stalled'
        detail: Human-readable explanation
    """

    prospect_id: int
    prospect_name: str
    company_name: str
    current_stage: str
    days_in_stage: int
    avg_days_in_stage: float
    momentum: str  # accelerating, normal, decelerating, stalled
    detail: str


@dataclass
class VelocityReport:
    """Full velocity analysis.

    Attributes:
        deals: All engaged deals with momentum signals
        decelerating: Deals losing momentum
        stalled: Deals with no movement
        accelerating: Deals moving faster than average
        avg_cycle_days: Average days from engaged to close (all-time)
    """

    deals: list[DealMomentum] = field(default_factory=list)
    decelerating: list[DealMomentum] = field(default_factory=list)
    stalled: list[DealMomentum] = field(default_factory=list)
    accelerating: list[DealMomentum] = field(default_factory=list)
    avg_cycle_days: Optional[float] = None

    @property
    def summary(self) -> str:
        """One-line summary for morning brief."""
        parts = []
        if self.accelerating:
            parts.append(f"{len(self.accelerating)} accelerating")
        if self.decelerating:
            parts.append(f"{len(self.decelerating)} slowing down")
        if self.stalled:
            parts.append(f"{len(self.stalled)} stalled")
        if not parts:
            return "All engaged deals moving at normal pace."
        return "Deal momentum: " + ", ".join(parts) + "."


class EngagementVelocity:
    """Analyze deal momentum across the engaged pipeline."""

    # Thresholds: days in stage before flagging
    _STAGE_THRESHOLDS = {
        EngagementStage.PRE_DEMO.value: 14,  # 2 weeks to get a demo scheduled
        EngagementStage.DEMO_SCHEDULED.value: 7,  # 1 week between scheduling and demo
        EngagementStage.POST_DEMO.value: 14,  # 2 weeks for follow-up after demo
        EngagementStage.CLOSING.value: 21,  # 3 weeks to close
    }

    def __init__(self, db: Database):
        self.db = db

    def analyze(self) -> VelocityReport:
        """Analyze velocity for all engaged prospects.

        Returns:
            VelocityReport with momentum signals for each deal
        """
        report = VelocityReport()

        # Calculate historical averages from closed deals
        report.avg_cycle_days = self._avg_cycle_days()
        stage_avgs = self._avg_days_per_stage()

        # Get all engaged prospects
        engaged = self.db.get_prospects(population=Population.ENGAGED.value)

        for prospect in engaged:
            if not prospect.id:
                continue

            stage = prospect.engagement_stage.value if prospect.engagement_stage else "pre_demo"
            company = self.db.get_company(prospect.company_id) if prospect.company_id else None
            company_name = company.name if company else "Unknown"

            # Calculate days in current stage
            days_in_stage = self._days_in_current_stage(prospect.id, stage)
            avg_for_stage = stage_avgs.get(stage, float(self._STAGE_THRESHOLDS.get(stage, 14)))

            # Determine momentum
            if avg_for_stage > 0:
                ratio = days_in_stage / avg_for_stage
            else:
                ratio = 0

            if ratio > 2.0:
                momentum = "stalled"
                detail = (
                    f"In {stage} for {days_in_stage} days "
                    f"(avg is {avg_for_stage:.0f}). This deal may be dead."
                )
            elif ratio > 1.3:
                momentum = "decelerating"
                detail = (
                    f"In {stage} for {days_in_stage} days "
                    f"(avg is {avg_for_stage:.0f}). Losing momentum."
                )
            elif ratio < 0.5 and days_in_stage >= 2:
                momentum = "accelerating"
                detail = (
                    f"In {stage} for only {days_in_stage} days "
                    f"(avg is {avg_for_stage:.0f}). Moving fast."
                )
            else:
                momentum = "normal"
                detail = f"In {stage} for {days_in_stage} days (avg is {avg_for_stage:.0f})."

            deal = DealMomentum(
                prospect_id=prospect.id,
                prospect_name=prospect.full_name,
                company_name=company_name,
                current_stage=stage,
                days_in_stage=days_in_stage,
                avg_days_in_stage=avg_for_stage,
                momentum=momentum,
                detail=detail,
            )
            report.deals.append(deal)

            if momentum == "stalled":
                report.stalled.append(deal)
            elif momentum == "decelerating":
                report.decelerating.append(deal)
            elif momentum == "accelerating":
                report.accelerating.append(deal)

        logger.info(
            "Velocity analysis complete",
            extra={
                "context": {
                    "total_deals": len(report.deals),
                    "accelerating": len(report.accelerating),
                    "decelerating": len(report.decelerating),
                    "stalled": len(report.stalled),
                }
            },
        )
        return report

    def _days_in_current_stage(self, prospect_id: int, stage: str) -> int:
        """Calculate days since last stage transition."""
        conn = self.db._get_connection()

        # Find the most recent STATUS_CHANGE activity for this prospect
        row = conn.execute(
            """SELECT created_at FROM activities
               WHERE prospect_id = ?
               AND activity_type = ?
               ORDER BY created_at DESC
               LIMIT 1""",
            (prospect_id, ActivityType.STATUS_CHANGE.value),
        ).fetchone()

        if row and row["created_at"]:
            try:
                transition_date = date.fromisoformat(str(row["created_at"])[:10])
                return (date.today() - transition_date).days
            except (ValueError, TypeError):
                pass

        # Fallback: use prospect created_at
        prospect = self.db.get_prospect(prospect_id)
        if prospect and prospect.created_at:
            try:
                created = date.fromisoformat(str(prospect.created_at)[:10])
                return (date.today() - created).days
            except (ValueError, TypeError):
                pass

        return 0

    def _avg_cycle_days(self) -> Optional[float]:
        """Calculate average days from first engaged to close (won or lost)."""
        conn = self.db._get_connection()

        rows = conn.execute(
            """SELECT prospect_id,
                      MIN(created_at) as first_engaged,
                      MAX(created_at) as closed_at
               FROM activities
               WHERE activity_type = ?
               AND (population_after = ? OR population_after = ?)
               GROUP BY prospect_id""",
            (
                ActivityType.STATUS_CHANGE.value,
                Population.CLOSED_WON.value,
                Population.LOST.value,
            ),
        ).fetchall()

        if not rows:
            return None

        # Also get when they first became engaged
        total_days = 0
        count = 0
        for row in rows:
            pid = row["prospect_id"]
            # Find when they first became engaged
            engaged_row = conn.execute(
                """SELECT MIN(created_at) as engaged_at FROM activities
                   WHERE prospect_id = ?
                   AND activity_type = ?
                   AND population_after = ?""",
                (pid, ActivityType.STATUS_CHANGE.value, Population.ENGAGED.value),
            ).fetchone()

            if engaged_row and engaged_row["engaged_at"] and row["closed_at"]:
                try:
                    start = date.fromisoformat(str(engaged_row["engaged_at"])[:10])
                    end = date.fromisoformat(str(row["closed_at"])[:10])
                    days = (end - start).days
                    if days > 0:
                        total_days += days
                        count += 1
                except (ValueError, TypeError):
                    continue

        return total_days / count if count > 0 else None

    def _avg_days_per_stage(self) -> dict[str, float]:
        """Calculate average days spent in each stage from historical data.

        Falls back to thresholds if insufficient data.
        """
        # For now, return thresholds as defaults.
        # As more deals close, this can analyze actual stage durations.
        return {k: float(v) for k, v in self._STAGE_THRESHOLDS.items()}
