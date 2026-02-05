"""Tests for one-off email service."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.db.models import (
    Activity,
    ActivityType,
    Company,
    ContactMethod,
    ContactMethodType,
    Prospect,
)
from src.engine.email_service import EmailHistoryEntry, EmailResult, EmailService


@pytest.fixture
def setup_db(memory_db):
    """Populated database with prospect and contact method."""
    company = Company(
        name="Acme Lending",
        name_normalized="acme lending",
        state="TX",
        timezone="central",
    )
    company_id = memory_db.create_company(company)

    prospect = Prospect(
        company_id=company_id,
        first_name="John",
        last_name="Doe",
        title="VP Ops",
    )
    prospect_id = memory_db.create_prospect(prospect)

    contact = ContactMethod(
        prospect_id=prospect_id,
        type=ContactMethodType.EMAIL,
        value="john@acme.com",
        label="work",
    )
    memory_db.create_contact_method(contact)

    return memory_db, prospect_id, company_id


@pytest.fixture
def mock_outlook():
    """Mocked OutlookClient."""
    outlook = MagicMock()
    outlook.send_email.return_value = "sent-123"
    outlook.create_draft.return_value = "draft-456"
    return outlook


class TestSendFromTemplate:
    """Test template-based email sending."""

    def test_send_success(self, setup_db, mock_outlook):
        """Template email sends via Outlook and logs activity."""
        db, prospect_id, _ = setup_db
        service = EmailService(db, mock_outlook)
        sender = {"name": "Jeff", "title": "AE", "company": "Nexys", "phone": "555-1234"}

        result = service.send_from_template(
            prospect_id=prospect_id,
            template_name="intro",
            sender=sender,
        )

        assert result.success is True
        assert result.message_id == "sent-123"
        assert result.recipient == "john@acme.com"
        assert result.activity_id is not None
        assert result.draft_mode is False

    def test_send_as_draft(self, setup_db, mock_outlook):
        """Template email saved as draft when draft_only=True."""
        db, prospect_id, _ = setup_db
        service = EmailService(db, mock_outlook)
        sender = {"name": "Jeff", "title": "AE", "company": "Nexys", "phone": "555-1234"}

        result = service.send_from_template(
            prospect_id=prospect_id,
            template_name="follow_up",
            sender=sender,
            draft_only=True,
        )

        assert result.success is True
        assert result.draft_mode is True
        mock_outlook.create_draft.assert_called_once()
        mock_outlook.send_email.assert_not_called()

    def test_send_offline_mode(self, setup_db):
        """Template email works without Outlook (offline mode)."""
        db, prospect_id, _ = setup_db
        service = EmailService(db, outlook=None)
        sender = {"name": "Jeff", "title": "AE", "company": "Nexys", "phone": "555-1234"}

        result = service.send_from_template(
            prospect_id=prospect_id,
            template_name="intro",
            sender=sender,
        )

        assert result.success is True
        assert result.message_id == ""
        assert result.activity_id is not None

    def test_send_missing_prospect(self, setup_db, mock_outlook):
        """Returns failure for nonexistent prospect."""
        db, _, _ = setup_db
        service = EmailService(db, mock_outlook)
        sender = {"name": "Jeff", "title": "AE", "company": "Nexys", "phone": "555-1234"}

        result = service.send_from_template(
            prospect_id=9999,
            template_name="intro",
            sender=sender,
        )

        assert result.success is False

    def test_activity_logged_with_template_name(self, setup_db, mock_outlook):
        """Activity notes include the template name."""
        db, prospect_id, _ = setup_db
        service = EmailService(db, mock_outlook)
        sender = {"name": "Jeff", "title": "AE", "company": "Nexys", "phone": "555-1234"}

        result = service.send_from_template(
            prospect_id=prospect_id,
            template_name="nurture_1",
            sender=sender,
        )

        activities = db.get_activities(prospect_id)
        email_acts = [a for a in activities if a.activity_type == ActivityType.EMAIL_SENT]
        assert len(email_acts) >= 1
        assert "nurture_1" in email_acts[-1].notes


class TestSendCustom:
    """Test custom email sending."""

    def test_send_custom_email(self, setup_db, mock_outlook):
        """Custom email sends successfully."""
        db, prospect_id, _ = setup_db
        service = EmailService(db, mock_outlook)

        result = service.send_custom(
            prospect_id=prospect_id,
            subject="Quick question",
            body="Hi John, wanted to ask about your timeline.",
        )

        assert result.success is True
        assert result.subject == "Quick question"

    def test_send_custom_html(self, setup_db, mock_outlook):
        """Custom HTML email sets html flag."""
        db, prospect_id, _ = setup_db
        service = EmailService(db, mock_outlook)

        result = service.send_custom(
            prospect_id=prospect_id,
            subject="Update",
            body="<p>Hi John</p>",
            html=True,
        )

        assert result.success is True
        mock_outlook.send_email.assert_called_once()
        call_kwargs = mock_outlook.send_email.call_args.kwargs
        assert call_kwargs["html"] is True


class TestGetEmailHistory:
    """Test email history retrieval."""

    def test_get_history(self, setup_db):
        """Get email history returns sent/received entries."""
        db, prospect_id, _ = setup_db

        # Add some email activities
        db.create_activity(Activity(
            prospect_id=prospect_id,
            activity_type=ActivityType.EMAIL_SENT,
            notes="Subject: Intro | Body preview here",
        ))
        db.create_activity(Activity(
            prospect_id=prospect_id,
            activity_type=ActivityType.EMAIL_RECEIVED,
            notes="Subject: Re: Intro | Thanks for reaching out",
        ))
        db.create_activity(Activity(
            prospect_id=prospect_id,
            activity_type=ActivityType.CALL,
            notes="Left voicemail",
        ))

        service = EmailService(db)
        history = service.get_email_history(prospect_id)

        assert len(history) == 2  # Only emails, not calls
        directions = {e.direction for e in history}
        subjects = {e.subject for e in history}
        assert directions == {"sent", "received"}
        assert "Intro" in subjects
        assert "Re: Intro" in subjects

    def test_get_history_empty(self, setup_db):
        """Empty history for prospect with no emails."""
        db, prospect_id, _ = setup_db
        service = EmailService(db)
        history = service.get_email_history(prospect_id)
        assert history == []

    def test_get_history_respects_limit(self, setup_db):
        """History respects limit parameter."""
        db, prospect_id, _ = setup_db

        for i in range(5):
            db.create_activity(Activity(
                prospect_id=prospect_id,
                activity_type=ActivityType.EMAIL_SENT,
                notes=f"Subject: Email {i} | Body {i}",
            ))

        service = EmailService(db)
        history = service.get_email_history(prospect_id, limit=3)
        assert len(history) == 3


class TestEmailResult:
    """Test EmailResult dataclass."""

    def test_defaults(self):
        result = EmailResult(success=True)
        assert result.message_id == ""
        assert result.activity_id is None
        assert result.draft_mode is False
