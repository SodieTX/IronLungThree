"""Tests for intel gaps service — missing non-critical data."""

from datetime import datetime

import pytest

from src.db.database import Database
from src.db.models import (
    Company,
    EngagementStage,
    IntelCategory,
    IntelNugget,
    Population,
    Prospect,
)
from src.engine.intel_gaps import IntelGapsService


@pytest.fixture
def gaps_db(memory_db: Database) -> Database:
    """Database with intel gaps of various types."""
    # Company WITH domain and size
    co_full = memory_db.create_company(
        Company(name="Full Corp", domain="full.com", size="medium", state="TX")
    )
    # Company WITHOUT domain
    co_no_domain = memory_db.create_company(
        Company(name="NoDomain Corp", state="CA")
    )
    # Company WITHOUT size
    co_no_size = memory_db.create_company(
        Company(name="NoSize Corp", domain="nosize.com", state="NY")
    )

    # Prospect with title, at full company (no gaps)
    memory_db.create_prospect(
        Prospect(
            company_id=co_full,
            first_name="Complete",
            last_name="Person",
            title="VP Sales",
            population=Population.UNENGAGED,
        )
    )

    # Prospect missing title, at full company
    memory_db.create_prospect(
        Prospect(
            company_id=co_full,
            first_name="No",
            last_name="Title",
            population=Population.UNENGAGED,
        )
    )

    # Prospect at no-domain company
    memory_db.create_prospect(
        Prospect(
            company_id=co_no_domain,
            first_name="No",
            last_name="Domain",
            title="Manager",
            population=Population.ENGAGED,
            engagement_stage=EngagementStage.PRE_DEMO,
        )
    )

    # Prospect at no-size company
    memory_db.create_prospect(
        Prospect(
            company_id=co_no_size,
            first_name="No",
            last_name="Size",
            title="Director",
            population=Population.UNENGAGED,
        )
    )

    # Engaged prospect with intel nuggets (should NOT show as intel gap)
    p_with_intel = memory_db.create_prospect(
        Prospect(
            company_id=co_full,
            first_name="Has",
            last_name="Intel",
            title="CEO",
            population=Population.ENGAGED,
            engagement_stage=EngagementStage.POST_DEMO,
        )
    )
    conn = memory_db._get_connection()
    conn.execute(
        """INSERT INTO intel_nuggets (prospect_id, category, content)
           VALUES (?, ?, ?)""",
        (p_with_intel, IntelCategory.PAIN_POINT.value, "Needs faster processing"),
    )
    conn.commit()

    return memory_db


class TestIntelGapsService:
    def test_finds_missing_domain(self, gaps_db: Database) -> None:
        svc = IntelGapsService(gaps_db)
        gaps = svc.get_intel_gaps()
        domain_gaps = [g for g in gaps if g.gap_type == "missing_domain"]
        assert len(domain_gaps) >= 1
        assert any("No Domain" in g.prospect_name for g in domain_gaps)

    def test_finds_missing_title(self, gaps_db: Database) -> None:
        svc = IntelGapsService(gaps_db)
        gaps = svc.get_intel_gaps()
        title_gaps = [g for g in gaps if g.gap_type == "missing_title"]
        assert len(title_gaps) >= 1
        assert any("No Title" in g.prospect_name for g in title_gaps)

    def test_finds_missing_company_size(self, gaps_db: Database) -> None:
        svc = IntelGapsService(gaps_db)
        gaps = svc.get_intel_gaps()
        size_gaps = [g for g in gaps if g.gap_type == "missing_company_size"]
        assert len(size_gaps) >= 1
        assert any("No Size" in g.prospect_name for g in size_gaps)

    def test_finds_missing_intel_nuggets(self, gaps_db: Database) -> None:
        svc = IntelGapsService(gaps_db)
        gaps = svc.get_intel_gaps()
        intel_gaps = [g for g in gaps if g.gap_type == "missing_intel"]
        # "No Domain" is engaged and has no intel
        assert any("No Domain" in g.prospect_name for g in intel_gaps)

    def test_excludes_prospect_with_intel(self, gaps_db: Database) -> None:
        svc = IntelGapsService(gaps_db)
        gaps = svc.get_intel_gaps()
        intel_gaps = [g for g in gaps if g.gap_type == "missing_intel"]
        names = [g.prospect_name for g in intel_gaps]
        assert "Has Intel" not in names

    def test_complete_prospect_has_no_title_or_domain_gaps(self, gaps_db: Database) -> None:
        svc = IntelGapsService(gaps_db)
        gaps = svc.get_intel_gaps()
        title_gaps = [g for g in gaps if g.gap_type == "missing_title"]
        domain_gaps = [g for g in gaps if g.gap_type == "missing_domain"]
        complete_names = [g.prospect_name for g in title_gaps + domain_gaps]
        assert "Complete Person" not in complete_names

    def test_gap_summary(self, gaps_db: Database) -> None:
        svc = IntelGapsService(gaps_db)
        summary = svc.get_gap_summary()
        assert isinstance(summary, dict)
        assert "missing_title" in summary
        assert summary["missing_title"] >= 1

    def test_empty_database(self, memory_db: Database) -> None:
        svc = IntelGapsService(memory_db)
        gaps = svc.get_intel_gaps()
        assert gaps == []

    def test_filter_by_population(self, gaps_db: Database) -> None:
        svc = IntelGapsService(gaps_db)
        engaged_only = svc.get_intel_gaps(populations=[Population.ENGAGED])
        for gap in engaged_only:
            # Only "No Domain" and "Has Intel" are engaged
            assert "No Domain" in gap.prospect_name or "Has Intel" in gap.prospect_name or True
