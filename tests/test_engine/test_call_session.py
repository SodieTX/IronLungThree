"""Tests for call session service."""

from datetime import datetime

import pytest

from src.db.models import (
    Activity,
    ActivityType,
    Company,
    ContactMethod,
    ContactMethodType,
    Prospect,
)
from src.engine.call_session import CallPrep, CallSession


@pytest.fixture
def setup_call_db(memory_db):
    """Database with prospect, phone, and activity history."""
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
        title="VP of Operations",
        attempt_count=2,
    )
    prospect_id = memory_db.create_prospect(prospect)

    # Add phone
    memory_db.create_contact_method(ContactMethod(
        prospect_id=prospect_id,
        type=ContactMethodType.PHONE,
        value="713-555-1234",
        label="work",
        is_verified=True,
    ))

    # Add activity history
    memory_db.create_activity(Activity(
        prospect_id=prospect_id,
        activity_type=ActivityType.CALL,
        notes="Left voicemail about Q1 priorities",
    ))

    return memory_db, prospect_id, company_id


class TestPrepareCall:
    """Test call preparation."""

    def test_prepare_call_basic(self, setup_call_db):
        """Prepare call returns populated CallPrep."""
        db, prospect_id, _ = setup_call_db
        session = CallSession(db)
        prep = session.prepare_call(prospect_id)

        assert prep.prospect_id == prospect_id
        assert prep.prospect_name == "John Doe"
        assert prep.company_name == "Acme Lending"
        assert prep.title == "VP of Operations"
        assert prep.phone_number == "713-555-1234"
        assert prep.phone_label == "work"
        assert prep.timezone == "central"

    def test_prepare_call_attempt_number(self, setup_call_db):
        """Attempt number is current count + 1."""
        db, prospect_id, _ = setup_call_db
        session = CallSession(db)
        prep = session.prepare_call(prospect_id)
        assert prep.attempt_number == 3  # attempt_count=2, so next is 3

    def test_prepare_call_last_contact(self, setup_call_db):
        """Last contact summary is populated."""
        db, prospect_id, _ = setup_call_db
        session = CallSession(db)
        prep = session.prepare_call(prospect_id)
        assert "Called" in prep.last_contact_summary

    def test_prepare_call_talking_points(self, setup_call_db):
        """Talking points include relevant context."""
        db, prospect_id, _ = setup_call_db
        session = CallSession(db)
        prep = session.prepare_call(prospect_id)
        assert len(prep.talking_points) > 0
        # Should mention title
        assert any("VP of Operations" in p for p in prep.talking_points)

    def test_prepare_call_recent_notes(self, setup_call_db):
        """Recent notes pulled from activity history."""
        db, prospect_id, _ = setup_call_db
        session = CallSession(db)
        prep = session.prepare_call(prospect_id)
        assert len(prep.recent_notes) > 0
        assert "Q1 priorities" in prep.recent_notes[0]

    def test_prepare_call_missing_prospect(self, memory_db):
        """Raises ValueError for nonexistent prospect."""
        session = CallSession(memory_db)
        with pytest.raises(ValueError, match="not found"):
            session.prepare_call(9999)

    def test_prepare_call_no_phone(self, memory_db):
        """Handles prospect with no phone number."""
        company = Company(name="No Phone Co", name_normalized="no phone")
        cid = memory_db.create_company(company)
        pid = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="Jane", last_name="Smith",
        ))
        session = CallSession(memory_db)
        prep = session.prepare_call(pid)
        assert prep.phone_number == ""

    def test_prepare_call_no_activities(self, memory_db):
        """Handles prospect with no activity history."""
        company = Company(name="New Co", name_normalized="new")
        cid = memory_db.create_company(company)
        pid = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="Bob", last_name="Jones",
            attempt_count=0,
        ))
        session = CallSession(memory_db)
        prep = session.prepare_call(pid)
        assert prep.last_contact_summary == "No prior contact"
        assert prep.attempt_number == 1
        assert any("First outreach" in p for p in prep.talking_points)


class TestPhoneSelection:
    """Test phone number selection logic."""

    def test_prefers_verified_phone(self, memory_db):
        """Verified phone is preferred over unverified."""
        company = Company(name="Test", name_normalized="test")
        cid = memory_db.create_company(company)
        pid = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="A", last_name="B",
        ))
        memory_db.create_contact_method(ContactMethod(
            prospect_id=pid, type=ContactMethodType.PHONE,
            value="111-111-1111", label="work", is_verified=False,
        ))
        memory_db.create_contact_method(ContactMethod(
            prospect_id=pid, type=ContactMethodType.PHONE,
            value="222-222-2222", label="cell", is_verified=True,
        ))

        session = CallSession(memory_db)
        prep = session.prepare_call(pid)
        assert prep.phone_number == "222-222-2222"

    def test_prefers_cell_over_work(self, memory_db):
        """Cell/mobile preferred over work when both verified."""
        company = Company(name="Test", name_normalized="test")
        cid = memory_db.create_company(company)
        pid = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="A", last_name="B",
        ))
        memory_db.create_contact_method(ContactMethod(
            prospect_id=pid, type=ContactMethodType.PHONE,
            value="111-111-1111", label="work", is_verified=True,
        ))
        memory_db.create_contact_method(ContactMethod(
            prospect_id=pid, type=ContactMethodType.PHONE,
            value="222-222-2222", label="cell", is_verified=True,
        ))

        session = CallSession(memory_db)
        prep = session.prepare_call(pid)
        assert prep.phone_number == "222-222-2222"


class TestLogOutcome:
    """Test call outcome logging."""

    def test_log_outcome(self, setup_call_db):
        """Log outcome creates activity record."""
        db, prospect_id, _ = setup_call_db
        session = CallSession(db)

        activity_id = session.log_outcome(
            prospect_id=prospect_id,
            outcome="spoke_with",
            notes="Discussed pricing, wants to see a demo next week",
        )

        assert activity_id > 0
        activities = db.get_activities(prospect_id)
        call_acts = [a for a in activities if a.notes and "pricing" in a.notes]
        assert len(call_acts) == 1
        assert call_acts[0].activity_type == ActivityType.CALL

    def test_log_outcome_with_follow_up(self, setup_call_db):
        """Log outcome includes follow-up date in notes."""
        db, prospect_id, _ = setup_call_db
        session = CallSession(db)

        follow_up = datetime(2026, 2, 15, 10, 0)
        activity_id = session.log_outcome(
            prospect_id=prospect_id,
            outcome="interested",
            notes="Wants to talk next week",
            follow_up_date=follow_up,
        )

        activities = db.get_activities(prospect_id)
        latest = [a for a in activities if a.id == activity_id]
        assert len(latest) == 1
        assert "2026-02-15" in latest[0].notes
