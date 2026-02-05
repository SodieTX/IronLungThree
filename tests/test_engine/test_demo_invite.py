"""Tests for demo invite service.

Tests Step 3.5: Demo Invite Service
    - Creating a demo invite with mocked Outlook
    - Creating a demo invite without Outlook (offline mode)
    - Activity logging
    - Error handling for missing prospects
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.db.database import Database
from src.db.models import (
    Activity,
    ActivityType,
    Company,
    ContactMethod,
    ContactMethodType,
    EngagementStage,
    Population,
    Prospect,
)
from src.engine.demo_invite import (
    DemoInvite,
    _log_demo_activity,
    create_demo_invite,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def db():
    """Fresh in-memory database."""
    database = Database(":memory:")
    database.initialize()
    yield database
    database.close()


@pytest.fixture
def company_id(db):
    """Create a test company, return its ID."""
    company = Company(name="Demo Corp", state="TX", size="medium")
    return db.create_company(company)


@pytest.fixture
def prospect_id(db, company_id):
    """Create a test prospect with email, return its ID."""
    prospect = Prospect(
        company_id=company_id,
        first_name="Alice",
        last_name="Johnson",
        title="VP of Operations",
        population=Population.ENGAGED,
        engagement_stage=EngagementStage.PRE_DEMO,
        prospect_score=85,
    )
    pid = db.create_prospect(prospect)
    # Add email contact method
    db.create_contact_method(
        ContactMethod(
            prospect_id=pid,
            type=ContactMethodType.EMAIL,
            value="alice@democorp.com",
            label="work",
            is_primary=True,
        )
    )
    return pid


@pytest.fixture
def mock_outlook():
    """Mocked Outlook client."""
    outlook = MagicMock()
    outlook.create_event.return_value = "event-123"
    outlook.send_email.return_value = "sent-msg-456"
    return outlook


@pytest.fixture
def demo_time():
    """Standard demo datetime."""
    return datetime(2026, 2, 15, 14, 0)


# =============================================================================
# DEMO INVITE WITH OUTLOOK
# =============================================================================


class TestDemoInviteWithOutlook:
    """Test demo invite creation with mocked Outlook."""

    def test_creates_invite_with_outlook(self, db, prospect_id, mock_outlook, demo_time):
        """Creates a demo invite with all Outlook operations."""
        invite = create_demo_invite(
            db=db,
            prospect_id=prospect_id,
            demo_datetime=demo_time,
            duration_minutes=30,
            outlook=mock_outlook,
        )

        assert isinstance(invite, DemoInvite)
        assert invite.prospect_id == prospect_id
        assert invite.prospect_name == "Alice Johnson"
        assert invite.company_name == "Demo Corp"
        assert invite.demo_datetime == demo_time
        assert invite.duration_minutes == 30

    def test_creates_calendar_event(self, db, prospect_id, mock_outlook, demo_time):
        """Calendar event is created via Outlook."""
        invite = create_demo_invite(
            db=db,
            prospect_id=prospect_id,
            demo_datetime=demo_time,
            outlook=mock_outlook,
        )

        mock_outlook.create_event.assert_called_once()
        call_kwargs = mock_outlook.create_event.call_args
        assert call_kwargs[1]["teams_meeting"] is True
        assert invite.calendar_event_id == "event-123"
        assert invite.teams_link is not None

    def test_sends_invite_email(self, db, prospect_id, mock_outlook, demo_time):
        """Demo invite email is sent via Outlook."""
        invite = create_demo_invite(
            db=db,
            prospect_id=prospect_id,
            demo_datetime=demo_time,
            outlook=mock_outlook,
        )

        mock_outlook.send_email.assert_called_once()
        call_kwargs = mock_outlook.send_email.call_args
        assert call_kwargs[1]["to"] == "alice@democorp.com"
        assert call_kwargs[1]["html"] is True
        assert invite.email_sent is True

    def test_logs_activity(self, db, prospect_id, mock_outlook, demo_time):
        """DEMO_SCHEDULED activity is logged."""
        invite = create_demo_invite(
            db=db,
            prospect_id=prospect_id,
            demo_datetime=demo_time,
            outlook=mock_outlook,
        )

        assert invite.activity_id is not None

        activities = db.get_activities(prospect_id)
        demo_activities = [a for a in activities if a.activity_type == ActivityType.DEMO_SCHEDULED]
        assert len(demo_activities) == 1
        assert "2026-02-15" in demo_activities[0].notes
        assert "Invite email sent" in demo_activities[0].notes

    def test_custom_duration(self, db, prospect_id, mock_outlook, demo_time):
        """Custom duration is passed through."""
        invite = create_demo_invite(
            db=db,
            prospect_id=prospect_id,
            demo_datetime=demo_time,
            duration_minutes=60,
            outlook=mock_outlook,
        )

        assert invite.duration_minutes == 60
        call_kwargs = mock_outlook.create_event.call_args
        assert call_kwargs[1]["duration_minutes"] == 60


# =============================================================================
# DEMO INVITE WITHOUT OUTLOOK (OFFLINE MODE)
# =============================================================================


class TestDemoInviteOffline:
    """Test demo invite creation without Outlook (offline mode)."""

    def test_creates_invite_offline(self, db, prospect_id, demo_time):
        """Creates invite without Outlook."""
        invite = create_demo_invite(
            db=db,
            prospect_id=prospect_id,
            demo_datetime=demo_time,
            duration_minutes=30,
            outlook=None,
        )

        assert isinstance(invite, DemoInvite)
        assert invite.prospect_id == prospect_id
        assert invite.prospect_name == "Alice Johnson"
        assert invite.company_name == "Demo Corp"
        assert invite.demo_datetime == demo_time

    def test_no_calendar_event_offline(self, db, prospect_id, demo_time):
        """No calendar event created in offline mode."""
        invite = create_demo_invite(
            db=db,
            prospect_id=prospect_id,
            demo_datetime=demo_time,
            outlook=None,
        )

        assert invite.calendar_event_id is None
        assert invite.teams_link is None

    def test_no_email_sent_offline(self, db, prospect_id, demo_time):
        """No email sent in offline mode."""
        invite = create_demo_invite(
            db=db,
            prospect_id=prospect_id,
            demo_datetime=demo_time,
            outlook=None,
        )

        assert invite.email_sent is False

    def test_activity_logged_offline(self, db, prospect_id, demo_time):
        """Activity is still logged in offline mode."""
        invite = create_demo_invite(
            db=db,
            prospect_id=prospect_id,
            demo_datetime=demo_time,
            outlook=None,
        )

        assert invite.activity_id is not None

        activities = db.get_activities(prospect_id)
        demo_activities = [a for a in activities if a.activity_type == ActivityType.DEMO_SCHEDULED]
        assert len(demo_activities) == 1
        assert "offline mode" in demo_activities[0].notes.lower()


# =============================================================================
# ACTIVITY LOGGING
# =============================================================================


class TestActivityLogging:
    """Test activity logging for demo invites."""

    def test_activity_type_is_demo_scheduled(self, db, prospect_id, demo_time):
        """Activity type is DEMO_SCHEDULED."""
        create_demo_invite(
            db=db,
            prospect_id=prospect_id,
            demo_datetime=demo_time,
        )

        activities = db.get_activities(prospect_id)
        assert any(a.activity_type == ActivityType.DEMO_SCHEDULED for a in activities)

    def test_activity_notes_contain_datetime(self, db, prospect_id, demo_time):
        """Activity notes contain the demo datetime."""
        create_demo_invite(
            db=db,
            prospect_id=prospect_id,
            demo_datetime=demo_time,
        )

        activities = db.get_activities(prospect_id)
        demo_activity = [a for a in activities if a.activity_type == ActivityType.DEMO_SCHEDULED][0]
        assert "2026-02-15 14:00" in demo_activity.notes

    def test_activity_notes_contain_duration(self, db, prospect_id, demo_time):
        """Activity notes contain the duration."""
        create_demo_invite(
            db=db,
            prospect_id=prospect_id,
            demo_datetime=demo_time,
            duration_minutes=45,
        )

        activities = db.get_activities(prospect_id)
        demo_activity = [a for a in activities if a.activity_type == ActivityType.DEMO_SCHEDULED][0]
        assert "45 minutes" in demo_activity.notes

    def test_activity_has_follow_up_set(self, db, prospect_id, demo_time):
        """Activity has follow_up_set to the demo datetime."""
        create_demo_invite(
            db=db,
            prospect_id=prospect_id,
            demo_datetime=demo_time,
        )

        activities = db.get_activities(prospect_id)
        demo_activity = [a for a in activities if a.activity_type == ActivityType.DEMO_SCHEDULED][0]
        assert demo_activity.follow_up_set is not None


# =============================================================================
# ERROR HANDLING
# =============================================================================


class TestDemoInviteErrors:
    """Test error handling for demo invite creation."""

    def test_missing_prospect_raises_error(self, db, demo_time):
        """Missing prospect raises ValueError."""
        with pytest.raises(ValueError, match="Prospect not found"):
            create_demo_invite(
                db=db,
                prospect_id=9999,
                demo_datetime=demo_time,
            )

    def test_missing_company_raises_error(self, db, demo_time):
        """Prospect with invalid company raises ValueError."""
        # Create prospect with non-existent company_id
        # First create a company to get a valid company_id for the prospect
        company_id = db.create_company(Company(name="Temp Co"))
        prospect = Prospect(
            company_id=company_id,
            first_name="Orphan",
            last_name="Prospect",
        )
        pid = db.create_prospect(prospect)

        # Now delete the company directly to create an orphan
        conn = db._get_connection()
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("DELETE FROM companies WHERE id = ?", (company_id,))
        conn.commit()
        conn.execute("PRAGMA foreign_keys = ON")

        with pytest.raises(ValueError, match="Company not found"):
            create_demo_invite(
                db=db,
                prospect_id=pid,
                demo_datetime=demo_time,
            )

    def test_outlook_failure_still_logs_activity(self, db, prospect_id, demo_time):
        """If Outlook fails, activity is still logged."""
        failing_outlook = MagicMock()
        failing_outlook.create_event.side_effect = Exception("API Error")

        invite = create_demo_invite(
            db=db,
            prospect_id=prospect_id,
            demo_datetime=demo_time,
            outlook=failing_outlook,
        )

        # Calendar failed but activity was still logged
        assert invite.calendar_event_id is None
        assert invite.activity_id is not None
