"""Tests for morning brief generation.

Tests Step 2.7: Morning Brief
    - Generates from seeded data
    - Includes pipeline summary with correct counts
    - Includes today's work queue info
    - Detects overdue and orphaned engaged
    - Generates warnings appropriately
    - Performance: < 2 seconds on 200 records
"""

from datetime import datetime, timedelta

import pytest

from src.content.morning_brief import MorningBrief, generate_morning_brief
from src.db.database import Database
from src.db.models import Company, EngagementStage, Population, Prospect


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
def seeded_db(db, company_id):
    """Database seeded with various prospects."""
    # 3 unengaged
    for i in range(3):
        db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name=f"Unengaged{i}",
                last_name="Test",
                population=Population.UNENGAGED,
                prospect_score=50 + i,
            )
        )

    # 2 engaged with follow-up today
    today = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    for i in range(2):
        db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name=f"EngagedToday{i}",
                last_name="Test",
                population=Population.ENGAGED,
                engagement_stage=EngagementStage.PRE_DEMO,
                follow_up_date=today,
            )
        )

    # 1 engaged orphan (no follow-up date)
    db.create_prospect(
        Prospect(
            company_id=company_id,
            first_name="Orphan",
            last_name="Test",
            population=Population.ENGAGED,
            engagement_stage=EngagementStage.POST_DEMO,
        )
    )

    # 1 overdue
    db.create_prospect(
        Prospect(
            company_id=company_id,
            first_name="Overdue",
            last_name="Test",
            population=Population.ENGAGED,
            follow_up_date=datetime.now() - timedelta(days=3),
        )
    )

    # 2 broken
    for i in range(2):
        db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name=f"Broken{i}",
                last_name="Test",
                population=Population.BROKEN,
            )
        )

    # 1 DNC
    db.create_prospect(
        Prospect(
            company_id=company_id,
            first_name="DNC",
            last_name="Test",
            population=Population.DEAD_DNC,
        )
    )

    return db


class TestMorningBrief:
    """Test morning brief generation."""

    def test_generates_brief(self, seeded_db):
        """Generates a morning brief."""
        brief = generate_morning_brief(seeded_db)
        assert isinstance(brief, MorningBrief)
        assert brief.date is not None
        assert len(brief.date) > 0

    def test_brief_includes_pipeline_summary(self, seeded_db):
        """Brief includes pipeline summary."""
        brief = generate_morning_brief(seeded_db)
        assert brief.pipeline_summary != ""
        assert "Total prospects" in brief.pipeline_summary

    def test_brief_has_correct_total(self, seeded_db):
        """Brief total matches actual prospect count."""
        brief = generate_morning_brief(seeded_db)
        # 3 unengaged + 2 engaged today + 1 orphan + 1 overdue + 2 broken + 1 DNC = 10
        assert brief.total_prospects == 10

    def test_brief_population_counts(self, seeded_db):
        """Population counts are correct."""
        brief = generate_morning_brief(seeded_db)
        assert brief.population_counts["unengaged"] == 3
        assert brief.population_counts["broken"] == 2
        assert brief.population_counts["dead_dnc"] == 1

    def test_brief_detects_overdue(self, seeded_db):
        """Brief detects overdue follow-ups."""
        brief = generate_morning_brief(seeded_db)
        assert brief.overdue_count >= 1
        assert "OVERDUE" in brief.todays_work

    def test_brief_detects_orphans(self, seeded_db):
        """Brief detects orphaned engaged prospects."""
        brief = generate_morning_brief(seeded_db)
        assert brief.orphan_count >= 1
        assert len(brief.warnings) >= 1

    def test_brief_includes_unengaged_count(self, seeded_db):
        """Brief mentions unengaged queue size."""
        brief = generate_morning_brief(seeded_db)
        assert brief.unengaged_queue_size == 3

    def test_brief_has_full_text(self, seeded_db):
        """Brief has composed full text."""
        brief = generate_morning_brief(seeded_db)
        assert "IRONLUNG 3" in brief.full_text
        assert "MORNING BRIEF" in brief.full_text
        assert "PIPELINE" in brief.full_text
        assert "TODAY'S WORK" in brief.full_text

    def test_empty_database_brief(self, db):
        """Brief works with empty database."""
        brief = generate_morning_brief(db)
        assert isinstance(brief, MorningBrief)
        assert brief.total_prospects == 0
        assert "Queue is clear" in brief.full_text

    def test_brief_performance(self, db):
        """Brief generates in < 2 seconds with 200 records."""
        import time

        company_id = db.create_company(Company(name="Perf Corp", state="TX"))
        for i in range(200):
            db.create_prospect(
                Prospect(
                    company_id=company_id,
                    first_name=f"Prospect{i}",
                    last_name="Perf",
                    population=Population.UNENGAGED,
                    prospect_score=i % 100,
                )
            )

        start = time.time()
        brief = generate_morning_brief(db)
        elapsed = time.time() - start

        assert brief.total_prospects == 200
        assert elapsed < 2.0
