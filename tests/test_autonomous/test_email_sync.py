"""Tests for email sync (src/autonomous/email_sync.py).

Covers:
    - EmailSync.get_last_sync: sentinel lookup in data_freshness table
    - EmailSync._update_last_sync: records timestamp
    - EmailSync.sync_received: match inbox messages to prospects, create activities
    - EmailSync.sync_sent: handles NotImplementedError gracefully
"""

from datetime import datetime, timedelta

import pytest

from src.autonomous.email_sync import EmailSync
from src.db.database import Database
from src.db.models import (
    ActivityType,
    Company,
    ContactMethod,
    ContactMethodType,
    Prospect,
)
from src.integrations.outlook import EmailMessage


@pytest.fixture
def fk_relaxed_db(memory_db: Database) -> Database:
    """Memory DB with foreign-key checks disabled.

    EmailSync._update_last_sync uses prospect_id=0 as a sentinel in
    data_freshness, which violates FK constraints. Disabling FK
    enforcement isolates the sync logic.
    """
    conn = memory_db._get_connection()
    conn.execute("PRAGMA foreign_keys = OFF")
    return memory_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class MockOutlookClient:
    """Minimal mock for OutlookClient used by EmailSync."""

    def __init__(
        self,
        inbox_messages: list[EmailMessage] | None = None,
    ):
        self._inbox = inbox_messages or []

    def get_inbox(self, since=None, limit=100) -> list[EmailMessage]:
        return self._inbox

    def classify_reply(self, message: EmailMessage):
        raise NotImplementedError("Mock does not classify")


def _setup_prospect_with_email(
    db: Database, email: str, first_name: str = "Test", last_name: str = "User"
) -> int:
    """Create company + prospect + email contact method. Return prospect_id."""
    company_id = db.create_company(Company(name=f"{first_name} Co"))
    pid = db.create_prospect(
        Prospect(company_id=company_id, first_name=first_name, last_name=last_name)
    )
    db.create_contact_method(
        ContactMethod(
            prospect_id=pid,
            type=ContactMethodType.EMAIL,
            value=email,
            is_primary=True,
        )
    )
    return pid


# ===========================================================================
# get_last_sync
# ===========================================================================


class TestGetLastSync:
    """Sentinel-based last-sync lookup."""

    def test_returns_none_when_no_sync_recorded(self, memory_db: Database):
        """First call returns None (nothing in data_freshness)."""
        outlook = MockOutlookClient()
        sync = EmailSync(db=memory_db, outlook=outlook)

        result = sync.get_last_sync()
        assert result is None


# ===========================================================================
# _update_last_sync
# ===========================================================================


class TestUpdateLastSync:
    """Record sync timestamp in data_freshness."""

    def test_records_timestamp(self, fk_relaxed_db: Database):
        """After _update_last_sync, get_last_sync returns a value."""
        outlook = MockOutlookClient()
        sync = EmailSync(db=fk_relaxed_db, outlook=outlook)

        assert sync.get_last_sync() is None

        sync._update_last_sync()

        result = sync.get_last_sync()
        assert result is not None

    def test_updates_idempotently(self, fk_relaxed_db: Database):
        """Calling _update_last_sync multiple times doesn't raise."""
        outlook = MockOutlookClient()
        sync = EmailSync(db=fk_relaxed_db, outlook=outlook)

        sync._update_last_sync()
        sync._update_last_sync()

        result = sync.get_last_sync()
        assert result is not None


# ===========================================================================
# sync_received
# ===========================================================================


class TestSyncReceived:
    """Sync received emails from (mocked) Outlook into activities."""

    def test_creates_activity_for_matched_email(self, memory_db: Database):
        """Inbox message from known prospect creates EMAIL_RECEIVED activity."""
        pid = _setup_prospect_with_email(memory_db, "syncsender@example.com", "Sync", "Sender")

        messages = [
            EmailMessage(
                id="sync-msg-1",
                from_address="syncsender@example.com",
                to_addresses=["jeff@mycompany.com"],
                subject="Re: Proposal",
                body="Thanks for the proposal.",
                received_at=datetime.utcnow(),
            ),
        ]
        outlook = MockOutlookClient(inbox_messages=messages)
        sync = EmailSync(db=memory_db, outlook=outlook)

        synced = sync.sync_received(since=datetime.utcnow() - timedelta(hours=1))
        assert synced == 1

        activities = memory_db.get_activities(pid)
        email_received = [a for a in activities if a.activity_type == ActivityType.EMAIL_RECEIVED]
        assert len(email_received) >= 1

    def test_skips_unknown_senders(self, memory_db: Database):
        """Messages from unknown senders are not synced."""
        messages = [
            EmailMessage(
                id="sync-msg-2",
                from_address="nobody@unknown.com",
                to_addresses=["jeff@mycompany.com"],
                subject="Spam",
                body="Buy now!",
            ),
        ]
        outlook = MockOutlookClient(inbox_messages=messages)
        sync = EmailSync(db=memory_db, outlook=outlook)

        synced = sync.sync_received(since=datetime.utcnow() - timedelta(hours=1))
        assert synced == 0

    def test_deduplicates_by_message_id(self, memory_db: Database):
        """Same message synced twice creates only one activity."""
        pid = _setup_prospect_with_email(memory_db, "dedup@example.com", "Dedup", "Test")

        messages = [
            EmailMessage(
                id="sync-msg-3",
                from_address="dedup@example.com",
                to_addresses=["jeff@mycompany.com"],
                subject="Re: Info",
                body="Got it!",
                received_at=datetime.utcnow(),
            ),
        ]
        outlook = MockOutlookClient(inbox_messages=messages)
        sync = EmailSync(db=memory_db, outlook=outlook)

        first_sync = sync.sync_received(since=datetime.utcnow() - timedelta(hours=1))
        assert first_sync == 1

        second_sync = sync.sync_received(since=datetime.utcnow() - timedelta(hours=1))
        assert second_sync == 0

    def test_empty_inbox_returns_zero(self, memory_db: Database):
        """Empty inbox -> 0 synced."""
        outlook = MockOutlookClient(inbox_messages=[])
        sync = EmailSync(db=memory_db, outlook=outlook)

        synced = sync.sync_received(since=datetime.utcnow() - timedelta(hours=1))
        assert synced == 0

    def test_skips_messages_without_from_address(self, memory_db: Database):
        """Messages with empty from_address are skipped."""
        messages = [
            EmailMessage(
                id="sync-msg-4",
                from_address="",
                to_addresses=[],
                subject="Empty sender",
                body="No from",
            ),
        ]
        outlook = MockOutlookClient(inbox_messages=messages)
        sync = EmailSync(db=memory_db, outlook=outlook)

        synced = sync.sync_received(since=datetime.utcnow() - timedelta(hours=1))
        assert synced == 0

    def test_updates_last_sync_timestamp(self, fk_relaxed_db: Database):
        """After sync_received, get_last_sync returns a value."""
        outlook = MockOutlookClient(inbox_messages=[])
        sync = EmailSync(db=fk_relaxed_db, outlook=outlook)

        assert sync.get_last_sync() is None
        sync.sync_received(since=datetime.utcnow() - timedelta(hours=1))
        assert sync.get_last_sync() is not None


# ===========================================================================
# sync_sent
# ===========================================================================


class TestSyncSent:
    """Sync sent emails - currently raises NotImplementedError internally."""

    def test_handles_not_implemented_gracefully(self, memory_db: Database):
        """sync_sent returns 0 when _get_sent_messages raises NotImplementedError."""
        outlook = MockOutlookClient()
        sync = EmailSync(db=memory_db, outlook=outlook)

        result = sync.sync_sent()
        assert result == 0

    def test_returns_zero_on_error(self, memory_db: Database):
        """sync_sent returns 0 even with explicit since parameter."""
        outlook = MockOutlookClient()
        sync = EmailSync(db=memory_db, outlook=outlook)

        result = sync.sync_sent(since=datetime.utcnow() - timedelta(days=7))
        assert result == 0
