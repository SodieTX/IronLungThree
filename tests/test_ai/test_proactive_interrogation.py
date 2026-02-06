"""Tests for proactive card interrogation (Phase 7, Step 7.7)."""

from datetime import date, datetime, timedelta

import pytest

from src.ai.proactive_interrogation import (
    CardFinding,
    InterrogationReport,
    get_card_findings,
    interrogate_cards,
)
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
    return db.create_company(Company(name="Test Corp", state="TX"))


class TestInterrogationReport:
    """Tests for InterrogationReport dataclass."""

    def test_empty_report(self):
        """Empty report has zero findings."""
        report = InterrogationReport()
        assert report.total_findings == 0
        assert not report.has_urgent
        assert report.findings_text == ""

    def test_total_findings(self):
        """Total includes all categories."""
        report = InterrogationReport(
            orphans=[CardFinding(1, "A", "C", "orphan", "desc")],
            stale_leads=[CardFinding(2, "B", "C", "stale", "desc")],
            overdue_followups=[CardFinding(3, "C", "C", "overdue", "desc")],
            data_concerns=[CardFinding(4, "D", "C", "dq", "desc")],
        )
        assert report.total_findings == 4

    def test_has_urgent_high(self):
        """has_urgent is True when any finding is high severity."""
        report = InterrogationReport(
            orphans=[CardFinding(1, "A", "C", "orphan", "desc", severity="high")],
        )
        assert report.has_urgent

    def test_has_urgent_none(self):
        """has_urgent is False when all findings are medium/low."""
        report = InterrogationReport(
            data_concerns=[CardFinding(1, "A", "C", "dq", "desc", severity="medium")],
        )
        assert not report.has_urgent

    def test_findings_text_includes_sections(self):
        """Findings text includes orphan, overdue, stale, and data quality sections."""
        report = InterrogationReport(
            orphans=[CardFinding(1, "Alice", "Corp", "orphan", "desc", suggested_action="Set date")],
            overdue_followups=[CardFinding(2, "Bob", "Corp", "overdue", "3 days ago")],
            stale_leads=[CardFinding(3, "Charlie", "Corp", "stale", "No activity 14d")],
            data_concerns=[CardFinding(4, "Dave", "Corp", "dq", "Score 80 confidence 30")],
        )
        text = report.findings_text
        assert "4 items" in text
        assert "Orphaned" in text
        assert "Overdue" in text
        assert "Going stale" in text
        assert "Data quality" in text
        assert "Alice" in text


class TestInterrogateCards:
    """Tests for the interrogate_cards function."""

    def test_empty_db(self, db):
        """Empty DB returns no findings."""
        report = interrogate_cards(db)
        assert report.total_findings == 0

    def test_finds_orphaned_engaged(self, db, company_id):
        """Detects engaged prospects with no follow-up date."""
        db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Orphan",
                last_name="Test",
                population=Population.ENGAGED,
                engagement_stage=EngagementStage.PRE_DEMO,
                follow_up_date=None,
            )
        )

        report = interrogate_cards(db)
        assert len(report.orphans) == 1
        assert report.orphans[0].prospect_name == "Orphan Test"
        assert report.orphans[0].severity == "high"

    def test_no_orphan_if_followup_set(self, db, company_id):
        """Engaged with follow-up date is NOT an orphan."""
        db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Good",
                last_name="Prospect",
                population=Population.ENGAGED,
                follow_up_date=datetime.now() + timedelta(days=3),
            )
        )

        report = interrogate_cards(db)
        assert len(report.orphans) == 0

    def test_finds_overdue_followups(self, db, company_id):
        """Detects follow-ups that already passed."""
        db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Overdue",
                last_name="Person",
                population=Population.ENGAGED,
                follow_up_date=datetime.now() - timedelta(days=5),
            )
        )

        report = interrogate_cards(db)
        assert len(report.overdue_followups) >= 1

    def test_overdue_severity_escalation(self, db, company_id):
        """Overdue 7+ days is high severity."""
        db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="VeryOverdue",
                last_name="Person",
                population=Population.ENGAGED,
                follow_up_date=datetime.now() - timedelta(days=10),
            )
        )

        report = interrogate_cards(db)
        overdue = [f for f in report.overdue_followups if f.prospect_name == "VeryOverdue Person"]
        assert len(overdue) >= 1
        assert overdue[0].severity == "high"

    def test_excludes_dnc_from_overdue(self, db, company_id):
        """DNC prospects are not flagged as overdue."""
        db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Dead",
                last_name="Contact",
                population=Population.DEAD_DNC,
                follow_up_date=datetime.now() - timedelta(days=30),
            )
        )

        report = interrogate_cards(db)
        names = [f.prospect_name for f in report.overdue_followups]
        assert "Dead Contact" not in names

    def test_finds_stale_engaged(self, db, company_id):
        """Detects engaged leads with no recent activity."""
        pid = db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Stale",
                last_name="Lead",
                population=Population.ENGAGED,
                follow_up_date=datetime.now() + timedelta(days=5),
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

        report = interrogate_cards(db)
        stale_names = [f.prospect_name for f in report.stale_leads]
        assert "Stale Lead" in stale_names

    def test_stale_severity_escalation(self, db, company_id):
        """Stale 21+ days is high severity."""
        pid = db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="VeryStale",
                last_name="Lead",
                population=Population.ENGAGED,
                follow_up_date=datetime.now() + timedelta(days=5),
            )
        )
        aid = db.create_activity(
            Activity(
                prospect_id=pid,
                activity_type=ActivityType.CALL,
                notes="Ancient call",
            )
        )
        old_date = (datetime.now() - timedelta(days=25)).strftime("%Y-%m-%d %H:%M:%S")
        conn = db._get_connection()
        conn.execute("UPDATE activities SET created_at = ? WHERE id = ?", (old_date, aid))
        conn.commit()

        report = interrogate_cards(db)
        stale = [f for f in report.stale_leads if f.prospect_name == "VeryStale Lead"]
        assert len(stale) >= 1
        assert stale[0].severity == "high"

    def test_finds_data_quality_issues(self, db, company_id):
        """Detects high-score/low-confidence prospects."""
        db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Bad",
                last_name="Data",
                population=Population.ENGAGED,
                prospect_score=85,
                data_confidence=30,
            )
        )

        report = interrogate_cards(db)
        dq_names = [f.prospect_name for f in report.data_concerns]
        assert "Bad Data" in dq_names


class TestGetCardFindings:
    """Tests for per-card findings."""

    def test_nonexistent_prospect(self, db):
        """Nonexistent prospect returns empty findings."""
        findings = get_card_findings(db, 999)
        assert findings == []

    def test_orphan_finding(self, db, company_id):
        """Engaged prospect with no follow-up gets orphan finding."""
        pid = db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Orphan",
                last_name="Card",
                population=Population.ENGAGED,
                follow_up_date=None,
            )
        )

        findings = get_card_findings(db, pid)
        types = [f.finding_type for f in findings]
        assert "orphan" in types

    def test_overdue_finding(self, db, company_id):
        """Overdue follow-up generates finding."""
        pid = db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Late",
                last_name="Followup",
                population=Population.ENGAGED,
                follow_up_date=datetime.now() - timedelta(days=3),
            )
        )

        findings = get_card_findings(db, pid)
        types = [f.finding_type for f in findings]
        assert "overdue_followup" in types

    def test_stale_finding(self, db, company_id):
        """Stale engaged prospect generates finding."""
        pid = db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Stale",
                last_name="Card",
                population=Population.ENGAGED,
                follow_up_date=datetime.now() + timedelta(days=5),
            )
        )
        aid = db.create_activity(
            Activity(
                prospect_id=pid,
                activity_type=ActivityType.EMAIL_SENT,
                notes="Old email",
            )
        )
        old_date = (datetime.now() - timedelta(days=16)).strftime("%Y-%m-%d %H:%M:%S")
        conn = db._get_connection()
        conn.execute("UPDATE activities SET created_at = ? WHERE id = ?", (old_date, aid))
        conn.commit()

        findings = get_card_findings(db, pid)
        types = [f.finding_type for f in findings]
        assert "stale_engaged" in types

    def test_data_quality_finding(self, db, company_id):
        """High-score/low-confidence generates finding."""
        pid = db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Sketchy",
                last_name="Data",
                population=Population.ENGAGED,
                prospect_score=80,
                data_confidence=25,
            )
        )

        findings = get_card_findings(db, pid)
        types = [f.finding_type for f in findings]
        assert "data_quality" in types

    def test_clean_card_no_findings(self, db, company_id):
        """Healthy card returns no findings."""
        pid = db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Clean",
                last_name="Card",
                population=Population.ENGAGED,
                follow_up_date=datetime.now() + timedelta(days=2),
                prospect_score=60,
                data_confidence=80,
            )
        )
        # Recent activity
        db.create_activity(
            Activity(
                prospect_id=pid,
                activity_type=ActivityType.CALL,
                notes="Recent call",
                created_at=datetime.now() - timedelta(days=2),
            )
        )

        findings = get_card_findings(db, pid)
        assert findings == []
