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
from datetime import datetime, timedelta
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import (
    Activity,
    ActivityOutcome,
    ActivityType,
)
from src.integrations.outlook import OutlookClient, ReplyClassification

logger = get_logger(__name__)

# Map ReplyClassification to ActivityOutcome for logging
_CLASSIFICATION_TO_OUTCOME: dict[ReplyClassification, ActivityOutcome] = {
    ReplyClassification.INTERESTED: ActivityOutcome.INTERESTED,
    ReplyClassification.NOT_INTERESTED: ActivityOutcome.NOT_INTERESTED,
    ReplyClassification.OOO: ActivityOutcome.OOO,
    ReplyClassification.REFERRAL: ActivityOutcome.REFERRAL,
    ReplyClassification.UNKNOWN: ActivityOutcome.REPLIED,
}


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
        """Poll inbox, match to prospects, classify.

        Retrieves recent emails from Outlook, matches sender addresses to
        known prospects, and classifies each reply. Logs each matched reply
        as an EMAIL_RECEIVED activity.

        Returns:
            List of MatchedReply objects for all matched incoming emails.
        """
        matched_replies: list[MatchedReply] = []

        # Retrieve recent emails from Outlook
        try:
            since = datetime.utcnow() - timedelta(hours=1)
            messages = self.outlook.get_inbox(since=since, limit=50)
        except (NotImplementedError, Exception) as e:
            logger.warning(
                "Could not poll inbox",
                extra={"context": {"error": str(e)}},
            )
            return matched_replies

        for message in messages:
            if not message.from_address:
                continue

            # Match sender to a known prospect
            prospect_id = self.db.find_prospect_by_email(message.from_address)
            if prospect_id is None:
                continue

            # Get prospect details for the matched reply
            prospect = self.db.get_prospect(prospect_id)
            if prospect is None:
                continue

            # Classify the reply
            try:
                classification = self.outlook.classify_reply(message)
            except (NotImplementedError, Exception):
                # Fall back to basic keyword classification
                classification = self._basic_classify(message.subject, message.body)

            # Determine if this needs Jeff's review
            needs_review = classification in (
                ReplyClassification.INTERESTED,
                ReplyClassification.REFERRAL,
                ReplyClassification.UNKNOWN,
            )

            received_at = message.received_at or datetime.utcnow()

            reply = MatchedReply(
                message_id=message.id,
                prospect_id=prospect_id,
                prospect_name=prospect.full_name,
                subject=message.subject,
                classification=classification,
                received_at=received_at,
                needs_review=needs_review,
            )
            matched_replies.append(reply)

            # Log as EMAIL_RECEIVED activity
            outcome = _CLASSIFICATION_TO_OUTCOME.get(classification, ActivityOutcome.REPLIED)
            activity = Activity(
                prospect_id=prospect_id,
                activity_type=ActivityType.EMAIL_RECEIVED,
                outcome=outcome,
                email_subject=message.subject,
                email_body=message.body[:500] if message.body else None,
                notes=f"message_id:{message.id} classification:{classification.value}",
                created_by="system",
            )
            try:
                self.db.create_activity(activity)
            except Exception as exc:
                logger.warning(
                    "Failed to log email activity",
                    extra={"context": {"message_id": message.id, "error": str(exc)}},
                )

            logger.info(
                "Reply matched to prospect",
                extra={
                    "context": {
                        "prospect_id": prospect_id,
                        "prospect_name": prospect.full_name,
                        "classification": classification.value,
                        "needs_review": needs_review,
                    }
                },
            )

        logger.info(
            "Inbox poll complete",
            extra={"context": {"matched": len(matched_replies)}},
        )
        return matched_replies

    def get_pending_reviews(self) -> list[MatchedReply]:
        """Get replies awaiting Jeff's review.

        Queries the activities table for recent EMAIL_RECEIVED activities where
        the outcome indicates INTERESTED or REPLIED, that have not yet been
        followed by a STATUS_CHANGE activity (indicating Jeff reviewed them).

        Returns:
            List of MatchedReply objects pending review.
        """
        conn = self.db._get_connection()

        # Find EMAIL_RECEIVED activities with outcomes that need review,
        # where there is no subsequent STATUS_CHANGE for the same prospect
        rows = conn.execute(
            """
            SELECT a.id, a.prospect_id, a.outcome, a.email_subject, a.notes, a.created_at,
                   p.first_name, p.last_name
            FROM activities a
            JOIN prospects p ON a.prospect_id = p.id
            WHERE a.activity_type = ?
              AND a.outcome IN (?, ?, ?)
              AND NOT EXISTS (
                  SELECT 1 FROM activities a2
                  WHERE a2.prospect_id = a.prospect_id
                    AND a2.activity_type = ?
                    AND a2.created_at > a.created_at
              )
            ORDER BY a.created_at DESC
            LIMIT 100
            """,
            (
                ActivityType.EMAIL_RECEIVED.value,
                ActivityOutcome.INTERESTED.value,
                ActivityOutcome.REPLIED.value,
                ActivityOutcome.REFERRAL.value,
                ActivityType.STATUS_CHANGE.value,
            ),
        ).fetchall()

        pending: list[MatchedReply] = []
        for row in rows:
            # Extract message_id from notes if available
            notes = row["notes"] or ""
            message_id = ""
            for part in notes.split():
                if part.startswith("message_id:"):
                    message_id = part[len("message_id:") :]
                    break

            # Map outcome back to classification
            outcome_str = row["outcome"]
            if outcome_str == ActivityOutcome.INTERESTED.value:
                classification = ReplyClassification.INTERESTED
            elif outcome_str == ActivityOutcome.REFERRAL.value:
                classification = ReplyClassification.REFERRAL
            else:
                classification = ReplyClassification.UNKNOWN

            prospect_name = f"{row['first_name']} {row['last_name']}".strip()

            # Parse created_at
            created_at = row["created_at"]
            if isinstance(created_at, str):
                try:
                    received_at = datetime.fromisoformat(created_at)
                except (ValueError, TypeError):
                    received_at = datetime.utcnow()
            elif isinstance(created_at, datetime):
                received_at = created_at
            else:
                received_at = datetime.utcnow()

            pending.append(
                MatchedReply(
                    message_id=message_id,
                    prospect_id=row["prospect_id"],
                    prospect_name=prospect_name,
                    subject=row["email_subject"] or "",
                    classification=classification,
                    received_at=received_at,
                    needs_review=True,
                )
            )

        logger.info(
            "Pending reviews retrieved",
            extra={"context": {"count": len(pending)}},
        )
        return pending

    def mark_reviewed(self, message_id: str, action: str) -> bool:
        """Mark reply as reviewed by logging a review activity.

        Creates a STATUS_CHANGE activity to indicate that Jeff has reviewed
        the reply and taken action.

        Args:
            message_id: The email message ID that was reviewed
            action: The action taken (e.g. 'promoted', 'dismissed', 'deferred')

        Returns:
            True if review was logged successfully, False otherwise.
        """
        if not message_id:
            logger.warning("mark_reviewed called with empty message_id")
            return False

        conn = self.db._get_connection()

        # Find the original EMAIL_RECEIVED activity by message_id in notes
        marker = f"message_id:{message_id}"
        original = conn.execute(
            "SELECT prospect_id FROM activities WHERE notes LIKE ? AND activity_type = ? LIMIT 1",
            (f"%{marker}%", ActivityType.EMAIL_RECEIVED.value),
        ).fetchone()

        if original is None:
            logger.warning(
                "Could not find original activity for review",
                extra={"context": {"message_id": message_id}},
            )
            return False

        prospect_id = original["prospect_id"]

        # Log the review as a STATUS_CHANGE activity
        activity = Activity(
            prospect_id=prospect_id,
            activity_type=ActivityType.STATUS_CHANGE,
            notes=f"Reply reviewed: {action} (message_id:{message_id})",
            created_by="user",
        )
        try:
            self.db.create_activity(activity)
            logger.info(
                "Reply marked as reviewed",
                extra={
                    "context": {
                        "message_id": message_id,
                        "prospect_id": prospect_id,
                        "action": action,
                    }
                },
            )
            return True
        except Exception as exc:
            logger.error(
                "Failed to mark reply as reviewed",
                extra={"context": {"message_id": message_id, "error": str(exc)}},
            )
            return False

    @staticmethod
    def _basic_classify(subject: str, body: str) -> ReplyClassification:
        """Basic keyword classification fallback.

        Used when the Outlook client's classify_reply method is not available.

        Args:
            subject: Email subject line
            body: Email body text

        Returns:
            ReplyClassification based on keyword matching
        """
        text = f"{subject or ''} {body or ''}".lower()

        # OOO patterns
        ooo_patterns = [
            "out of office",
            "out of the office",
            "automatic reply",
            "auto-reply",
            "autoreply",
            "on vacation",
            "on leave",
        ]
        if any(p in text for p in ooo_patterns):
            return ReplyClassification.OOO

        # Not interested patterns
        not_interested_patterns = [
            "not interested",
            "no thank you",
            "no thanks",
            "please remove",
            "unsubscribe",
            "stop contacting",
            "do not contact",
        ]
        if any(p in text for p in not_interested_patterns):
            return ReplyClassification.NOT_INTERESTED

        # Referral patterns
        referral_patterns = [
            "reach out to",
            "contact instead",
            "the right person",
            "forward this to",
            "passing this along",
        ]
        if any(p in text for p in referral_patterns):
            return ReplyClassification.REFERRAL

        # Interested patterns
        interested_patterns = [
            "interested",
            "sounds good",
            "sounds great",
            "let's chat",
            "let's talk",
            "schedule a",
            "tell me more",
            "more information",
            "happy to chat",
            "would love to",
        ]
        if any(p in text for p in interested_patterns):
            return ReplyClassification.INTERESTED

        return ReplyClassification.UNKNOWN
