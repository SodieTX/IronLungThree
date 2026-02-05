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
from typing import Any, Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import Prospect

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

    # Populations that should be checked for stale data
    ACTIVE_POPULATIONS = [
        "unengaged",
        "engaged",
        "broken",
    ]

    def flag_stale_records(self) -> list[int]:
        """Flag records with stale data.

        Updates data_freshness table with flagged fields.

        Returns:
            List of prospect IDs flagged
        """
        flagged_ids: list[int] = []

        # Gather all prospects in active populations
        from src.db.models import Population

        active_pops = [
            Population.UNENGAGED,
            Population.ENGAGED,
            Population.BROKEN,
        ]

        prospects: list[Prospect] = []
        for pop in active_pops:
            prospects.extend(self.db.get_prospects(population=pop, limit=10000))

        for prospect in prospects:
            if prospect.id is None:
                continue

            stale_fields: list[str] = []

            # Check email freshness
            email_days = self._check_email_freshness(prospect.id)
            if email_days is not None:
                stale_fields.append("email")

            # Check phone freshness
            phone_days = self._check_phone_freshness(prospect.id)
            if phone_days is not None:
                stale_fields.append("phone")

            # Check title freshness
            title_days = self._check_title_freshness(prospect.id)
            if title_days is not None:
                stale_fields.append("title")

            # Check company existence freshness
            company_days = self._check_company_freshness(prospect)
            if company_days is not None:
                stale_fields.append("company")

            if stale_fields:
                flagged_ids.append(prospect.id)
                logger.info(
                    "Prospect flagged with stale data",
                    extra={
                        "context": {
                            "prospect_id": prospect.id,
                            "stale_fields": stale_fields,
                        }
                    },
                )

        logger.info(
            "Stale record flagging complete",
            extra={"context": {"total_flagged": len(flagged_ids)}},
        )
        return flagged_ids

    def get_stale_by_priority(self, limit: int = 50) -> list[StaleRecord]:
        """Get stale records ordered by priority.

        Priority = days_stale x prospect_score
        High-value stale data gets attention first.

        Args:
            limit: Maximum records to return

        Returns:
            Stale records ordered by priority
        """
        from src.db.models import Population

        active_pops = [
            Population.UNENGAGED,
            Population.ENGAGED,
            Population.BROKEN,
        ]

        prospects: list[Prospect] = []
        for pop in active_pops:
            prospects.extend(self.db.get_prospects(population=pop, limit=10000))

        stale_records: list[StaleRecord] = []

        for prospect in prospects:
            if prospect.id is None:
                continue

            stale_fields: list[str] = []
            max_days_stale = 0

            email_days = self._check_email_freshness(prospect.id)
            if email_days is not None:
                stale_fields.append("email")
                max_days_stale = max(max_days_stale, email_days)

            phone_days = self._check_phone_freshness(prospect.id)
            if phone_days is not None:
                stale_fields.append("phone")
                max_days_stale = max(max_days_stale, phone_days)

            title_days = self._check_title_freshness(prospect.id)
            if title_days is not None:
                stale_fields.append("title")
                max_days_stale = max(max_days_stale, title_days)

            company_days = self._check_company_freshness(prospect)
            if company_days is not None:
                stale_fields.append("company")
                max_days_stale = max(max_days_stale, company_days)

            if stale_fields:
                # Fetch company name for display
                company = self.db.get_company(prospect.company_id) if prospect.company_id else None
                company_name = company.name if company else "Unknown"

                priority_score = float(max_days_stale) * float(prospect.prospect_score or 1)

                stale_records.append(
                    StaleRecord(
                        prospect_id=prospect.id,
                        prospect_name=prospect.full_name,
                        company_name=company_name,
                        stale_fields=stale_fields,
                        days_stale=max_days_stale,
                        priority_score=priority_score,
                    )
                )

        # Sort by priority_score descending, take top N
        stale_records.sort(key=lambda r: r.priority_score, reverse=True)
        return stale_records[:limit]

    def _check_field_freshness(
        self, prospect_id: int, field_name: str, threshold_days: int
    ) -> Optional[int]:
        """Check freshness for a specific field.

        Looks up data_freshness records for the prospect and field.
        If no record exists, the data has never been verified and is
        considered stale (returns threshold_days + 1).
        If a record exists but is older than threshold, returns days since
        verification.

        Returns:
            Days since verification if stale, or None if fresh.
        """
        freshness_records = self.db.get_data_freshness(prospect_id)

        # Find the most recent record for this field
        field_records = [r for r in freshness_records if r.get("field_name") == field_name]

        if not field_records:
            # Never verified - considered stale
            return threshold_days + 1

        # Get most recent by verified_date (records are already sorted DESC)
        latest = field_records[0]
        verified_date = latest.get("verified_date")

        if verified_date is None:
            return threshold_days + 1

        # Parse verified_date if it's a string
        if isinstance(verified_date, str):
            try:
                verified_date = date.fromisoformat(verified_date)
            except (ValueError, TypeError):
                return threshold_days + 1

        days_since = (date.today() - verified_date).days
        if days_since > threshold_days:
            return days_since

        return None

    def _check_email_freshness(self, prospect_id: int) -> Optional[int]:
        """Check email verification freshness.

        Returns days since verification, or None if fresh.
        """
        # Only check if the prospect actually has an email
        contact_methods = self.db.get_contact_methods(prospect_id)
        has_email = any(
            m.type.value == "email" if hasattr(m.type, "value") else m.type == "email"
            for m in contact_methods
        )
        if not has_email:
            return None

        return self._check_field_freshness(prospect_id, "email", self.thresholds.email_days)

    def _check_phone_freshness(self, prospect_id: int) -> Optional[int]:
        """Check phone verification freshness."""
        contact_methods = self.db.get_contact_methods(prospect_id)
        has_phone = any(
            m.type.value == "phone" if hasattr(m.type, "value") else m.type == "phone"
            for m in contact_methods
        )
        if not has_phone:
            return None

        return self._check_field_freshness(prospect_id, "phone", self.thresholds.phone_days)

    def _check_title_freshness(self, prospect_id: int) -> Optional[int]:
        """Check title verification freshness."""
        prospect = self.db.get_prospect(prospect_id)
        if not prospect or not prospect.title:
            return None

        return self._check_field_freshness(prospect_id, "title", self.thresholds.title_days)

    def _check_company_freshness(self, prospect: Prospect) -> Optional[int]:
        """Check company existence verification freshness.

        Returns days since verification, or None if fresh.
        """
        if not prospect.company_id:
            return None

        assert prospect.id is not None
        return self._check_field_freshness(prospect.id, "company", self.thresholds.company_days)

    def run_maintenance(self) -> dict[str, Any]:
        """Run full maintenance cycle.

        Called during nightly cycle.

        Returns:
            Dict with counts: {"flagged": N, "by_field": {...}}
        """
        logger.info("Starting groundskeeper maintenance cycle")

        flagged_ids = self.flag_stale_records()

        # Count stale fields across all flagged records
        by_field: dict[str, int] = {
            "email": 0,
            "phone": 0,
            "title": 0,
            "company": 0,
        }

        for prospect_id in flagged_ids:
            if self._check_email_freshness(prospect_id) is not None:
                by_field["email"] += 1
            if self._check_phone_freshness(prospect_id) is not None:
                by_field["phone"] += 1
            if self._check_title_freshness(prospect_id) is not None:
                by_field["title"] += 1
            prospect = self.db.get_prospect(prospect_id)
            if prospect and self._check_company_freshness(prospect) is not None:
                by_field["company"] += 1

        result = {
            "flagged": len(flagged_ids),
            "by_field": by_field,
        }

        logger.info(
            "Groundskeeper maintenance complete",
            extra={"context": result},
        )
        return result
