"""Tests for end-of-day summary and cockpit data.

Tests Step 2.11: EOD Summary + Daily Cockpit
    - EOD summary captures today's activity counts
    - Cockpit provides real-time queue metrics
    - Both work with empty databases
"""

from datetime import date, datetime, timedelta

import pytest

from src.content.daily_cockpit import CockpitData, get_cockpit_data
from src.content.eod_summary import EODSummary, generate_eod_summary
from src.db.database import Database
from src.db.models import Activity, ActivityType, Company, EngagementStage, Population, Prospect


@pytest.fixture
def db():
    """Fresh in-memory database."""
    database = Database(":memory:")
    database.initialize()
    yield database
    database.close()


@pytest.fixture
def company_id(db):
    """Create a test company."""
    return db.create_company(Company(name="Test Corp", state="TX"))


@pytest.fixture
def active_db(db, company_id):
    """Database with today's activity."""
    # Create some prospects
    p1 = db.create_prospect(
        Prospect(
            company_id=company_id,
            first_name="Active",
            last_name="One",
            population=Population.UNENGAGED,
            prospect_score=80,
        )
    )
    p2 = db.create_prospect(
        Prospect(
            company_id=company_id,
            first_name="Active",
            last_name="Two",
            population=Population.ENGAGED,
            engagement_stage=EngagementStage.PRE_DEMO,
            follow_up_date=datetime.now(),
        )
    )

    # Log some activities today
    db.create_activity(
        Activity(
            prospect_id=p1,
            activity_type=ActivityType.CALL,
            notes="Called, no answer",
            created_at=datetime.now(),
        )
    )
    db.create_activity(
        Activity(
            prospect_id=p1,
            activity_type=ActivityType.EMAIL_SENT,
            notes="Sent follow-up",
            created_at=datetime.now(),
        )
    )
    db.create_activity(
        Activity(
            prospect_id=p2,
            activity_type=ActivityType.CALL,
            notes="Had a great conversation",
            created_at=datetime.now(),
        )
    )

    return db


# =============================================================================
# EOD SUMMARY
# =============================================================================


class TestEODSummary:
    """Test end-of-day summary."""

    def test_generates_summary(self, active_db):
        """Generates an EOD summary."""
        summary = generate_eod_summary(active_db)
        assert isinstance(summary, EODSummary)
        assert summary.date is not None

    def test_counts_calls(self, active_db):
        """Counts today's calls."""
        summary = generate_eod_summary(active_db)
        assert summary.calls_made >= 2

    def test_counts_emails(self, active_db):
        """Counts today's emails."""
        summary = generate_eod_summary(active_db)
        assert summary.emails_sent >= 1

    def test_counts_cards_processed(self, active_db):
        """Counts unique prospects touched."""
        summary = generate_eod_summary(active_db)
        assert summary.cards_processed >= 2  # Two different prospects

    def test_has_tomorrow_preview(self, active_db):
        """Includes tomorrow preview."""
        summary = generate_eod_summary(active_db)
        assert summary.tomorrow_preview != ""
        assert "follow-ups" in summary.tomorrow_preview

    def test_has_full_text(self, active_db):
        """Has composed full text."""
        summary = generate_eod_summary(active_db)
        assert "IRONLUNG 3" in summary.full_text
        assert "END OF DAY" in summary.full_text
        assert "Cards worked" in summary.full_text

    def test_empty_database(self, db):
        """Works with empty database."""
        summary = generate_eod_summary(db)
        assert isinstance(summary, EODSummary)
        assert summary.cards_processed == 0
        assert summary.calls_made == 0

    def test_empty_day_message(self, db):
        """Empty day gets appropriate message."""
        summary = generate_eod_summary(db)
        assert "No cards processed" in summary.full_text


# =============================================================================
# COCKPIT DATA
# =============================================================================


class TestCockpitData:
    """Test real-time cockpit metrics."""

    def test_generates_cockpit_data(self, active_db):
        """Generates cockpit data."""
        data = get_cockpit_data(active_db)
        assert isinstance(data, CockpitData)

    def test_total_prospects(self, active_db):
        """Reports total prospect count."""
        data = get_cockpit_data(active_db)
        assert data.total_prospects >= 2

    def test_engaged_count(self, active_db):
        """Reports engaged count."""
        data = get_cockpit_data(active_db)
        assert data.engaged_count >= 1

    def test_queue_total(self, active_db):
        """Reports queue total."""
        data = get_cockpit_data(active_db)
        assert data.queue_total >= 0

    def test_empty_database(self, db):
        """Works with empty database."""
        data = get_cockpit_data(db)
        assert isinstance(data, CockpitData)
        assert data.total_prospects == 0
        assert data.queue_total == 0
        assert data.overdue_count == 0
