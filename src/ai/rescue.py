"""Rescue engine for zero-capacity mode.

When Jeff is having a bad day:
    - Generate absolute minimum: "Just do these 3 things"
    - Simplified interface
    - Lowest friction
    - No guilt trips
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import EngagementStage, Population

logger = get_logger(__name__)


@dataclass
class RescueItem:
    """A single must-do item."""

    prospect_id: int
    prospect_name: str
    company_name: str
    action: str
    reason: str
    priority: int


class RescueEngine:
    """Zero-capacity crisis mode.

    Generates the absolute minimum list of things to do today.
    Priority order:
    1. Engaged follow-ups that are due today or overdue (closing > post-demo > demo > pre-demo)
    2. Demos scheduled for today
    3. Highest-score unengaged prospects due today

    Everything else can wait.
    """

    def __init__(self, db: Database):
        self.db = db

    def generate_rescue_list(
        self,
        max_items: int = 3,
        target_date: Optional[date] = None,
    ) -> list[RescueItem]:
        """Generate minimal must-do list.

        Args:
            max_items: Maximum items to return (default 3)
            target_date: Date to evaluate (defaults to today)

        Returns:
            List of RescueItem, sorted by priority (highest first)
        """
        if target_date is None:
            target_date = date.today()

        items = self._prioritize_urgent(target_date)

        # Cap at max_items
        result = items[:max_items]

        logger.info(
            "Rescue list generated",
            extra={
                "context": {
                    "total_urgent": len(items),
                    "returned": len(result),
                    "max_items": max_items,
                }
            },
        )

        return result

    def _prioritize_urgent(self, target_date: date) -> list[RescueItem]:
        """Find and prioritize the most urgent items.

        Priority scoring:
        - Engaged + closing stage + overdue: 100
        - Engaged + post-demo + overdue: 90
        - Engaged + demo_scheduled + today: 85
        - Engaged + pre-demo + overdue: 80
        - Engaged + today (not overdue): 70
        - Unengaged + due today by score: 30-50
        """
        items: list[RescueItem] = []
        conn = self.db._get_connection()

        # Get engaged prospects with follow-ups due today or earlier
        rows = conn.execute(
            """SELECT p.id, p.first_name, p.last_name, p.engagement_stage,
                      p.follow_up_date, p.prospect_score,
                      c.name as company_name
               FROM prospects p
               LEFT JOIN companies c ON p.company_id = c.id
               WHERE p.population = ?
                 AND p.follow_up_date IS NOT NULL
                 AND DATE(p.follow_up_date) <= ?
               ORDER BY p.follow_up_date ASC""",
            (Population.ENGAGED.value, target_date.isoformat()),
        ).fetchall()

        stage_priority = {
            EngagementStage.CLOSING.value: 100,
            EngagementStage.POST_DEMO.value: 90,
            EngagementStage.DEMO_SCHEDULED.value: 85,
            EngagementStage.PRE_DEMO.value: 80,
        }

        for row in rows:
            stage = row["engagement_stage"] or EngagementStage.PRE_DEMO.value
            base_priority = stage_priority.get(stage, 70)
            name = f"{row['first_name']} {row['last_name']}".strip()
            company = row["company_name"] or "Unknown"

            # Determine action based on stage
            if stage == EngagementStage.DEMO_SCHEDULED.value:
                action = "Confirm demo"
                reason = "Demo is scheduled"
            elif stage == EngagementStage.CLOSING.value:
                action = "Follow up"
                reason = "In closing stage — keep momentum"
            elif stage == EngagementStage.POST_DEMO.value:
                action = "Follow up"
                reason = "Post-demo follow-up due"
            else:
                action = "Contact"
                reason = "Engaged follow-up due"

            items.append(
                RescueItem(
                    prospect_id=row["id"],
                    prospect_name=name,
                    company_name=company,
                    action=action,
                    reason=reason,
                    priority=base_priority,
                )
            )

        # Get unengaged prospects due today
        unengaged_rows = conn.execute(
            """SELECT p.id, p.first_name, p.last_name, p.prospect_score,
                      p.follow_up_date, c.name as company_name
               FROM prospects p
               LEFT JOIN companies c ON p.company_id = c.id
               WHERE p.population = ?
                 AND p.follow_up_date IS NOT NULL
                 AND DATE(p.follow_up_date) <= ?
               ORDER BY p.prospect_score DESC
               LIMIT 10""",
            (Population.UNENGAGED.value, target_date.isoformat()),
        ).fetchall()

        for row in unengaged_rows:
            name = f"{row['first_name']} {row['last_name']}".strip()
            company = row["company_name"] or "Unknown"
            # Score-based priority: higher score = higher priority (30-50 range)
            score = row["prospect_score"] or 0
            priority = 30 + min(20, score // 5)

            items.append(
                RescueItem(
                    prospect_id=row["id"],
                    prospect_name=name,
                    company_name=company,
                    action="Reach out",
                    reason=f"High-priority unengaged (score {score})",
                    priority=priority,
                )
            )

        # Sort by priority descending
        items.sort(key=lambda x: x.priority, reverse=True)
        return items
