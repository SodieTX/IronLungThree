"""Tests for the contact analyzer (Phase 7, Step 7.3)."""

from datetime import datetime, timedelta

import pytest

from src.ai.contact_analyzer import CompanyAnalysis, analyze_company, find_stalling_patterns
from src.db.database import Database
from src.db.models import (
    Activity,
    ActivityType,
    Company,
    EngagementStage,
    Population,
    Prospect,
)


@pytest.fixture
def db():
    """Create in-memory database for testing."""
    database = Database(":memory:")
    database.initialize()
    yield database
    database.close()


@pytest.fixture
def company_id(db):
    """Create a test company."""
    company = Company(name="Acme Lending", state="TX")
    return db.create_company(company)


class TestAnalyzeCompany:
    """Tests for company analysis."""

    def test_empty_company(self, db, company_id):
        """Company with no prospects returns empty analysis."""
        analysis = analyze_company(db, company_id)
        assert isinstance(analysis, CompanyAnalysis)
        assert analysis.total_contacts == 0
        assert analysis.company_name == "Acme Lending"

    def test_nonexistent_company(self, db):
        """Nonexistent company ID returns empty analysis."""
        analysis = analyze_company(db, 999)
        assert analysis.total_contacts == 0

    def test_advancing_contact(self, db, company_id):
        """Contact with recent activity is classified as advancing."""
        pid = db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Active",
                last_name="Contact",
                population=Population.ENGAGED,
                engagement_stage=EngagementStage.PRE_DEMO,
            )
        )
        db.create_activity(
            Activity(
                prospect_id=pid,
                activity_type=ActivityType.CALL,
                notes="Great call today",
            )
        )

        analysis = analyze_company(db, company_id)
        assert analysis.total_contacts == 1
        assert pid in analysis.advancing_contacts

    def test_stalling_contact(self, db, company_id):
        """Contact with old activity is classified as stalling."""
        pid = db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Stale",
                last_name="Contact",
                population=Population.ENGAGED,
            )
        )
        # Add activity and backdate it via SQL
        aid = db.create_activity(
            Activity(
                prospect_id=pid,
                activity_type=ActivityType.CALL,
                notes="Old call",
            )
        )
        old_date = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S")
        conn = db._get_connection()
        conn.execute("UPDATE activities SET created_at = ? WHERE id = ?", (old_date, aid))
        conn.commit()

        analysis = analyze_company(db, company_id)
        assert pid in analysis.stalling_contacts

    def test_multi_contact_recommendation(self, db, company_id):
        """Multiple engaged contacts generates coordination recommendation."""
        for name in ["Alice", "Bob"]:
            pid = db.create_prospect(
                Prospect(
                    company_id=company_id,
                    first_name=name,
                    last_name="Contact",
                    population=Population.ENGAGED,
                )
            )
            db.create_activity(
                Activity(prospect_id=pid, activity_type=ActivityType.CALL, notes="Called")
            )

        analysis = analyze_company(db, company_id)
        assert any("coordinate" in r.lower() or "multiple" in r.lower() for r in analysis.recommendations)

    def test_excludes_terminal_states(self, db, company_id):
        """DNC and closed-won contacts are excluded from analysis."""
        db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Dead",
                last_name="Contact",
                population=Population.DEAD_DNC,
            )
        )
        db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Won",
                last_name="Contact",
                population=Population.CLOSED_WON,
            )
        )

        analysis = analyze_company(db, company_id)
        assert analysis.total_contacts == 0

    def test_lost_contact_warning(self, db, company_id):
        """Previously lost contacts generate a warning."""
        db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Lost",
                last_name="One",
                population=Population.LOST,
            )
        )
        db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="New",
                last_name="Prospect",
                population=Population.UNENGAGED,
            )
        )

        analysis = analyze_company(db, company_id)
        assert any("lost" in r.lower() for r in analysis.recommendations)


class TestFindStallingPatterns:
    """Tests for stalling pattern detection."""

    def test_empty_db(self, db):
        """Empty database returns empty list."""
        result = find_stalling_patterns(db)
        assert result == []

    def test_finds_stalling_engaged(self, db, company_id):
        """Finds engaged prospects with no recent activity."""
        pid = db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Stale",
                last_name="Lead",
                population=Population.ENGAGED,
                engagement_stage=EngagementStage.POST_DEMO,
            )
        )
        # Add activity and backdate it via SQL
        aid = db.create_activity(
            Activity(
                prospect_id=pid,
                activity_type=ActivityType.CALL,
                notes="Talked post-demo",
            )
        )
        old_date = (datetime.now() - timedelta(days=18)).strftime("%Y-%m-%d %H:%M:%S")
        conn = db._get_connection()
        conn.execute("UPDATE activities SET created_at = ? WHERE id = ?", (old_date, aid))
        conn.commit()

        result = find_stalling_patterns(db)
        assert len(result) >= 1
        assert result[0]["prospect_id"] == pid
        assert result[0]["days_stale"] >= 14
