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
from src.db.models import Prospect

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
        raise NotImplementedError("Phase 7, Step 7.6")

    def _find_overdue_followups(self) -> list[DecayItem]:
        """Find prospects with missed follow-up dates."""
        raise NotImplementedError("Phase 7, Step 7.6")

    def _find_stale_engaged(self) -> list[DecayItem]:
        """Find engaged prospects with no recent activity."""
        raise NotImplementedError("Phase 7, Step 7.6")

    def _find_unworked(self) -> list[DecayItem]:
        """Find prospects that have never been worked."""
        raise NotImplementedError("Phase 7, Step 7.6")

    def _find_data_quality_issues(self) -> list[DecayItem]:
        """Find high-score prospects with low data confidence."""
        raise NotImplementedError("Phase 7, Step 7.6")
