"""Tests for dead lead resurrection audit (Phase 7, Step 7.9)."""

from datetime import date, datetime, timedelta

import pytest

from src.db.database import Database
from src.db.models import (
    Company,
    Population,
    Prospect,
)
from src.engine.resurrection import (
    ResurrectionCandidate,
    _generate_rationale,
    find_resurrection_candidates,
    generate_resurrection_report,
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
    return db.create_company(Company(name="Lost Corp", state="TX"))


def _create_lost_prospect(
    db,
    company_id,
    first_name,
    last_name,
    months_ago=14,
    score=50,
    lost_reason=None,
    lost_competitor=None,
    population=Population.LOST,
):
    """Helper to create a lost prospect with a lost_date in the past."""
    lost_date = (datetime.now() - timedelta(days=months_ago * 30)).strftime("%Y-%m-%d")
    pid = db.create_prospect(
        Prospect(
            company_id=company_id,
            first_name=first_name,
            last_name=last_name,
            population=population,
            prospect_score=score,
        )
    )
    # Set lost_date, lost_reason, lost_competitor directly via SQL
    # to avoid enum validation in create_prospect
    conn = db._get_connection()
    conn.execute(
        "UPDATE prospects SET lost_date = ?, lost_reason = ?, lost_competitor = ? WHERE id = ?",
        (lost_date, lost_reason, lost_competitor, pid),
    )
    conn.commit()
    return pid


class TestFindResurrectionCandidates:
    """Tests for find_resurrection_candidates."""

    def test_empty_db(self, db):
        """Empty DB returns no candidates."""
        candidates = find_resurrection_candidates(db)
        assert candidates == []

    def test_finds_old_lost(self, db, company_id):
        """Finds prospect lost 14+ months ago with decent score."""
        _create_lost_prospect(db, company_id, "Old", "Lost", months_ago=14, score=50)

        candidates = find_resurrection_candidates(db)
        assert len(candidates) == 1
        assert candidates[0].prospect_name == "Old Lost"
        assert candidates[0].months_dormant >= 12

    def test_excludes_recent_lost(self, db, company_id):
        """Does NOT find prospect lost only 6 months ago."""
        _create_lost_prospect(db, company_id, "Recent", "Lost", months_ago=6, score=50)

        candidates = find_resurrection_candidates(db)
        assert len(candidates) == 0

    def test_excludes_low_score(self, db, company_id):
        """Does NOT find prospect with score below threshold."""
        _create_lost_prospect(db, company_id, "Low", "Score", months_ago=14, score=10)

        candidates = find_resurrection_candidates(db)
        assert len(candidates) == 0

    def test_never_resurrects_dnc(self, db, company_id):
        """NEVER includes DNC contacts — absolute and permanent."""
        _create_lost_prospect(
            db,
            company_id,
            "Dead",
            "DNC",
            months_ago=24,
            score=90,
            population=Population.DEAD_DNC,
        )

        candidates = find_resurrection_candidates(db)
        names = [c.prospect_name for c in candidates]
        assert "Dead DNC" not in names

    def test_sorted_by_score_desc(self, db, company_id):
        """Candidates are sorted by original score, highest first."""
        _create_lost_prospect(db, company_id, "Low", "Score", months_ago=14, score=40)
        _create_lost_prospect(db, company_id, "High", "Score", months_ago=14, score=80)
        _create_lost_prospect(db, company_id, "Mid", "Score", months_ago=14, score=60)

        candidates = find_resurrection_candidates(db)
        scores = [c.original_score for c in candidates]
        assert scores == sorted(scores, reverse=True)

    def test_includes_lost_reason(self, db, company_id):
        """Candidate includes the lost reason."""
        _create_lost_prospect(
            db,
            company_id,
            "Budget",
            "Lost",
            months_ago=14,
            score=50,
            lost_reason="budget",
        )

        candidates = find_resurrection_candidates(db)
        assert len(candidates) == 1
        assert "budget" in candidates[0].reason

    def test_includes_competitor_info(self, db, company_id):
        """Candidate includes competitor information in reason."""
        _create_lost_prospect(
            db,
            company_id,
            "Comp",
            "Lost",
            months_ago=14,
            score=50,
            lost_reason="lost_to_competitor",
            lost_competitor="LoanPro",
        )

        candidates = find_resurrection_candidates(db)
        assert len(candidates) == 1
        assert "LoanPro" in candidates[0].reason

    def test_custom_min_months(self, db, company_id):
        """Custom min_months_dormant parameter works."""
        _create_lost_prospect(db, company_id, "Old", "Lost", months_ago=8, score=50)

        # Default 12 months: should not find
        assert len(find_resurrection_candidates(db)) == 0
        # Custom 6 months: should find
        assert len(find_resurrection_candidates(db, min_months_dormant=6)) == 1

    def test_custom_min_score(self, db, company_id):
        """Custom min_original_score parameter works."""
        _create_lost_prospect(db, company_id, "Med", "Score", months_ago=14, score=25)

        # Default 30: should not find
        assert len(find_resurrection_candidates(db)) == 0
        # Custom 20: should find
        assert len(find_resurrection_candidates(db, min_original_score=20)) == 1


class TestGenerateRationale:
    """Tests for rationale generation."""

    def test_timing_rationale(self):
        """Timing loss generates timing-specific rationale."""
        rationale = _generate_rationale("timing", None, 14)
        assert "timing" in rationale.lower()

    def test_budget_rationale(self):
        """Budget loss generates budget-specific rationale."""
        rationale = _generate_rationale("budget", None, 14)
        assert "budget" in rationale.lower()

    def test_competitor_rationale(self):
        """Competitor loss generates competitor-specific rationale."""
        rationale = _generate_rationale("lost_to_competitor", "LoanPro", 14)
        assert "LoanPro" in rationale

    def test_competitor_no_name(self):
        """Competitor loss without name still generates rationale."""
        rationale = _generate_rationale("competitor", None, 14)
        assert "competitor" in rationale.lower() or "contract" in rationale.lower()

    def test_not_buying_rationale(self):
        """Not buying generates appropriate rationale."""
        rationale = _generate_rationale("not_buying", None, 14)
        assert "buying" in rationale.lower() or "evolve" in rationale.lower()

    def test_long_dormancy_rationale(self):
        """24+ months dormancy gets special emphasis."""
        rationale = _generate_rationale(None, None, 24)
        assert "2+" in rationale or "24 months" in rationale

    def test_medium_dormancy_rationale(self):
        """18-23 months dormancy mentions budget cycles."""
        rationale = _generate_rationale(None, None, 18)
        assert "budget" in rationale.lower() or "contract" in rationale.lower()


class TestGenerateResurrectionReport:
    """Tests for the report generation."""

    def test_empty_report(self, db):
        """No candidates produces appropriate message."""
        report = generate_resurrection_report(db)
        assert "no resurrection" in report.lower() or "no" in report.lower()

    def test_report_with_candidates(self, db, company_id):
        """Report includes candidate details."""
        _create_lost_prospect(
            db,
            company_id,
            "Revival",
            "Candidate",
            months_ago=14,
            score=65,
            lost_reason="timing",
        )

        report = generate_resurrection_report(db)
        assert "RESURRECTION" in report.upper()
        assert "Revival Candidate" in report
        assert "Lost Corp" in report
        assert "65" in report  # score
        assert "timing" in report.lower()

    def test_report_includes_instructions(self, db, company_id):
        """Report includes instructions on how to resurrect."""
        _create_lost_prospect(db, company_id, "Test", "Lead", months_ago=14, score=50)

        report = generate_resurrection_report(db)
        assert "unengaged" in report.lower() or "Unengaged" in report
