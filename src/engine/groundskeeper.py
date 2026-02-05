"""Groundskeeper - Continuous database maintenance.

Flags stale data for manual review:
    - Email: 90 days
    - Phone: 180 days
    - Title: 120 days
    - Company existence: 180 days

Does NOT auto-verify. Flags for Jeff to check.

Usage:
    from src.engine.groundskeeper import Groundskeeper

    keeper = Groundskeeper(db)
    flagged = keeper.flag_stale_records()
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from src.db.database import Database
from src.db.models import Prospect
from src.core.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# STALE THRESHOLDS
# =============================================================================


@dataclass
class StaleThresholds:
    """Days before data is considered stale."""

    email_days: int = 90
    phone_days: int = 180
    title_days: int = 120
    company_days: int = 180


DEFAULT_THRESHOLDS = StaleThresholds()


@dataclass
class StaleRecord:
    """A record with stale data.

    Attributes:
        prospect_id: Prospect ID
        prospect_name: Prospect name
        company_name: Company name
        stale_fields: List of stale field names
        days_stale: Days since last verification
        priority_score: Higher = more urgent (age × prospect score)
    """

    prospect_id: int
    prospect_name: str
    company_name: str
    stale_fields: list[str]
    days_stale: int
    priority_score: float


class Groundskeeper:
    """Database maintenance and data freshness.

    Runs during nightly cycle to flag records needing attention.
    """

    def __init__(
        self,
        db: Database,
        thresholds: StaleThresholds = DEFAULT_THRESHOLDS,
    ):
        """Initialize groundskeeper.

        Args:
            db: Database instance
            thresholds: Stale data thresholds
        """
        self.db = db
        self.thresholds = thresholds

    def flag_stale_records(self) -> list[int]:
        """Flag records with stale data.

        Updates data_freshness table with flagged fields.

        Returns:
            List of prospect IDs flagged
        """
        raise NotImplementedError("Phase 5, Step 5.2")

    def get_stale_by_priority(self, limit: int = 50) -> list[StaleRecord]:
        """Get stale records ordered by priority.

        Priority = days_stale × prospect_score
        High-value stale data gets attention first.

        Args:
            limit: Maximum records to return

        Returns:
            Stale records ordered by priority
        """
        raise NotImplementedError("Phase 5, Step 5.2")

    def _check_email_freshness(self, prospect_id: int) -> Optional[int]:
        """Check email verification freshness.

        Returns days since verification, or None if fresh.
        """
        raise NotImplementedError("Phase 5, Step 5.2")

    def _check_phone_freshness(self, prospect_id: int) -> Optional[int]:
        """Check phone verification freshness."""
        raise NotImplementedError("Phase 5, Step 5.2")

    def _check_title_freshness(self, prospect_id: int) -> Optional[int]:
        """Check title verification freshness."""
        raise NotImplementedError("Phase 5, Step 5.2")

    def run_maintenance(self) -> dict[str, int]:
        """Run full maintenance cycle.

        Called during nightly cycle.

        Returns:
            Dict with counts: {"flagged": N, "by_field": {...}}
        """
        raise NotImplementedError("Phase 5, Step 5.2")
