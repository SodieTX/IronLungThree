"""Tests for activity capture (src/autonomous/activity_capture.py).

Covers:
    - capture_email_activity: creates EMAIL_RECEIVED activity, returns ID
    - capture_calendar_activity: creates DEMO_SCHEDULED activity, returns ID
    - Duplicate prevention: same message/event captured twice -> only one record
"""

import pytest

from src.autonomous.activity_capture import (
    capture_calendar_activity,
    capture_email_activity,
)
from src.db.database import Database
from src.db.models import ActivityType


@pytest.fixture
def fk_relaxed_db(memory_db: Database) -> Database:
    """Memory DB with foreign-key checks disabled.

    The capture functions use prospect_id=0 (a sentinel), which violates
    the FK constraint on activities.prospect_id -> prospects.id.
    Disabling FK enforcement lets us test the capture logic in isolation.
    """
    conn = memory_db._get_connection()
    conn.execute("PRAGMA foreign_keys = OFF")
    return memory_db


# ===========================================================================
# capture_email_activity
# ===========================================================================


class TestCaptureEmailActivity:
    """Capture email as activity."""

    def test_creates_activity_and_returns_id(self, fk_relaxed_db: Database):
        """First capture creates activity and returns its ID."""
        activity_id = capture_email_activity(fk_relaxed_db, "email-msg-001")
        assert activity_id is not None
        assert isinstance(activity_id, int)
        assert activity_id > 0

    def test_activity_has_correct_type(self, fk_relaxed_db: Database):
        """Created activity is of type EMAIL_RECEIVED."""
        activity_id = capture_email_activity(fk_relaxed_db, "email-msg-002")
        assert activity_id is not None

        conn = fk_relaxed_db._get_connection()
        row = conn.execute(
            "SELECT activity_type FROM activities WHERE id = ?", (activity_id,)
        ).fetchone()
        assert row is not None
        assert row["activity_type"] == ActivityType.EMAIL_RECEIVED.value

    def test_notes_contain_message_id_marker(self, fk_relaxed_db: Database):
        """Activity notes contain the message_id marker."""
        activity_id = capture_email_activity(fk_relaxed_db, "email-msg-003")
        assert activity_id is not None

        conn = fk_relaxed_db._get_connection()
        row = conn.execute("SELECT notes FROM activities WHERE id = ?", (activity_id,)).fetchone()
        assert row is not None
        assert "message_id:email-msg-003" in row["notes"]

    def test_duplicate_returns_none(self, fk_relaxed_db: Database):
        """Second capture of same message_id returns None."""
        first = capture_email_activity(fk_relaxed_db, "email-msg-dup")
        assert first is not None

        second = capture_email_activity(fk_relaxed_db, "email-msg-dup")
        assert second is None

    def test_empty_message_id_returns_none(self, fk_relaxed_db: Database):
        """Empty message_id returns None without creating activity."""
        result = capture_email_activity(fk_relaxed_db, "")
        assert result is None

    def test_different_message_ids_create_separate_activities(self, fk_relaxed_db: Database):
        """Different message IDs each create their own activity."""
        id1 = capture_email_activity(fk_relaxed_db, "email-a")
        id2 = capture_email_activity(fk_relaxed_db, "email-b")

        assert id1 is not None
        assert id2 is not None
        assert id1 != id2


# ===========================================================================
# capture_calendar_activity
# ===========================================================================


class TestCaptureCalendarActivity:
    """Capture calendar event as activity."""

    def test_creates_activity_and_returns_id(self, fk_relaxed_db: Database):
        """First capture creates activity and returns its ID."""
        activity_id = capture_calendar_activity(fk_relaxed_db, "cal-event-001")
        assert activity_id is not None
        assert isinstance(activity_id, int)
        assert activity_id > 0

    def test_activity_has_correct_type(self, fk_relaxed_db: Database):
        """Created activity is of type DEMO_SCHEDULED."""
        activity_id = capture_calendar_activity(fk_relaxed_db, "cal-event-002")
        assert activity_id is not None

        conn = fk_relaxed_db._get_connection()
        row = conn.execute(
            "SELECT activity_type FROM activities WHERE id = ?", (activity_id,)
        ).fetchone()
        assert row is not None
        assert row["activity_type"] == ActivityType.DEMO_SCHEDULED.value

    def test_notes_contain_event_id_marker(self, fk_relaxed_db: Database):
        """Activity notes contain the event_id marker."""
        activity_id = capture_calendar_activity(fk_relaxed_db, "cal-event-003")
        assert activity_id is not None

        conn = fk_relaxed_db._get_connection()
        row = conn.execute("SELECT notes FROM activities WHERE id = ?", (activity_id,)).fetchone()
        assert row is not None
        assert "event_id:cal-event-003" in row["notes"]

    def test_duplicate_returns_none(self, fk_relaxed_db: Database):
        """Second capture of same event_id returns None."""
        first = capture_calendar_activity(fk_relaxed_db, "cal-event-dup")
        assert first is not None

        second = capture_calendar_activity(fk_relaxed_db, "cal-event-dup")
        assert second is None

    def test_empty_event_id_returns_none(self, fk_relaxed_db: Database):
        """Empty event_id returns None without creating activity."""
        result = capture_calendar_activity(fk_relaxed_db, "")
        assert result is None

    def test_different_event_ids_create_separate_activities(self, fk_relaxed_db: Database):
        """Different event IDs each create their own activity."""
        id1 = capture_calendar_activity(fk_relaxed_db, "cal-a")
        id2 = capture_calendar_activity(fk_relaxed_db, "cal-b")

        assert id1 is not None
        assert id2 is not None
        assert id1 != id2


# ===========================================================================
# Cross-type duplicate prevention
# ===========================================================================


class TestCrossTypeDuplication:
    """Email and calendar captures don't interfere with each other."""

    def test_email_and_calendar_same_id_are_independent(self, fk_relaxed_db: Database):
        """Same string used for email and calendar should create two separate activities."""
        email_id = capture_email_activity(fk_relaxed_db, "shared-id-001")
        cal_id = capture_calendar_activity(fk_relaxed_db, "shared-id-001")

        # Both should succeed because markers differ: message_id: vs event_id:
        assert email_id is not None
        assert cal_id is not None
        assert email_id != cal_id
