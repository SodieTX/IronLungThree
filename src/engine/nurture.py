"""Nurture email sequences for unengaged prospects.

Draft-and-queue model: emails are generated and queued for Jeff's
batch approval, NOT auto-sent.

Sequences:
    - Warm Touch: 3 emails, 7 days apart
    - Re-engagement: 2 emails, 14 days apart
    - Breakup: 1 final email

Usage:
    from src.engine.nurture import NurtureEngine

    engine = NurtureEngine(db)
    batch = engine.generate_nurture_batch(limit=30)
    # Jeff reviews and approves...
    sent = engine.send_approved_emails()
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum

from src.db.database import Database
from src.db.models import Prospect, AttemptType
from src.core.logging import get_logger

logger = get_logger(__name__)


class NurtureSequence(str, Enum):
    """Type of nurture sequence."""

    WARM_TOUCH = "warm_touch"
    RE_ENGAGEMENT = "re_engagement"
    BREAKUP = "breakup"


@dataclass
class NurtureEmail:
    """A queued nurture email.

    Attributes:
        id: Queue ID
        prospect_id: Target prospect
        prospect_name: Prospect name
        company_name: Company name
        sequence: Sequence type
        sequence_step: Step in sequence (1, 2, 3)
        subject: Email subject
        body: Email body
        to_address: Recipient email
        status: pending, approved, sent, rejected
        queued_at: When queued
        approved_at: When approved
        sent_at: When sent
    """

    id: Optional[int] = None
    prospect_id: int = 0
    prospect_name: str = ""
    company_name: str = ""
    sequence: NurtureSequence = NurtureSequence.WARM_TOUCH
    sequence_step: int = 1
    subject: str = ""
    body: str = ""
    to_address: str = ""
    status: str = "pending"
    queued_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None


class NurtureEngine:
    """Nurture email generation and sending.

    Draft-and-queue model for compliance and quality control.
    """

    def __init__(self, db: Database, daily_send_cap: int = 50):
        """Initialize nurture engine.

        Args:
            db: Database instance
            daily_send_cap: Maximum emails to send per day
        """
        self.db = db
        self.daily_send_cap = daily_send_cap

    def generate_nurture_batch(self, limit: int = 30) -> list[NurtureEmail]:
        """Generate nurture emails for batch approval.

        Identifies prospects due for nurture and generates emails.
        Does NOT send - queues for approval.

        Args:
            limit: Maximum emails to generate

        Returns:
            List of generated NurtureEmail objects
        """
        raise NotImplementedError("Phase 5, Step 5.3")

    def get_pending_approval(self) -> list[NurtureEmail]:
        """Get emails pending Jeff's approval.

        Returns:
            Emails awaiting approval
        """
        raise NotImplementedError("Phase 5, Step 5.3")

    def approve_email(self, email_id: int) -> bool:
        """Approve an email for sending.

        Args:
            email_id: Queue ID

        Returns:
            True if approved
        """
        raise NotImplementedError("Phase 5, Step 5.3")

    def reject_email(self, email_id: int, reason: Optional[str] = None) -> bool:
        """Reject an email (won't be sent).

        Args:
            email_id: Queue ID
            reason: Why rejected

        Returns:
            True if rejected
        """
        raise NotImplementedError("Phase 5, Step 5.3")

    def send_approved_emails(self) -> int:
        """Send all approved emails.

        Respects daily send cap.
        Logs as automated attempt on each prospect.

        Returns:
            Number of emails sent
        """
        raise NotImplementedError("Phase 5, Step 5.3")

    def _get_prospects_for_nurture(self, limit: int) -> list[Prospect]:
        """Find prospects due for nurture emails."""
        raise NotImplementedError("Phase 5, Step 5.3")

    def _determine_sequence(self, prospect: Prospect) -> tuple[NurtureSequence, int]:
        """Determine which sequence and step for prospect."""
        raise NotImplementedError("Phase 5, Step 5.3")

    def _generate_email(
        self,
        prospect: Prospect,
        sequence: NurtureSequence,
        step: int,
    ) -> NurtureEmail:
        """Generate email content for prospect."""
        raise NotImplementedError("Phase 5, Step 5.3")
