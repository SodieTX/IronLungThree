"""Tests for the learning engine (Phase 7, Step 7.5)."""

from datetime import date, datetime, timedelta

import pytest

from src.db.database import Database
from src.db.models import (
    Activity,
    ActivityType,
    Company,
    IntelCategory,
    IntelNugget,
    LostReason,
    Population,
    Prospect,
)
from src.engine.learning import (
    LearningEngine,
    LearningInsights,
    LossPattern,
    WinPattern,
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
    company = Company(name="Test Corp", state="TX")
    return db.create_company(company)


class TestAnalyzeOutcomes:
    """Tests for outcome analysis."""

    def test_empty_db(self, db):
        """Empty database returns empty insights."""
        engine = LearningEngine(db)
        insights = engine.analyze_outcomes()
        assert isinstance(insights, LearningInsights)
        assert len(insights.win_patterns) == 0
        assert len(insights.loss_patterns) == 0
        assert insights.win_rate is None
        assert insights.avg_cycle_days is None

    def test_win_patterns_from_close_notes(self, db, company_id):
        """Extracts win patterns from close_notes."""
        prospect = Prospect(
            company_id=company_id,
            first_name="Won",
            last_name="Deal",
            population=Population.CLOSED_WON,
            close_notes="They loved the borrower portal and automation",
            close_date=date.today(),
            created_at=datetime.now() - timedelta(days=30),
        )
        db.create_prospect(prospect)

        engine = LearningEngine(db)
        insights = engine.analyze_outcomes()
        assert len(insights.win_patterns) >= 1
        pattern_descs = [p.pattern for p in insights.win_patterns]
        assert any("portal" in d.lower() or "automation" in d.lower() for d in pattern_descs)

    def test_loss_patterns_from_notes(self, db, company_id):
        """Extracts loss patterns from lost deal notes."""
        prospect = Prospect(
            company_id=company_id,
            first_name="Lost",
            last_name="Deal",
            population=Population.LOST,
            lost_reason=LostReason.LOST_TO_COMPETITOR,
            lost_competitor="LoanPro",
            notes="They said pricing was too high and went with LoanPro",
        )
        db.create_prospect(prospect)

        engine = LearningEngine(db)
        insights = engine.analyze_outcomes()
        assert len(insights.loss_patterns) >= 1
        assert len(insights.top_competitors) >= 1

    def test_win_rate_calculation(self, db, company_id):
        """Win rate is calculated correctly."""
        # 2 wins
        for i in range(2):
            db.create_prospect(
                Prospect(
                    company_id=company_id,
                    first_name=f"Winner{i}",
                    last_name="Deal",
                    population=Population.CLOSED_WON,
                    close_notes="Great demo",
                )
            )
        # 1 loss
        db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Loser",
                last_name="Deal",
                population=Population.LOST,
                lost_reason=LostReason.BUDGET,
                notes="Budget issue",
            )
        )

        engine = LearningEngine(db)
        insights = engine.analyze_outcomes()
        assert insights.win_rate is not None
        assert abs(insights.win_rate - 2 / 3) < 0.01

    def test_avg_cycle_days(self, db, company_id):
        """Average cycle days calculated from won deals."""
        pid = db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Quick",
                last_name="Close",
                population=Population.CLOSED_WON,
                close_date=date.today(),
            )
        )
        # Backdate created_at via SQL so cycle = ~45 days
        old_date = (datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d %H:%M:%S")
        conn = db._get_connection()
        conn.execute("UPDATE prospects SET created_at = ? WHERE id = ?", (old_date, pid))
        conn.commit()

        engine = LearningEngine(db)
        insights = engine.analyze_outcomes()
        assert insights.avg_cycle_days is not None
        assert insights.avg_cycle_days >= 40

    def test_competitor_mentions(self, db, company_id):
        """Detects known competitor mentions."""
        db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Lost1",
                last_name="Deal",
                population=Population.LOST,
                lost_competitor="Encompass",
                notes="They went with Encompass because of their existing setup",
            )
        )
        db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Lost2",
                last_name="Deal",
                population=Population.LOST,
                lost_competitor="Encompass",
                notes="Another loss to encompass",
            )
        )

        engine = LearningEngine(db)
        insights = engine.analyze_outcomes()
        assert len(insights.top_competitors) >= 1
        comp_names = [c[0] for c in insights.top_competitors]
        assert "encompass" in comp_names

    def test_activity_notes_included(self, db, company_id):
        """Activity notes are incorporated into pattern analysis."""
        pid = db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Won",
                last_name="WithNotes",
                population=Population.CLOSED_WON,
            )
        )
        db.create_activity(
            Activity(
                prospect_id=pid,
                activity_type=ActivityType.NOTE,
                notes="The referral from our existing client was key to this deal",
            )
        )

        engine = LearningEngine(db)
        insights = engine.analyze_outcomes()
        pattern_descs = [p.pattern for p in insights.win_patterns]
        assert any("referral" in d.lower() for d in pattern_descs)


class TestGetSuggestionsForProspect:
    """Tests for prospect-specific suggestions."""

    def test_no_data_returns_empty(self, db, company_id):
        """Nonexistent prospect returns empty suggestions."""
        engine = LearningEngine(db)
        suggestions = engine.get_suggestions_for_prospect(999)
        assert suggestions == []

    def test_returns_suggestions_with_data(self, db, company_id):
        """Returns suggestions when there's historical data."""
        # Create won deal with pattern
        db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Won",
                last_name="Deal",
                population=Population.CLOSED_WON,
                close_notes="The demo was incredible",
            )
        )
        # Create the target prospect
        pid = db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Target",
                last_name="Prospect",
                population=Population.UNENGAGED,
            )
        )

        engine = LearningEngine(db)
        suggestions = engine.get_suggestions_for_prospect(pid)
        assert len(suggestions) >= 1

    def test_competitor_intel_in_suggestions(self, db, company_id):
        """Competitor intel nuggets generate suggestions."""
        pid = db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Target",
                last_name="WithIntel",
                population=Population.ENGAGED,
            )
        )
        db.create_intel_nugget(
            IntelNugget(
                prospect_id=pid,
                category=IntelCategory.COMPETITOR,
                content="Currently evaluating LoanPro",
            )
        )

        # Need at least one closed deal for patterns
        db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Won",
                last_name="One",
                population=Population.CLOSED_WON,
                close_notes="Great portal demo",
            )
        )

        engine = LearningEngine(db)
        suggestions = engine.get_suggestions_for_prospect(pid)
        intel_suggestions = [s for s in suggestions if "intel" in s.lower() or "competitor" in s.lower()]
        assert len(intel_suggestions) >= 1


class TestPatternExtraction:
    """Tests for internal pattern extraction methods."""

    def test_extract_win_patterns_empty(self, db):
        engine = LearningEngine(db)
        patterns = engine._extract_win_patterns([])
        assert patterns == []

    def test_extract_win_patterns_deduplicates(self, db):
        """Same keyword in one note only counts once."""
        engine = LearningEngine(db)
        patterns = engine._extract_win_patterns(
            ["Great portal, amazing portal, loved the portal"]
        )
        portal_patterns = [p for p in patterns if "portal" in p.pattern.lower()]
        # Should only count once per note
        for p in portal_patterns:
            assert p.count == 1

    def test_extract_loss_patterns_with_competitors(self, db):
        """Loss patterns track associated competitors."""
        engine = LearningEngine(db)
        patterns = engine._extract_loss_patterns(
            ["Lost on price, they went with loanpro because it was cheaper"]
        )
        assert len(patterns) >= 1
        price_patterns = [p for p in patterns if "pricing" in p.pattern.lower() or "cost" in p.pattern.lower()]
        assert len(price_patterns) >= 1

    def test_find_competitor_mentions(self, db):
        """Finds known competitor names in notes."""
        engine = LearningEngine(db)
        mentions = engine._find_competitor_mentions(
            ["Lost to encompass", "They use calyx point", "loanpro was cheaper"]
        )
        assert len(mentions) >= 3
