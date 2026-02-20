"""Email sync - Synchronize email history."""

from datetime import date, datetime, timedelta
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import Activity, ActivityOutcome, ActivityType, AttemptType
from src.integrations.outlook import OutlookClient

logger = get_logger(__name__)

# Sentinel values for storing sync metadata in data_freshness table
_SYNC_SENTINEL_PROSPECT_ID = 0
_SYNC_SENTINEL_FIELD = "email_sync"


class EmailSync:
    """Email history synchronization."""

    def __init__(self, db: Database, outlook: OutlookClient):
        self.db = db
        self.outlook = outlook

    def sync_sent(self, since: Optional[datetime] = None) -> int:
        """Sync sent emails from Outlook to the database.

        Retrieves sent emails from Outlook, matches each to a prospect by
        recipient email address, and creates EMAIL_SENT activity records for
        any that are not already captured.

        Args:
            since: Only sync emails sent after this timestamp.
                   Defaults to last sync time or 7 days ago.

        Returns:
            Count of newly synced sent email activities.
        """
        if since is None:
            since = self.get_last_sync()
            if since is None:
                since = datetime.utcnow() - timedelta(days=7)

        # Retrieve sent emails from Outlook
        try:
            # Use get_inbox with the sent items folder concept.
            # The OutlookClient only exposes get_inbox for inbox messages.
            # For sent items, we would need a separate API call. Since the
            # OutlookClient does not have a get_sent() method, we gracefully
            # handle this limitation.
            messages = self._get_sent_messages(since)
        except (NotImplementedError, Exception) as e:
            logger.warning(
                "Could not retrieve sent emails for sync",
                extra={"context": {"error": str(e)}},
            )
            return 0

        synced = 0
        conn = self.db._get_connection()

        for message in messages:
            # Match by recipient email to a prospect
            for to_addr in message.get("to_addresses", []):
                prospect_id = self.db.find_prospect_by_email(to_addr)
                if prospect_id is None:
                    continue

                # Check for duplicate by message_id in notes
                msg_id = message.get("id", "")
                marker = f"message_id:{msg_id}"
                existing = conn.execute(
                    "SELECT id FROM activities WHERE notes LIKE ? AND activity_type = ? LIMIT 1",
                    (f"%{marker}%", ActivityType.EMAIL_SENT.value),
                ).fetchone()

                if existing:
                    continue

                # Create EMAIL_SENT activity
                activity = Activity(
                    prospect_id=prospect_id,
                    activity_type=ActivityType.EMAIL_SENT,
                    email_subject=message.get("subject", ""),
                    email_body=(message.get("body", "") or "")[:500],
                    attempt_type=AttemptType.PERSONAL,
                    notes=marker,
                    created_by="system",
                )
                try:
                    self.db.create_activity(activity)
                    synced += 1
                except Exception as exc:
                    logger.warning(
                        "Failed to create sent email activity",
                        extra={"context": {"message_id": msg_id, "error": str(exc)}},
                    )

        self._update_last_sync()
        logger.info(
            "Sent email sync complete",
            extra={"context": {"synced": synced}},
        )
        return synced

    def sync_received(self, since: Optional[datetime] = None) -> int:
        """Sync received emails from Outlook to the database.

        Retrieves inbox emails from Outlook, matches each to a prospect by
        sender email address, and creates EMAIL_RECEIVED activity records for
        any that are not already captured.

        Args:
            since: Only sync emails received after this timestamp.
                   Defaults to last sync time or 7 days ago.

        Returns:
            Count of newly synced received email activities.
        """
        if since is None:
            since = self.get_last_sync()
            if since is None:
                since = datetime.utcnow() - timedelta(days=7)

        # Retrieve inbox messages from Outlook
        try:
            messages = self.outlook.get_inbox(since=since, limit=100)
        except (NotImplementedError, Exception) as e:
            logger.warning(
                "Could not retrieve inbox emails for sync",
                extra={"context": {"error": str(e)}},
            )
            return 0

        synced = 0
        conn = self.db._get_connection()

        for message in messages:
            if not message.from_address:
                continue

            # Match sender to a prospect
            prospect_id = self.db.find_prospect_by_email(message.from_address)
            if prospect_id is None:
                continue

            # Check for duplicate by message_id in notes
            marker = f"message_id:{message.id}"
            existing = conn.execute(
                "SELECT id FROM activities WHERE notes LIKE ? AND activity_type = ? LIMIT 1",
                (f"%{marker}%", ActivityType.EMAIL_RECEIVED.value),
            ).fetchone()

            if existing:
                continue

            # Classify the reply for outcome
            try:
                classification = self.outlook.classify_reply(message)
                from src.autonomous.reply_monitor import _CLASSIFICATION_TO_OUTCOME
                from src.integrations.outlook import ReplyClassification

                outcome = _CLASSIFICATION_TO_OUTCOME.get(classification, ActivityOutcome.REPLIED)
            except (NotImplementedError, ImportError, Exception):
                outcome = ActivityOutcome.REPLIED

            # Create EMAIL_RECEIVED activity
            activity = Activity(
                prospect_id=prospect_id,
                activity_type=ActivityType.EMAIL_RECEIVED,
                outcome=outcome,
                email_subject=message.subject,
                email_body=(message.body or "")[:500],
                notes=marker,
                created_by="system",
            )
            try:
                self.db.create_activity(activity)
                synced += 1
            except Exception as exc:
                logger.warning(
                    "Failed to create received email activity",
                    extra={"context": {"message_id": message.id, "error": str(exc)}},
                )

        self._update_last_sync()
        logger.info(
            "Received email sync complete",
            extra={"context": {"synced": synced}},
        )
        return synced

    def get_last_sync(self) -> Optional[datetime]:
        """Get last sync timestamp from data_freshness table.

        Uses a sentinel record with prospect_id=0 and field_name='email_sync'.

        Returns:
            Datetime of last successful sync, or None if never synced.
        """
        conn = self.db._get_connection()
        row = conn.execute(
            "SELECT verified_date FROM data_freshness WHERE prospect_id = ? AND field_name = ? "
            "ORDER BY verified_date DESC LIMIT 1",
            (_SYNC_SENTINEL_PROSPECT_ID, _SYNC_SENTINEL_FIELD),
        ).fetchone()

        if row is None:
            return None

        verified = row["verified_date"]
        if isinstance(verified, str):
            try:
                return datetime.fromisoformat(verified)
            except (ValueError, TypeError):
                return None
        elif isinstance(verified, (datetime, date)):
            if isinstance(verified, date) and not isinstance(verified, datetime):
                return datetime(verified.year, verified.month, verified.day)
            return verified
        return None

    def _update_last_sync(self) -> None:
        """Record the current time as the last sync timestamp."""
        today = date.today()
        try:
            self.db.create_data_freshness(
                prospect_id=_SYNC_SENTINEL_PROSPECT_ID,
                field_name=_SYNC_SENTINEL_FIELD,
                verified_date=today,
                verification_method="email_sync",
            )
        except Exception as exc:
            logger.warning(
                "Failed to update last sync timestamp",
                extra={"context": {"error": str(exc)}},
            )

    def _get_sent_messages(self, since: datetime) -> list[dict]:
        """Retrieve sent messages from Outlook.

        Uses OutlookClient.get_sent_emails() to fetch from the sentitems
        mailFolder via Microsoft Graph API.

        Args:
            since: Only include messages sent after this time.

        Returns:
            List of dicts with message data (id, to_addresses, subject, body).
        """
        email_messages = self.outlook.get_sent_emails(since=since, limit=100)
        return [
            {
                "id": msg.id,
                "to_addresses": msg.to_addresses,
                "subject": msg.subject,
                "body": msg.body,
            }
            for msg in email_messages
        ]
