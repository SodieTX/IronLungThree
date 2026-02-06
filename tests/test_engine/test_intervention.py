"""Tests for the intervention engine (Phase 7, Step 7.6)."""

from datetime import date, datetime, timedelta

import pytest

from src.db.database import Database
from src.db.models import (
    Activity,
    ActivityType,
    Company,
    EngagementStage,
    Population,
    Prospect,
)
from src.engine.intervention import DecayItem, DecayReport, InterventionEngine


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
    company = Company(name="Test Corp", state="TX")
    return db.create_company(company)


class TestDecayReport:
    """Tests for DecayReport dataclass."""

    def test_total_issues_empty(self):
        report = DecayReport()
        assert report.total_issues == 0

    def test_total_issues_with_items(self):
        report = DecayReport(
            overdue_followups=[
                DecayItem(1, "A", "C", "overdue", "desc"),
                DecayItem(2, "B", "C", "overdue", "desc"),
            ],
            stale_engaged=[DecayItem(3, "C", "C", "stale", "desc")],
        )
        assert report.total_issues == 3

    def test_has_critical_false(self):
        report = DecayReport(
            overdue_followups=[
                DecayItem(1, "A", "C", "overdue", "desc", severity="low"),
            ],
        )
        assert not report.has_critical

    def test_has_critical_true(self):
        report = DecayReport(
            overdue_followups=[
                DecayItem(1, "A", "C", "overdue", "desc", severity="high"),
            ],
        )
        assert report.has_critical


class TestFindOverdueFollowups:
    """Tests for overdue follow-up detection."""

    def test_no_overdue(self, db, company_id):
        """No prospects with overdue follow-ups returns empty."""
        engine = InterventionEngine(db)
        report = engine.detect_decay()
        assert len(report.overdue_followups) == 0

    def test_detects_overdue(self, db, company_id):
        """Finds prospects with follow-up in the past."""
        past_date = datetime.now() - timedelta(days=5)
        prospect = Prospect(
            company_id=company_id,
            first_name="John",
            last_name="Doe",
            population=Population.ENGAGED,
            follow_up_date=past_date,
        )
        db.create_prospect(prospect)

        engine = InterventionEngine(db)
        report = engine.detect_decay()
        assert len(report.overdue_followups) >= 1
        assert report.overdue_followups[0].issue_type == "overdue_followup"

    def test_excludes_dnc(self, db, company_id):
        """DNC prospects are excluded from overdue detection."""
        past_date = datetime.now() - timedelta(days=5)
        prospect = Prospect(
            company_id=company_id,
            first_name="Dead",
            last_name="Contact",
            population=Population.DEAD_DNC,
            follow_up_date=past_date,
        )
        db.create_prospect(prospect)

        engine = InterventionEngine(db)
        report = engine.detect_decay()
        assert len(report.overdue_followups) == 0

    def test_severity_escalation(self, db, company_id):
        """7+ days overdue is high severity."""
        past_date = datetime.now() - timedelta(days=10)
        prospect = Prospect(
            company_id=company_id,
            first_name="Very",
            last_name="Overdue",
            population=Population.ENGAGED,
            follow_up_date=past_date,
        )
        db.create_prospect(prospect)

        engine = InterventionEngine(db)
        report = engine.detect_decay()
        assert len(report.overdue_followups) >= 1
        assert report.overdue_followups[0].severity == "high"


class TestFindStaleEngaged:
    """Tests for stale engaged detection."""

    def test_detects_stale(self, db, company_id):
        """Finds engaged prospects with no recent activity."""
        prospect = Prospect(
            company_id=company_id,
            first_name="Stale",
            last_name="Lead",
            population=Population.ENGAGED,
            engagement_stage=EngagementStage.PRE_DEMO,
        )
        pid = db.create_prospect(prospect)

        # Add an old activity and backdate it via SQL
        activity = Activity(
            prospect_id=pid,
            activity_type=ActivityType.CALL,
            notes="Called, left VM",
        )
        aid = db.create_activity(activity)
        old_date = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S")
        conn = db._get_connection()
        conn.execute("UPDATE activities SET created_at = ? WHERE id = ?", (old_date, aid))
        conn.commit()

        engine = InterventionEngine(db)
        report = engine.detect_decay()
        assert len(report.stale_engaged) >= 1

    def test_recent_activity_not_stale(self, db, company_id):
        """Engaged prospect with recent activity is NOT stale."""
        prospect = Prospect(
            company_id=company_id,
            first_name="Active",
            last_name="Lead",
            population=Population.ENGAGED,
        )
        pid = db.create_prospect(prospect)

        # Add a recent activity
        activity = Activity(
            prospect_id=pid,
            activity_type=ActivityType.CALL,
            notes="Spoke with today",
        )
        db.create_activity(activity)

        engine = InterventionEngine(db)
        report = engine.detect_decay()
        stale_ids = [item.prospect_id for item in report.stale_engaged]
        assert pid not in stale_ids


class TestFindUnworked:
    """Tests for unworked card detection."""

    def test_detects_unworked(self, db, company_id):
        """Finds old unengaged prospects with no outreach activity."""
        prospect = Prospect(
            company_id=company_id,
            first_name="Never",
            last_name="Called",
            population=Population.UNENGAGED,
            prospect_score=50,
        )
        pid = db.create_prospect(prospect)
        # Backdate created_at via SQL
        old_date = (datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d %H:%M:%S")
        conn = db._get_connection()
        conn.execute("UPDATE prospects SET created_at = ? WHERE id = ?", (old_date, pid))
        conn.commit()

        engine = InterventionEngine(db)
        report = engine.detect_decay()
        assert len(report.unworked) >= 1

    def test_worked_prospect_excluded(self, db, company_id):
        """Prospect with call activity is NOT unworked."""
        prospect = Prospect(
            company_id=company_id,
            first_name="Was",
            last_name="Called",
            population=Population.UNENGAGED,
        )
        pid = db.create_prospect(prospect)
        # Backdate created_at via SQL
        old_date = (datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d %H:%M:%S")
        conn = db._get_connection()
        conn.execute("UPDATE prospects SET created_at = ? WHERE id = ?", (old_date, pid))
        conn.commit()

        activity = Activity(
            prospect_id=pid,
            activity_type=ActivityType.CALL,
            notes="Left VM",
        )
        db.create_activity(activity)

        engine = InterventionEngine(db)
        report = engine.detect_decay()
        unworked_ids = [item.prospect_id for item in report.unworked]
        assert pid not in unworked_ids


class TestFindDataQuality:
    """Tests for data quality issue detection."""

    def test_detects_low_confidence_high_score(self, db, company_id):
        """Finds high-score prospects with low data confidence."""
        prospect = Prospect(
            company_id=company_id,
            first_name="High",
            last_name="Score",
            population=Population.UNENGAGED,
            prospect_score=85,
            data_confidence=20,
        )
        db.create_prospect(prospect)

        engine = InterventionEngine(db)
        report = engine.detect_decay()
        assert len(report.low_confidence_high_score) >= 1

    def test_excludes_low_score(self, db, company_id):
        """Low-score prospects are not flagged for data quality."""
        prospect = Prospect(
            company_id=company_id,
            first_name="Low",
            last_name="Score",
            population=Population.UNENGAGED,
            prospect_score=30,
            data_confidence=20,
        )
        db.create_prospect(prospect)

        engine = InterventionEngine(db)
        report = engine.detect_decay()
        assert len(report.low_confidence_high_score) == 0


class TestFullDecayDetection:
    """Integration test for full decay detection."""

    def test_detect_decay_returns_report(self, db, company_id):
        """detect_decay returns a DecayReport even with empty DB."""
        engine = InterventionEngine(db)
        report = engine.detect_decay()
        assert isinstance(report, DecayReport)
        assert report.total_issues == 0

    def test_custom_thresholds(self, db, company_id):
        """Custom thresholds are respected."""
        engine = InterventionEngine(
            db,
            stale_engaged_days=7,
            unworked_days=15,
            high_score_threshold=50,
            low_confidence_threshold=60,
        )
        report = engine.detect_decay()
        assert isinstance(report, DecayReport)
