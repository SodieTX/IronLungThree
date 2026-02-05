"""Tests for reply monitor (src/autonomous/reply_monitor.py).

Covers:
    - ReplyMonitor.poll_inbox: match incoming emails to prospects, classify
    - ReplyMonitor.get_pending_reviews: retrieve unreviewed EMAIL_RECEIVED activities
    - ReplyMonitor.mark_reviewed: log STATUS_CHANGE to dismiss pending review
    - ReplyMonitor._basic_classify: keyword-based email classification
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, PropertyMock

import pytest

from src.autonomous.reply_monitor import MatchedReply, ReplyMonitor
from src.db.database import Database
from src.db.models import (
    Activity,
    ActivityOutcome,
    ActivityType,
    Company,
    ContactMethod,
    ContactMethodType,
    Prospect,
)
from src.integrations.outlook import EmailMessage, OutlookClient, ReplyClassification

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class MockOutlookClient:
    """Minimal mock for OutlookClient used by ReplyMonitor."""

    def __init__(self, inbox_messages: list[EmailMessage] | None = None):
        self._inbox = inbox_messages or []

    def get_inbox(self, since=None, limit=50) -> list[EmailMessage]:
        return self._inbox

    def classify_reply(self, message: EmailMessage) -> ReplyClassification:
        # Always raise so the monitor falls back to _basic_classify
        raise NotImplementedError("Mock does not classify")


def _setup_prospect_with_email(
    db: Database, email: str, first_name: str = "Test", last_name: str = "User"
) -> int:
    """Create a company, prospect, and email contact method. Return prospect_id."""
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
# poll_inbox
# ===========================================================================


class TestPollInbox:
    """Poll inbox, match senders to prospects, classify."""

    def test_matches_known_prospect(self, memory_db: Database):
        """Inbox email from known prospect is matched and classified."""
        pid = _setup_prospect_with_email(memory_db, "alice@example.com", "Alice", "Jones")

        messages = [
            EmailMessage(
                id="msg-1",
                from_address="alice@example.com",
                to_addresses=["jeff@mycompany.com"],
                subject="Re: Follow up",
                body="Sounds great, let's chat next week!",
                received_at=datetime.utcnow(),
            ),
        ]
        outlook = MockOutlookClient(inbox_messages=messages)
        monitor = ReplyMonitor(db=memory_db, outlook=outlook)

        replies = monitor.poll_inbox()

        assert len(replies) == 1
        assert replies[0].prospect_id == pid
        assert replies[0].message_id == "msg-1"
        # _basic_classify should flag "let's chat" as INTERESTED
        assert replies[0].classification == ReplyClassification.INTERESTED

    def test_unmatched_sender_ignored(self, memory_db: Database):
        """Emails from unknown senders produce no matches."""
        messages = [
            EmailMessage(
                id="msg-2",
                from_address="stranger@unknown.com",
                to_addresses=["jeff@mycompany.com"],
                subject="Hello",
                body="Random email",
            ),
        ]
        outlook = MockOutlookClient(inbox_messages=messages)
        monitor = ReplyMonitor(db=memory_db, outlook=outlook)

        replies = monitor.poll_inbox()
        assert len(replies) == 0

    def test_creates_email_received_activity(self, memory_db: Database):
        """Matched reply logs an EMAIL_RECEIVED activity."""
        pid = _setup_prospect_with_email(memory_db, "bob@example.com", "Bob", "Smith")

        messages = [
            EmailMessage(
                id="msg-3",
                from_address="bob@example.com",
                to_addresses=["jeff@mycompany.com"],
                subject="Out of office",
                body="I am currently out of office until Monday.",
                received_at=datetime.utcnow(),
            ),
        ]
        outlook = MockOutlookClient(inbox_messages=messages)
        monitor = ReplyMonitor(db=memory_db, outlook=outlook)
        monitor.poll_inbox()

        activities = memory_db.get_activities(pid)
        email_received = [a for a in activities if a.activity_type == ActivityType.EMAIL_RECEIVED]
        assert len(email_received) >= 1

    def test_empty_inbox_returns_empty_list(self, memory_db: Database):
        """Empty inbox -> no matches."""
        outlook = MockOutlookClient(inbox_messages=[])
        monitor = ReplyMonitor(db=memory_db, outlook=outlook)

        replies = monitor.poll_inbox()
        assert replies == []

    def test_message_without_from_address_skipped(self, memory_db: Database):
        """Messages with empty from_address are skipped."""
        messages = [
            EmailMessage(
                id="msg-4",
                from_address="",
                to_addresses=[],
                subject="No sender",
                body="No sender body",
            ),
        ]
        outlook = MockOutlookClient(inbox_messages=messages)
        monitor = ReplyMonitor(db=memory_db, outlook=outlook)

        replies = monitor.poll_inbox()
        assert len(replies) == 0

    def test_needs_review_for_interested(self, memory_db: Database):
        """INTERESTED replies are flagged for review."""
        _setup_prospect_with_email(memory_db, "carol@example.com", "Carol", "Keen")

        messages = [
            EmailMessage(
                id="msg-5",
                from_address="carol@example.com",
                to_addresses=["jeff@mycompany.com"],
                subject="Re: Intro",
                body="I'm interested in learning more about your product.",
                received_at=datetime.utcnow(),
            ),
        ]
        outlook = MockOutlookClient(inbox_messages=messages)
        monitor = ReplyMonitor(db=memory_db, outlook=outlook)

        replies = monitor.poll_inbox()
        assert len(replies) == 1
        assert replies[0].needs_review is True


# ===========================================================================
# get_pending_reviews
# ===========================================================================


class TestGetPendingReviews:
    """Retrieve EMAIL_RECEIVED activities awaiting review."""

    def test_returns_pending_interested_activity(self, memory_db: Database):
        """An EMAIL_RECEIVED with INTERESTED outcome appears as pending."""
        pid = _setup_prospect_with_email(memory_db, "dan@example.com", "Dan", "Eager")

        # Manually create an EMAIL_RECEIVED activity with INTERESTED outcome
        activity = Activity(
            prospect_id=pid,
            activity_type=ActivityType.EMAIL_RECEIVED,
            outcome=ActivityOutcome.INTERESTED,
            email_subject="Re: Demo?",
            notes="message_id:msg-100 classification:interested",
            created_by="system",
        )
        memory_db.create_activity(activity)

        outlook = MockOutlookClient()
        monitor = ReplyMonitor(db=memory_db, outlook=outlook)

        pending = monitor.get_pending_reviews()
        assert len(pending) >= 1
        assert any(r.prospect_id == pid for r in pending)

    def test_reviewed_activity_not_pending(self, memory_db: Database):
        """After STATUS_CHANGE is logged, the reply is no longer pending."""
        pid = _setup_prospect_with_email(memory_db, "eve@example.com", "Eve", "Done")

        # Create EMAIL_RECEIVED with an explicit past timestamp
        conn = memory_db._get_connection()
        conn.execute(
            """INSERT INTO activities
               (prospect_id, activity_type, outcome, email_subject, notes, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                pid,
                ActivityType.EMAIL_RECEIVED.value,
                ActivityOutcome.INTERESTED.value,
                "Re: Offer",
                "message_id:msg-200 classification:interested",
                "system",
                "2026-01-01 10:00:00",
            ),
        )
        # Create STATUS_CHANGE with a LATER timestamp so the > comparison works
        conn.execute(
            """INSERT INTO activities
               (prospect_id, activity_type, notes, created_by, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                pid,
                ActivityType.STATUS_CHANGE.value,
                "Reply reviewed: promoted (message_id:msg-200)",
                "user",
                "2026-01-01 10:01:00",
            ),
        )
        conn.commit()

        outlook = MockOutlookClient()
        monitor = ReplyMonitor(db=memory_db, outlook=outlook)

        pending = monitor.get_pending_reviews()
        # Eve's reply should NOT be pending because a STATUS_CHANGE followed
        assert all(r.prospect_id != pid for r in pending)

    def test_empty_db_returns_empty(self, memory_db: Database):
        """No EMAIL_RECEIVED activities -> empty pending list."""
        outlook = MockOutlookClient()
        monitor = ReplyMonitor(db=memory_db, outlook=outlook)

        pending = monitor.get_pending_reviews()
        assert pending == []


# ===========================================================================
# mark_reviewed
# ===========================================================================


class TestMarkReviewed:
    """Mark a reply as reviewed by logging STATUS_CHANGE."""

    def test_mark_reviewed_creates_status_change(self, memory_db: Database):
        """mark_reviewed logs a STATUS_CHANGE activity and returns True."""
        pid = _setup_prospect_with_email(memory_db, "frank@example.com", "Frank", "Rev")

        # Create the original EMAIL_RECEIVED
        memory_db.create_activity(
            Activity(
                prospect_id=pid,
                activity_type=ActivityType.EMAIL_RECEIVED,
                outcome=ActivityOutcome.INTERESTED,
                notes="message_id:msg-300 classification:interested",
                created_by="system",
            )
        )

        outlook = MockOutlookClient()
        monitor = ReplyMonitor(db=memory_db, outlook=outlook)

        result = monitor.mark_reviewed("msg-300", "promoted")
        assert result is True

        # Verify STATUS_CHANGE activity was created
        activities = memory_db.get_activities(pid)
        status_changes = [a for a in activities if a.activity_type == ActivityType.STATUS_CHANGE]
        assert len(status_changes) >= 1

    def test_mark_reviewed_shrinks_pending(self, memory_db: Database):
        """After marking reviewed, pending reviews list shrinks."""
        pid = _setup_prospect_with_email(memory_db, "grace@example.com", "Grace", "Rev2")

        # Insert EMAIL_RECEIVED with explicit PAST timestamp so that when
        # mark_reviewed creates STATUS_CHANGE with CURRENT_TIMESTAMP,
        # the > comparison in get_pending_reviews works correctly.
        conn = memory_db._get_connection()
        conn.execute(
            """INSERT INTO activities
               (prospect_id, activity_type, outcome, notes, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                pid,
                ActivityType.EMAIL_RECEIVED.value,
                ActivityOutcome.INTERESTED.value,
                "message_id:msg-400 classification:interested",
                "system",
                "2020-01-01 00:00:00",
            ),
        )
        conn.commit()

        outlook = MockOutlookClient()
        monitor = ReplyMonitor(db=memory_db, outlook=outlook)

        before = monitor.get_pending_reviews()
        count_before = len([r for r in before if r.prospect_id == pid])
        assert count_before >= 1

        monitor.mark_reviewed("msg-400", "dismissed")

        after = monitor.get_pending_reviews()
        count_after = len([r for r in after if r.prospect_id == pid])
        assert count_after < count_before

    def test_empty_message_id_returns_false(self, memory_db: Database):
        """Empty message_id -> returns False."""
        outlook = MockOutlookClient()
        monitor = ReplyMonitor(db=memory_db, outlook=outlook)

        result = monitor.mark_reviewed("", "promoted")
        assert result is False

    def test_unknown_message_id_returns_false(self, memory_db: Database):
        """Non-existent message_id -> returns False."""
        outlook = MockOutlookClient()
        monitor = ReplyMonitor(db=memory_db, outlook=outlook)

        result = monitor.mark_reviewed("nonexistent-msg-id", "promoted")
        assert result is False


# ===========================================================================
# _basic_classify
# ===========================================================================


class TestBasicClassify:
    """Keyword-based fallback classification."""

    def test_ooo_detection(self):
        """Out-of-office patterns return OOO."""
        assert (
            ReplyMonitor._basic_classify("Automatic Reply", "I am out of the office")
            == ReplyClassification.OOO
        )
        assert (
            ReplyMonitor._basic_classify("Auto-reply", "On vacation until Monday")
            == ReplyClassification.OOO
        )

    def test_not_interested_detection(self):
        """Decline patterns return NOT_INTERESTED."""
        assert (
            ReplyMonitor._basic_classify("Re: Intro", "Not interested, please remove me.")
            == ReplyClassification.NOT_INTERESTED
        )
        assert (
            ReplyMonitor._basic_classify("Re: Follow up", "No thanks, we're good.")
            == ReplyClassification.NOT_INTERESTED
        )

    def test_referral_detection(self):
        """Referral patterns return REFERRAL."""
        assert (
            ReplyMonitor._basic_classify("Re: Intro", "You should reach out to Jane instead")
            == ReplyClassification.REFERRAL
        )
        assert (
            ReplyMonitor._basic_classify("Re: Call", "Passing this along to the right person")
            == ReplyClassification.REFERRAL
        )

    def test_interested_detection(self):
        """Interest patterns return INTERESTED."""
        assert (
            ReplyMonitor._basic_classify("Re: Demo", "Sounds great, let's chat!")
            == ReplyClassification.INTERESTED
        )
        assert (
            ReplyMonitor._basic_classify("Re: Offer", "I'm interested, tell me more.")
            == ReplyClassification.INTERESTED
        )

    def test_unknown_default(self):
        """Generic text with no keywords returns UNKNOWN."""
        assert (
            ReplyMonitor._basic_classify("Re: Meeting", "Got it, thanks for the update.")
            == ReplyClassification.UNKNOWN
        )

    def test_ooo_takes_precedence_over_interested(self):
        """OOO is checked before interest patterns."""
        # Body contains both 'out of office' and 'interested'
        result = ReplyMonitor._basic_classify(
            "Automatic Reply",
            "I am out of the office. If interested, contact my colleague.",
        )
        assert result == ReplyClassification.OOO

    def test_handles_none_inputs(self):
        """None subject/body don't crash."""
        result = ReplyMonitor._basic_classify(None, None)
        assert result == ReplyClassification.UNKNOWN
