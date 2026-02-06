"""Tests for prospect insights (Phase 7, Step 7.4)."""

from datetime import datetime, timedelta

import pytest

from src.ai.insights import ProspectInsights, generate_insights
from src.db.database import Database
from src.db.models import (
    Activity,
    ActivityOutcome,
    ActivityType,
    Company,
    ContactMethod,
    ContactMethodType,
    EngagementStage,
    IntelCategory,
    IntelNugget,
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
    company = Company(name="Insight Corp", state="CA")
    return db.create_company(company)


class TestGenerateInsights:
    """Tests for insight generation."""

    def test_nonexistent_prospect(self, db):
        """Nonexistent prospect returns low-confidence insights."""
        insights = generate_insights(db, 999)
        assert isinstance(insights, ProspectInsights)
        assert insights.confidence == 0.0

    def test_basic_prospect(self, db, company_id):
        """Basic prospect gets default approach recommendation."""
        pid = db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Basic",
                last_name="Prospect",
                population=Population.UNENGAGED,
            )
        )

        insights = generate_insights(db, pid)
        assert insights.prospect_id == pid
        assert len(insights.best_approach) > 0
        assert insights.confidence == 0.2  # Low data

    def test_email_preference(self, db, company_id):
        """Email preference influences approach."""
        pid = db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Email",
                last_name="Lover",
                population=Population.UNENGAGED,
                preferred_contact_method="email",
            )
        )

        insights = generate_insights(db, pid)
        assert "email" in insights.best_approach.lower()

    def test_engaged_closing_stage(self, db, company_id):
        """Closing stage gets specific approach."""
        pid = db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Closing",
                last_name="Deal",
                population=Population.ENGAGED,
                engagement_stage=EngagementStage.CLOSING,
            )
        )
        db.create_activity(
            Activity(prospect_id=pid, activity_type=ActivityType.CALL, notes="Closing discussion")
        )

        insights = generate_insights(db, pid)
        assert "closing" in insights.best_approach.lower()

    def test_objections_from_notes(self, db, company_id):
        """Objections detected from activity notes."""
        pid = db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Price",
                last_name="Sensitive",
                population=Population.ENGAGED,
            )
        )
        db.create_activity(
            Activity(
                prospect_id=pid,
                activity_type=ActivityType.CALL,
                notes="They mentioned pricing concerns and need budget approval",
            )
        )

        insights = generate_insights(db, pid)
        assert len(insights.likely_objections) >= 1
        objection_text = " ".join(insights.likely_objections).lower()
        assert "pricing" in objection_text or "budget" in objection_text

    def test_competitor_vulnerabilities(self, db, company_id):
        """Competitor intel generates vulnerability analysis."""
        pid = db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Comp",
                last_name="Battle",
                population=Population.ENGAGED,
            )
        )
        db.create_intel_nugget(
            IntelNugget(
                prospect_id=pid,
                category=IntelCategory.COMPETITOR,
                content="Currently using Encompass LOS",
            )
        )

        insights = generate_insights(db, pid)
        assert len(insights.competitive_vulnerabilities) >= 1
        vuln_text = " ".join(insights.competitive_vulnerabilities).lower()
        assert "encompass" in vuln_text

    def test_overdue_timing_recommendation(self, db, company_id):
        """Overdue follow-up generates urgent timing recommendation."""
        past_date = datetime.now() - timedelta(days=5)
        pid = db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Overdue",
                last_name="Follow",
                population=Population.ENGAGED,
                follow_up_date=past_date,
            )
        )

        insights = generate_insights(db, pid)
        assert insights.timing_recommendation is not None
        assert "overdue" in insights.timing_recommendation.lower()

    def test_orphan_timing_recommendation(self, db, company_id):
        """Engaged with no follow-up gets orphan warning."""
        pid = db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Orphan",
                last_name="Engaged",
                population=Population.ENGAGED,
            )
        )

        insights = generate_insights(db, pid)
        assert insights.timing_recommendation is not None
        assert "orphan" in insights.timing_recommendation.lower()

    def test_confidence_scales_with_data(self, db, company_id):
        """More data points increase confidence."""
        pid = db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Rich",
                last_name="Data",
                population=Population.ENGAGED,
            )
        )
        # Add many activities
        for i in range(8):
            db.create_activity(
                Activity(
                    prospect_id=pid,
                    activity_type=ActivityType.CALL,
                    notes=f"Call {i}",
                )
            )
        # Add nuggets
        for i in range(3):
            db.create_intel_nugget(
                IntelNugget(
                    prospect_id=pid,
                    category=IntelCategory.KEY_FACT,
                    content=f"Fact {i}",
                )
            )

        insights = generate_insights(db, pid)
        assert insights.confidence >= 0.8

    def test_many_attempts_no_connection(self, db, company_id):
        """Many attempts with no connection suggests different approach."""
        pid = db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Unreachable",
                last_name="Person",
                population=Population.UNENGAGED,
                attempt_count=6,
            )
        )
        for i in range(6):
            db.create_activity(
                Activity(
                    prospect_id=pid,
                    activity_type=ActivityType.CALL,
                    outcome=ActivityOutcome.NO_ANSWER,
                    notes=f"No answer attempt {i}",
                )
            )

        insights = generate_insights(db, pid)
        assert "different" in insights.best_approach.lower() or "linkedin" in insights.best_approach.lower()
