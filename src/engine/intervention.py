"""Intervention engine - Detect pipeline decay.

Identifies problems before they become disasters:
    - Overdue follow-ups
    - Stale engaged leads (no movement in 2+ weeks)
    - Unworked cards
    - High-score prospects with low data confidence

Usage:
    from src.engine.intervention import InterventionEngine

    engine = InterventionEngine(db)
    report = engine.detect_decay()
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import Population, Prospect

logger = get_logger(__name__)


@dataclass
class DecayItem:
    """A single decay/problem item.

    Attributes:
        prospect_id: Prospect ID
        prospect_name: Prospect name
        company_name: Company name
        issue_type: Type of issue
        description: Human-readable description
        days_stale: Days since last activity
        severity: high, medium, low
    """

    prospect_id: int
    prospect_name: str
    company_name: str
    issue_type: str
    description: str
    days_stale: int = 0
    severity: str = "medium"


@dataclass
class DecayReport:
    """Full decay report.

    Attributes:
        overdue_followups: Missed follow-up dates
        stale_engaged: Engaged with no recent activity
        unworked: Cards never worked
        low_confidence_high_score: Data quality issues
        total_issues: Total issue count
    """

    overdue_followups: list[DecayItem] = field(default_factory=list)
    stale_engaged: list[DecayItem] = field(default_factory=list)
    unworked: list[DecayItem] = field(default_factory=list)
    low_confidence_high_score: list[DecayItem] = field(default_factory=list)

    @property
    def total_issues(self) -> int:
        """Total number of issues."""
        return (
            len(self.overdue_followups)
            + len(self.stale_engaged)
            + len(self.unworked)
            + len(self.low_confidence_high_score)
        )

    @property
    def has_critical(self) -> bool:
        """Whether there are high-severity issues."""
        for item in self.overdue_followups + self.stale_engaged:
            if item.severity == "high":
                return True
        return False


class InterventionEngine:
    """Pipeline decay detection.

    Runs during nightly cycle and surfaces issues in morning brief.
    """

    def __init__(
        self,
        db: Database,
        stale_engaged_days: int = 14,
        unworked_days: int = 30,
        high_score_threshold: int = 70,
        low_confidence_threshold: int = 40,
    ):
        """Initialize intervention engine.

        Args:
            db: Database instance
            stale_engaged_days: Days before engaged is "stale"
            unworked_days: Days before card is "unworked"
            high_score_threshold: Score above which data quality matters
            low_confidence_threshold: Confidence below which is concerning
        """
        self.db = db
        self.stale_engaged_days = stale_engaged_days
        self.unworked_days = unworked_days
        self.high_score_threshold = high_score_threshold
        self.low_confidence_threshold = low_confidence_threshold

    def detect_decay(self) -> DecayReport:
        """Run full decay detection.

        Returns:
            DecayReport with all issues found
        """
        report = DecayReport(
            overdue_followups=self._find_overdue_followups(),
            stale_engaged=self._find_stale_engaged(),
            unworked=self._find_unworked(),
            low_confidence_high_score=self._find_data_quality_issues(),
        )
        logger.info(
            "Decay detection complete",
            extra={
                "context": {
                    "total_issues": report.total_issues,
                    "overdue": len(report.overdue_followups),
                    "stale_engaged": len(report.stale_engaged),
                    "unworked": len(report.unworked),
                    "data_quality": len(report.low_confidence_high_score),
                    "has_critical": report.has_critical,
                }
            },
        )
        return report

    def _find_overdue_followups(self) -> list[DecayItem]:
        """Find prospects with missed follow-up dates."""
        conn = self.db._get_connection()
        today = date.today()
        today_iso = today.isoformat()

        rows = conn.execute(
            """SELECT p.id, p.first_name, p.last_name, p.follow_up_date,
                      p.population, c.name as company_name
               FROM prospects p
               LEFT JOIN companies c ON p.company_id = c.id
               WHERE p.follow_up_date IS NOT NULL
                 AND DATE(p.follow_up_date) < DATE(?)
                 AND p.population NOT IN (?, ?, ?)
               ORDER BY p.follow_up_date ASC""",
            (
                today_iso,
                Population.DEAD_DNC.value,
                Population.CLOSED_WON.value,
                Population.LOST.value,
            ),
        ).fetchall()

        items = []
        for row in rows:
            try:
                fu_str = str(row["follow_up_date"])[:10]
                fu_date = date.fromisoformat(fu_str)
                days_overdue = (today - fu_date).days
            except (ValueError, TypeError):
                days_overdue = 0

            severity = "high" if days_overdue >= 7 else "medium" if days_overdue >= 3 else "low"

            name = f"{row['first_name']} {row['last_name']}".strip()
            items.append(
                DecayItem(
                    prospect_id=row["id"],
                    prospect_name=name,
                    company_name=row["company_name"] or "Unknown",
                    issue_type="overdue_followup",
                    description=f"Follow-up was due {days_overdue} days ago ({fu_str})",
                    days_stale=days_overdue,
                    severity=severity,
                )
            )

        return items

    def _find_stale_engaged(self) -> list[DecayItem]:
        """Find engaged prospects with no recent activity."""
        conn = self.db._get_connection()
        today = date.today()
        cutoff = (today - timedelta(days=self.stale_engaged_days)).isoformat()

        rows = conn.execute(
            """SELECT p.id, p.first_name, p.last_name, p.engagement_stage,
                      c.name as company_name,
                      MAX(a.created_at) as last_activity
               FROM prospects p
               LEFT JOIN companies c ON p.company_id = c.id
               LEFT JOIN activities a ON a.prospect_id = p.id
               WHERE p.population = ?
               GROUP BY p.id
               HAVING last_activity IS NULL OR DATE(last_activity) < DATE(?)""",
            (Population.ENGAGED.value, cutoff),
        ).fetchall()

        items = []
        for row in rows:
            if row["last_activity"]:
                try:
                    last_str = str(row["last_activity"])[:10]
                    last_date = date.fromisoformat(last_str)
                    days_stale = (today - last_date).days
                except (ValueError, TypeError):
                    days_stale = self.stale_engaged_days
            else:
                days_stale = self.stale_engaged_days

            severity = "high" if days_stale >= 21 else "medium"

            name = f"{row['first_name']} {row['last_name']}".strip()
            stage = row["engagement_stage"] or "unknown"
            items.append(
                DecayItem(
                    prospect_id=row["id"],
                    prospect_name=name,
                    company_name=row["company_name"] or "Unknown",
                    issue_type="stale_engaged",
                    description=f"Engaged ({stage}) with no activity for {days_stale} days",
                    days_stale=days_stale,
                    severity=severity,
                )
            )

        return items

    def _find_unworked(self) -> list[DecayItem]:
        """Find prospects that have never been worked."""
        conn = self.db._get_connection()
        today = date.today()
        cutoff = (today - timedelta(days=self.unworked_days)).isoformat()

        rows = conn.execute(
            """SELECT p.id, p.first_name, p.last_name, p.created_at,
                      p.prospect_score, c.name as company_name
               FROM prospects p
               LEFT JOIN companies c ON p.company_id = c.id
               LEFT JOIN activities a ON a.prospect_id = p.id
                   AND a.activity_type IN ('call', 'voicemail', 'email_sent', 'demo')
               WHERE p.population = ?
                 AND DATE(p.created_at) < DATE(?)
                 AND a.id IS NULL
               ORDER BY p.prospect_score DESC""",
            (Population.UNENGAGED.value, cutoff),
        ).fetchall()

        items = []
        for row in rows:
            try:
                created_str = str(row["created_at"])[:10]
                created_date = date.fromisoformat(created_str)
                days_stale = (today - created_date).days
            except (ValueError, TypeError):
                days_stale = self.unworked_days

            severity = "high" if row["prospect_score"] >= 70 else "medium" if days_stale >= 60 else "low"

            name = f"{row['first_name']} {row['last_name']}".strip()
            items.append(
                DecayItem(
                    prospect_id=row["id"],
                    prospect_name=name,
                    company_name=row["company_name"] or "Unknown",
                    issue_type="unworked",
                    description=f"Imported {days_stale} days ago, never contacted (score: {row['prospect_score']})",
                    days_stale=days_stale,
                    severity=severity,
                )
            )

        return items

    def _find_data_quality_issues(self) -> list[DecayItem]:
        """Find high-score prospects with low data confidence."""
        conn = self.db._get_connection()

        rows = conn.execute(
            """SELECT p.id, p.first_name, p.last_name, p.prospect_score,
                      p.data_confidence, c.name as company_name
               FROM prospects p
               LEFT JOIN companies c ON p.company_id = c.id
               WHERE p.prospect_score >= ?
                 AND p.data_confidence <= ?
                 AND p.population NOT IN (?, ?, ?)
               ORDER BY p.prospect_score DESC""",
            (
                self.high_score_threshold,
                self.low_confidence_threshold,
                Population.DEAD_DNC.value,
                Population.CLOSED_WON.value,
                Population.LOST.value,
            ),
        ).fetchall()

        items = []
        for row in rows:
            name = f"{row['first_name']} {row['last_name']}".strip()
            items.append(
                DecayItem(
                    prospect_id=row["id"],
                    prospect_name=name,
                    company_name=row["company_name"] or "Unknown",
                    issue_type="low_confidence_high_score",
                    description=(
                        f"Score {row['prospect_score']} but confidence only "
                        f"{row['data_confidence']} — data may be stale or wrong"
                    ),
                    days_stale=0,
                    severity="medium",
                )
            )

        return items
