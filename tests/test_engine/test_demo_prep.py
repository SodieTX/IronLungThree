"""Tests for demo prep generator.

Tests Step 3.8: Demo Prep Generator
    - Full prep generation with all data
    - Prep with minimal data
    - Pain point extraction
    - Competitor extraction
    - Talking point generation
    - History summarization
"""

import pytest

from src.db.database import Database
from src.db.models import (
    Activity,
    ActivityType,
    Company,
    IntelCategory,
    IntelNugget,
    Population,
    Prospect,
)
from src.engine.demo_prep import (
    DemoPrep,
    _extract_competitors,
    _extract_pain_points,
    _generate_talking_points,
    _summarize_history,
    generate_prep,
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
    """Create a test company with full data, return its ID."""
    company = Company(
        name="ABC Lending, LLC",
        state="TX",
        size="medium",
        domain="abclending.com",
        loan_types='["bridge", "fix_and_flip"]',
    )
    return db.create_company(company)


@pytest.fixture
def sparse_company_id(db):
    """Create a company with minimal data, return its ID."""
    company = Company(name="Unknown Co")
    return db.create_company(company)


@pytest.fixture
def prospect_id(db, company_id):
    """Create a prospect with activities and nuggets, return its ID."""
    prospect = Prospect(
        company_id=company_id,
        first_name="John",
        last_name="Smith",
        title="CEO",
        population=Population.ENGAGED,
    )
    pid = db.create_prospect(prospect)

    # Add activities
    db.create_activity(
        Activity(
            prospect_id=pid,
            activity_type=ActivityType.CALL,
            notes="Discussed their current lending workflow pain points",
        )
    )
    db.create_activity(
        Activity(
            prospect_id=pid,
            activity_type=ActivityType.EMAIL_SENT,
            notes="Sent product overview",
        )
    )

    # Add intel nuggets
    db.create_intel_nugget(
        IntelNugget(
            prospect_id=pid,
            category=IntelCategory.PAIN_POINT,
            content="Manual underwriting process is too slow",
        )
    )
    db.create_intel_nugget(
        IntelNugget(
            prospect_id=pid,
            category=IntelCategory.PAIN_POINT,
            content="Compliance tracking is done in spreadsheets",
        )
    )
    db.create_intel_nugget(
        IntelNugget(
            prospect_id=pid,
            category=IntelCategory.COMPETITOR,
            content="LendingPad",
        )
    )
    db.create_intel_nugget(
        IntelNugget(
            prospect_id=pid,
            category=IntelCategory.COMPETITOR,
            content="Encompass",
        )
    )
    db.create_intel_nugget(
        IntelNugget(
            prospect_id=pid,
            category=IntelCategory.DECISION_TIMELINE,
            content="Looking to decide by end of Q2",
        )
    )
    db.create_intel_nugget(
        IntelNugget(
            prospect_id=pid,
            category=IntelCategory.KEY_FACT,
            content="Company recently hired 5 new loan officers",
        )
    )

    return pid


@pytest.fixture
def sparse_prospect_id(db, sparse_company_id):
    """Create a prospect with no activities or nuggets, return its ID."""
    prospect = Prospect(
        company_id=sparse_company_id,
        first_name="Jane",
        last_name="Doe",
        population=Population.ENGAGED,
    )
    return db.create_prospect(prospect)


# =============================================================================
# FULL PREP GENERATION
# =============================================================================


class TestGeneratePrep:
    """Test full demo prep generation."""

    def test_generates_prep_with_full_data(self, db, prospect_id):
        """Generates complete prep from rich prospect data."""
        prep = generate_prep(db, prospect_id)

        assert isinstance(prep, DemoPrep)
        assert prep.prospect_name == "John Smith"
        assert prep.company_name == "ABC Lending, LLC"
        assert prep.company_size == "medium"
        assert prep.state == "TX"

    def test_includes_loan_types(self, db, prospect_id):
        """Loan types are parsed from company JSON field."""
        prep = generate_prep(db, prospect_id)

        assert "bridge" in prep.loan_types
        assert "fix_and_flip" in prep.loan_types

    def test_includes_pain_points(self, db, prospect_id):
        """Pain points are extracted from intel nuggets."""
        prep = generate_prep(db, prospect_id)

        assert prep.pain_points is not None
        assert len(prep.pain_points) == 2
        assert any("underwriting" in p.lower() for p in prep.pain_points)

    def test_includes_competitors(self, db, prospect_id):
        """Competitors are extracted from intel nuggets."""
        prep = generate_prep(db, prospect_id)

        assert prep.competitors is not None
        assert "LendingPad" in prep.competitors
        assert "Encompass" in prep.competitors

    def test_includes_decision_timeline(self, db, prospect_id):
        """Decision timeline is extracted from intel nuggets."""
        prep = generate_prep(db, prospect_id)

        assert prep.decision_timeline is not None
        assert "Q2" in prep.decision_timeline

    def test_includes_key_facts(self, db, prospect_id):
        """Key facts are extracted from intel nuggets."""
        prep = generate_prep(db, prospect_id)

        assert prep.key_facts is not None
        assert any("loan officers" in f.lower() for f in prep.key_facts)

    def test_includes_talking_points(self, db, prospect_id):
        """Talking points are generated from prep data."""
        prep = generate_prep(db, prospect_id)

        assert prep.talking_points is not None
        assert len(prep.talking_points) > 0

    def test_includes_history_summary(self, db, prospect_id):
        """History summary is generated from activities."""
        prep = generate_prep(db, prospect_id)

        assert prep.history_summary is not None
        assert "interaction" in prep.history_summary.lower()

    def test_includes_questions_to_ask(self, db, prospect_id):
        """Questions to ask are generated."""
        prep = generate_prep(db, prospect_id)

        assert prep.questions_to_ask is not None
        assert len(prep.questions_to_ask) > 0


class TestGeneratePrepSparse:
    """Test prep generation with minimal data."""

    def test_generates_prep_with_sparse_data(self, db, sparse_prospect_id):
        """Generates prep even with minimal data."""
        prep = generate_prep(db, sparse_prospect_id)

        assert isinstance(prep, DemoPrep)
        assert prep.prospect_name == "Jane Doe"
        assert prep.loan_types == []
        assert prep.pain_points is None
        assert prep.competitors is None
        assert prep.decision_timeline is None

    def test_sparse_has_generic_talking_points(self, db, sparse_prospect_id):
        """Sparse data generates generic talking points."""
        prep = generate_prep(db, sparse_prospect_id)

        assert prep.talking_points is not None
        assert any("walkthrough" in tp.lower() for tp in prep.talking_points)

    def test_sparse_has_discovery_questions(self, db, sparse_prospect_id):
        """Sparse data generates discovery questions."""
        prep = generate_prep(db, sparse_prospect_id)

        assert prep.questions_to_ask is not None
        # Should ask about loan types since we don't know them
        assert any("loan types" in q.lower() for q in prep.questions_to_ask)

    def test_sparse_history_shows_no_interactions(self, db, sparse_prospect_id):
        """No interactions shows appropriate message."""
        prep = generate_prep(db, sparse_prospect_id)

        assert prep.history_summary is not None
        assert "no prior" in prep.history_summary.lower()


class TestGeneratePrepErrors:
    """Test error handling in prep generation."""

    def test_missing_prospect_raises_error(self, db):
        """Missing prospect raises ValueError."""
        with pytest.raises(ValueError, match="Prospect not found"):
            generate_prep(db, 9999)


# =============================================================================
# PAIN POINT EXTRACTION
# =============================================================================


class TestExtractPainPoints:
    """Test pain point extraction from nuggets."""

    def test_extracts_pain_points(self):
        """Extracts PAIN_POINT nuggets."""
        nuggets = [
            IntelNugget(prospect_id=1, category=IntelCategory.PAIN_POINT, content="Slow process"),
            IntelNugget(prospect_id=1, category=IntelCategory.COMPETITOR, content="CompetitorX"),
            IntelNugget(prospect_id=1, category=IntelCategory.PAIN_POINT, content="Bad reporting"),
        ]
        result = _extract_pain_points(nuggets)
        assert len(result) == 2
        assert "Slow process" in result
        assert "Bad reporting" in result

    def test_empty_nuggets_returns_empty(self):
        """Empty nuggets returns empty list."""
        result = _extract_pain_points([])
        assert result == []

    def test_no_pain_points_returns_empty(self):
        """No PAIN_POINT nuggets returns empty list."""
        nuggets = [
            IntelNugget(prospect_id=1, category=IntelCategory.COMPETITOR, content="CompetitorX"),
        ]
        result = _extract_pain_points(nuggets)
        assert result == []


# =============================================================================
# COMPETITOR EXTRACTION
# =============================================================================


class TestExtractCompetitors:
    """Test competitor extraction from nuggets."""

    def test_extracts_competitors(self):
        """Extracts COMPETITOR nuggets."""
        nuggets = [
            IntelNugget(prospect_id=1, category=IntelCategory.COMPETITOR, content="LendingPad"),
            IntelNugget(prospect_id=1, category=IntelCategory.PAIN_POINT, content="Slow process"),
            IntelNugget(prospect_id=1, category=IntelCategory.COMPETITOR, content="Encompass"),
        ]
        result = _extract_competitors(nuggets)
        assert len(result) == 2
        assert "LendingPad" in result
        assert "Encompass" in result

    def test_deduplicates_competitors(self):
        """Duplicate competitors are deduplicated (case-insensitive)."""
        nuggets = [
            IntelNugget(prospect_id=1, category=IntelCategory.COMPETITOR, content="LendingPad"),
            IntelNugget(prospect_id=1, category=IntelCategory.COMPETITOR, content="lendingpad"),
            IntelNugget(prospect_id=1, category=IntelCategory.COMPETITOR, content="Encompass"),
        ]
        result = _extract_competitors(nuggets)
        assert len(result) == 2

    def test_empty_nuggets_returns_empty(self):
        """Empty nuggets returns empty list."""
        result = _extract_competitors([])
        assert result == []


# =============================================================================
# TALKING POINTS
# =============================================================================


class TestGenerateTalkingPoints:
    """Test talking point generation."""

    def test_generates_loan_type_points(self):
        """Loan types generate talking points."""
        prep = DemoPrep(
            prospect_name="Test",
            company_name="Test Co",
            loan_types=["bridge", "fix_and_flip"],
        )
        points = _generate_talking_points(prep)
        assert any("bridge" in p.lower() for p in points)

    def test_generates_pain_point_points(self):
        """Pain points generate talking points."""
        prep = DemoPrep(
            prospect_name="Test",
            company_name="Test Co",
            loan_types=[],
            pain_points=["Slow process"],
        )
        points = _generate_talking_points(prep)
        assert any("slow process" in p.lower() for p in points)

    def test_generates_competitor_points(self):
        """Competitors generate talking points."""
        prep = DemoPrep(
            prospect_name="Test",
            company_name="Test Co",
            loan_types=[],
            competitors=["LendingPad"],
        )
        points = _generate_talking_points(prep)
        assert any("lendingpad" in p.lower() for p in points)

    def test_empty_data_generates_generic_points(self):
        """Empty data generates generic talking points."""
        prep = DemoPrep(
            prospect_name="Test",
            company_name="Test Co",
            loan_types=[],
        )
        points = _generate_talking_points(prep)
        assert len(points) > 0
        assert any("walkthrough" in p.lower() for p in points)


# =============================================================================
# HISTORY SUMMARIZATION
# =============================================================================


class TestSummarizeHistory:
    """Test interaction history summarization."""

    def test_summarizes_activities(self):
        """Summarizes activity list."""
        activities = [
            Activity(
                prospect_id=1,
                activity_type=ActivityType.CALL,
                notes="Left voicemail",
            ),
            Activity(
                prospect_id=1,
                activity_type=ActivityType.EMAIL_SENT,
                notes="Sent intro email",
            ),
        ]
        summary = _summarize_history(activities)
        assert "2 total interactions" in summary

    def test_includes_activity_type_counts(self):
        """Summary includes counts by activity type."""
        activities = [
            Activity(prospect_id=1, activity_type=ActivityType.CALL, notes="Call 1"),
            Activity(prospect_id=1, activity_type=ActivityType.CALL, notes="Call 2"),
            Activity(prospect_id=1, activity_type=ActivityType.EMAIL_SENT, notes="Email"),
        ]
        summary = _summarize_history(activities)
        assert "2 call" in summary
        assert "1 email_sent" in summary

    def test_includes_most_recent_note(self):
        """Summary includes the most recent activity note."""
        activities = [
            Activity(
                prospect_id=1,
                activity_type=ActivityType.CALL,
                notes="Discussed pricing options",
            ),
            Activity(
                prospect_id=1,
                activity_type=ActivityType.EMAIL_SENT,
                notes="Old email",
            ),
        ]
        summary = _summarize_history(activities)
        assert "Discussed pricing options" in summary

    def test_empty_activities_returns_no_history(self):
        """Empty activity list returns no history message."""
        summary = _summarize_history([])
        assert "no prior" in summary.lower()

    def test_single_activity(self):
        """Single activity summary is correct."""
        activities = [
            Activity(
                prospect_id=1,
                activity_type=ActivityType.NOTE,
                notes="Initial contact note",
            ),
        ]
        summary = _summarize_history(activities)
        assert "1 total interaction" in summary
        assert "interactions" not in summary  # singular
