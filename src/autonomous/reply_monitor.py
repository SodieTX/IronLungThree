"""Reply monitor - Poll inbox and classify replies.

Polls every 30 minutes. Classifies replies as:
    - interested
    - not_interested
    - ooo (out of office)
    - referral
    - unknown

NO auto-promotion: interested replies are flagged for Jeff's review.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from src.db.database import Database
from src.integrations.outlook import OutlookClient, ReplyClassification
from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MatchedReply:
    """A reply matched to a prospect."""

    message_id: str
    prospect_id: int
    prospect_name: str
    subject: str
    classification: ReplyClassification
    received_at: datetime
    needs_review: bool


class ReplyMonitor:
    """Email reply monitoring."""

    def __init__(self, db: Database, outlook: OutlookClient):
        self.db = db
        self.outlook = outlook

    def poll_inbox(self) -> list[MatchedReply]:
        """Poll inbox, match to prospects, classify."""
        raise NotImplementedError("Phase 5, Step 5.4")

    def get_pending_reviews(self) -> list[MatchedReply]:
        """Get replies awaiting Jeff's review."""
        raise NotImplementedError("Phase 5, Step 5.4")

    def mark_reviewed(self, message_id: str, action: str) -> bool:
        """Mark reply as reviewed."""
        raise NotImplementedError("Phase 5, Step 5.4")
