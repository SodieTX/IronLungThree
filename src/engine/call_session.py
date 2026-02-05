"""Call session service for call mode view.

Prepares prospect data for phone calls:
    - Phone number lookup and formatting
    - Recent interaction history
    - Quick talking points
    - Call outcome logging

Usage:
    from src.engine.call_session import CallSession

    session = CallSession(db)
    prep = session.prepare_call(prospect_id=1)
    session.log_outcome(prospect_id=1, outcome="spoke_with", notes="...")
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import (
    Activity,
    ActivityOutcome,
    ActivityType,
    ContactMethodType,
)

logger = get_logger(__name__)


@dataclass
class CallPrep:
    """Prepared data for a phone call.

    Attributes:
        prospect_id: Prospect ID
        prospect_name: Full name
        company_name: Company name
        title: Prospect title
        phone_number: Best phone number to call
        phone_label: Phone label (work, cell, etc.)
        attempt_number: Which attempt this is
        last_contact_summary: Brief summary of last interaction
        talking_points: Quick bullet points for the call
        recent_notes: Last few activity notes
        timezone: Prospect's timezone
    """

    prospect_id: int
    prospect_name: str
    company_name: str
    title: str = ""
    phone_number: str = ""
    phone_label: str = ""
    attempt_number: int = 0
    last_contact_summary: str = ""
    talking_points: list[str] = field(default_factory=list)
    recent_notes: list[str] = field(default_factory=list)
    timezone: str = ""


class CallSession:
    """Manages the business logic for call mode.

    Prepares call data and logs outcomes.
    """

    def __init__(self, db: Database) -> None:
        self._db = db

    def prepare_call(self, prospect_id: int) -> CallPrep:
        """Prepare all data needed for a phone call.

        Args:
            prospect_id: Target prospect ID

        Returns:
            CallPrep with all call data

        Raises:
            ValueError: If prospect not found
        """
        prospect = self._db.get_prospect(prospect_id)
        if not prospect:
            raise ValueError(f"Prospect {prospect_id} not found")

        company = self._db.get_company(prospect.company_id) if prospect.company_id else None
        company_name = company.name if company else "Unknown"
        timezone = company.timezone if company else ""

        # Get phone number
        phone, phone_label = self._get_best_phone(prospect_id)

        # Get activities for history
        activities = self._db.get_activities(prospect_id)

        # Build last contact summary
        last_contact = self._get_last_contact_summary(activities)

        # Build talking points
        talking_points = self._build_talking_points(
            prospect, company, activities
        )

        # Get recent notes
        recent_notes = self._get_recent_notes(activities, limit=3)

        return CallPrep(
            prospect_id=prospect_id,
            prospect_name=f"{prospect.first_name or ''} {prospect.last_name or ''}".strip(),
            company_name=company_name,
            title=prospect.title or "",
            phone_number=phone,
            phone_label=phone_label,
            attempt_number=(prospect.attempt_count or 0) + 1,
            last_contact_summary=last_contact,
            talking_points=talking_points,
            recent_notes=recent_notes,
            timezone=timezone,
        )

    def log_outcome(
        self,
        prospect_id: int,
        outcome: str,
        notes: str = "",
        follow_up_date: Optional[datetime] = None,
    ) -> int:
        """Log the outcome of a call.

        Args:
            prospect_id: Prospect who was called
            outcome: Call outcome (see ActivityOutcome enum)
            notes: Call notes
            follow_up_date: If set, next follow-up date

        Returns:
            Activity ID
        """
        # Build activity notes
        activity_notes = notes
        if follow_up_date:
            activity_notes += f" | Follow-up: {follow_up_date.strftime('%Y-%m-%d')}"

        # Convert string outcome to enum
        outcome_enum: Optional[ActivityOutcome] = None
        if outcome:
            try:
                outcome_enum = ActivityOutcome(outcome)
            except ValueError:
                logger.warning(f"Unknown outcome: {outcome}")

        activity = Activity(
            prospect_id=prospect_id,
            activity_type=ActivityType.CALL,
            outcome=outcome_enum,
            notes=activity_notes,
        )
        activity_id = self._db.create_activity(activity)

        logger.info(
            f"Call outcome logged: {outcome}",
            extra={"context": {
                "prospect_id": prospect_id,
                "outcome": outcome,
            }},
        )

        return activity_id

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _get_best_phone(self, prospect_id: int) -> tuple[str, str]:
        """Get the best phone number for a prospect.

        Prefers verified numbers, then by label priority (cell > work > other).

        Returns:
            Tuple of (phone_number, label)
        """
        methods = self._db.get_contact_methods(prospect_id)
        phones = [m for m in methods if m.type == ContactMethodType.PHONE]

        if not phones:
            return ("", "")

        # Sort: verified first, then by label preference
        label_priority = {"cell": 0, "mobile": 0, "work": 1, "office": 1}

        def sort_key(m):
            verified = 0 if m.is_verified else 1
            label = label_priority.get((m.label or "").lower(), 2)
            return (verified, label)

        phones.sort(key=sort_key)
        best = phones[0]
        return (best.value, best.label or "")

    def _get_last_contact_summary(self, activities: list[Activity]) -> str:
        """Summarize the last contact with this prospect."""
        if not activities:
            return "No prior contact"

        # Find most recent non-import activity
        contact_types = {
            ActivityType.CALL, ActivityType.VOICEMAIL,
            ActivityType.EMAIL_SENT, ActivityType.EMAIL_RECEIVED,
            ActivityType.DEMO, ActivityType.DEMO_COMPLETED,
        }
        contacts = [a for a in activities if a.activity_type in contact_types]

        if not contacts:
            return "No prior contact"

        # Sort by created_at descending
        contacts.sort(key=lambda a: a.created_at or datetime.min, reverse=True)
        last = contacts[0]

        type_labels = {
            ActivityType.CALL: "Called",
            ActivityType.VOICEMAIL: "Left voicemail",
            ActivityType.EMAIL_SENT: "Emailed",
            ActivityType.EMAIL_RECEIVED: "Received email",
            ActivityType.DEMO: "Demo",
            ActivityType.DEMO_COMPLETED: "Completed demo",
        }

        label = type_labels.get(last.activity_type, str(last.activity_type))
        date_str = ""
        if last.created_at:
            date_str = f" on {last.created_at.strftime('%b %d')}"

        return f"{label}{date_str}"

    def _build_talking_points(
        self,
        prospect,
        company,
        activities: list[Activity],
    ) -> list[str]:
        """Build quick talking points for the call."""
        points: list[str] = []

        # Mention their title
        if prospect.title:
            points.append(f"Speaking with {prospect.title}")

        # Check if we've had demos
        demos = [a for a in activities if a.activity_type in (
            ActivityType.DEMO, ActivityType.DEMO_COMPLETED, ActivityType.DEMO_SCHEDULED
        )]
        if demos:
            points.append("Has had demo — follow up on questions/next steps")

        # Check attempt count
        count = prospect.attempt_count or 0
        if count == 0:
            points.append("First outreach — introduce yourself and the platform")
        elif count <= 2:
            points.append(f"Attempt #{count + 1} — reference previous outreach")
        elif count >= 4:
            points.append(f"Attempt #{count + 1} — consider breakup approach")

        # Company context
        if company and company.state:
            points.append(f"Based in {company.state}")

        if not points:
            points.append("General introduction call")

        return points

    def _get_recent_notes(
        self, activities: list[Activity], limit: int = 3
    ) -> list[str]:
        """Get recent activity notes."""
        noted = [a for a in activities if a.notes]
        noted.sort(key=lambda a: a.created_at or datetime.min, reverse=True)
        return [a.notes for a in noted[:limit]]
