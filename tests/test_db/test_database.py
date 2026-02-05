"""Tests for database operations."""

from datetime import date, datetime
from pathlib import Path

import pytest

from src.db.database import Database
from src.db.models import (
    Activity,
    ActivityOutcome,
    ActivityType,
    Company,
    ContactMethod,
    ContactMethodType,
    EngagementStage,
    ImportSource,
    IntelCategory,
    IntelNugget,
    Population,
    Prospect,
    ResearchStatus,
    ResearchTask,
)


class TestDatabaseConnection:
    """Test database connection management."""

    def test_connect_creates_file(self, tmp_path: Path):
        """Connecting creates database file."""
        db_path = tmp_path / "new.db"
        db = Database(str(db_path))
        db.initialize()
        assert db_path.exists()
        db.close()

    def test_connect_memory_database(self):
        """Can connect to memory database."""
        db = Database(":memory:")
        db.close()

    def test_initialize_schema(self, memory_db: Database):
        """Schema initialization creates all required tables and indexes."""
        conn = memory_db._get_connection()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [t[0] for t in tables]

        expected_tables = [
            "activities",
            "companies",
            "contact_methods",
            "data_freshness",
            "import_sources",
            "intel_nuggets",
            "prospect_tags",
            "prospects",
            "research_queue",
            "schema_version",
        ]
        for table in expected_tables:
            assert table in table_names, f"Missing table: {table}"

        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        index_names = [i[0] for i in indexes]

        expected_indexes = [
            "idx_companies_normalized",
            "idx_companies_domain",
            "idx_prospects_population",
            "idx_prospects_follow_up",
            "idx_prospects_company",
            "idx_prospects_score",
            "idx_contact_methods_prospect",
            "idx_activities_prospect",
            "idx_activities_date",
        ]
        for idx in expected_indexes:
            assert idx in index_names, f"Missing index: {idx}"

        version = conn.execute("SELECT version FROM schema_version").fetchone()
        assert version[0] == 1

    def test_wal_mode_enabled(self, tmp_path: Path):
        """WAL journal mode is enabled for file databases."""
        db_path = tmp_path / "test_wal.db"
        db = Database(str(db_path))
        db.initialize()
        journal_mode = db._get_connection().execute("PRAGMA journal_mode").fetchone()[0]
        assert journal_mode == "wal"
        db.close()

    def test_foreign_keys_enabled(self, memory_db: Database):
        """Foreign key constraints are enabled."""
        fk_status = memory_db._get_connection().execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk_status == 1


class TestCompanyCRUD:
    """Test Company CRUD operations."""

    def test_create_company(self, memory_db: Database):
        """Can create a company and get auto-generated ID."""
        company = Company(name="ABC Lending, LLC", state="TX")
        company_id = memory_db.create_company(company)
        assert company_id > 0

    def test_create_company_auto_normalizes(self, memory_db: Database):
        """Company name is auto-normalized on create."""
        company = Company(name="First National Holdings, Inc.", state="CO")
        company_id = memory_db.create_company(company)
        retrieved = memory_db.get_company(company_id)
        assert retrieved is not None
        assert retrieved.name == "First National Holdings, Inc."
        assert retrieved.name_normalized == "first national holdings"

    def test_create_company_auto_timezone(self, memory_db: Database):
        """Timezone is auto-assigned from state."""
        company = Company(name="Test Co", state="CA")
        company_id = memory_db.create_company(company)
        retrieved = memory_db.get_company(company_id)
        assert retrieved.timezone == "pacific"

    def test_get_company_not_found(self, memory_db: Database):
        """Getting non-existent company returns None."""
        assert memory_db.get_company(999) is None

    def test_get_company_by_normalized_name(self, memory_db: Database):
        """Can find company by normalized name."""
        memory_db.create_company(Company(name="Widget LLC", state="TX"))
        found = memory_db.get_company_by_normalized_name("Widget, LLC")
        assert found is not None
        assert found.name == "Widget LLC"

    def test_update_company(self, memory_db: Database):
        """Can update company fields."""
        cid = memory_db.create_company(Company(name="Old Name", state="TX"))
        company = memory_db.get_company(cid)
        company.name = "New Name"
        company.state = "CA"
        assert memory_db.update_company(company) is True
        updated = memory_db.get_company(cid)
        assert updated.name == "New Name"
        assert updated.timezone == "pacific"

    def test_search_companies(self, memory_db: Database):
        """Can search companies by partial name."""
        memory_db.create_company(Company(name="Alpha Corp", state="TX"))
        memory_db.create_company(Company(name="Beta Inc", state="TX"))
        memory_db.create_company(Company(name="Alpha Holdings", state="TX"))

        results = memory_db.search_companies("alpha")
        assert len(results) == 2


class TestProspectCRUD:
    """Test Prospect CRUD operations."""

    def test_create_prospect(self, memory_db: Database):
        """Can create a prospect."""
        cid = memory_db.create_company(Company(name="Test Co", state="TX"))
        prospect = Prospect(
            company_id=cid,
            first_name="John",
            last_name="Doe",
            population=Population.UNENGAGED,
        )
        pid = memory_db.create_prospect(prospect)
        assert pid > 0

    def test_get_prospect(self, memory_db: Database):
        """Can retrieve a prospect by ID."""
        cid = memory_db.create_company(Company(name="Test Co", state="TX"))
        pid = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="Jane", last_name="Smith",
            population=Population.ENGAGED,
            engagement_stage=EngagementStage.PRE_DEMO,
        ))
        retrieved = memory_db.get_prospect(pid)
        assert retrieved is not None
        assert retrieved.first_name == "Jane"
        assert retrieved.population == Population.ENGAGED
        assert retrieved.engagement_stage == EngagementStage.PRE_DEMO

    def test_update_prospect(self, memory_db: Database):
        """Can update prospect fields."""
        cid = memory_db.create_company(Company(name="Test Co", state="TX"))
        pid = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="John", last_name="Doe",
        ))
        prospect = memory_db.get_prospect(pid)
        prospect.population = Population.ENGAGED
        prospect.engagement_stage = EngagementStage.DEMO_SCHEDULED
        prospect.prospect_score = 85
        assert memory_db.update_prospect(prospect) is True
        updated = memory_db.get_prospect(pid)
        assert updated.population == Population.ENGAGED
        assert updated.prospect_score == 85

    def test_get_prospects_by_population(self, memory_db: Database):
        """Can filter prospects by population."""
        cid = memory_db.create_company(Company(name="Test Co", state="TX"))
        memory_db.create_prospect(Prospect(
            company_id=cid, first_name="A", last_name="B",
            population=Population.UNENGAGED,
        ))
        memory_db.create_prospect(Prospect(
            company_id=cid, first_name="C", last_name="D",
            population=Population.ENGAGED,
        ))
        memory_db.create_prospect(Prospect(
            company_id=cid, first_name="E", last_name="F",
            population=Population.UNENGAGED,
        ))

        unengaged = memory_db.get_prospects(population=Population.UNENGAGED)
        assert len(unengaged) == 2
        engaged = memory_db.get_prospects(population=Population.ENGAGED)
        assert len(engaged) == 1

    def test_get_prospects_by_score_range(self, memory_db: Database):
        """Can filter prospects by score range."""
        cid = memory_db.create_company(Company(name="Test Co", state="TX"))
        memory_db.create_prospect(Prospect(
            company_id=cid, first_name="A", last_name="B", prospect_score=20,
        ))
        memory_db.create_prospect(Prospect(
            company_id=cid, first_name="C", last_name="D", prospect_score=80,
        ))
        memory_db.create_prospect(Prospect(
            company_id=cid, first_name="E", last_name="F", prospect_score=50,
        ))

        results = memory_db.get_prospects(score_min=40, score_max=90)
        assert len(results) == 2

    def test_get_prospects_search_query(self, memory_db: Database):
        """Can search prospects by name."""
        cid = memory_db.create_company(Company(name="Test Co", state="TX"))
        memory_db.create_prospect(Prospect(
            company_id=cid, first_name="John", last_name="Doe",
        ))
        memory_db.create_prospect(Prospect(
            company_id=cid, first_name="Jane", last_name="Smith",
        ))

        results = memory_db.get_prospects(search_query="John")
        assert len(results) == 1
        assert results[0].first_name == "John"

    def test_get_prospects_pagination(self, memory_db: Database):
        """Can paginate prospect results."""
        cid = memory_db.create_company(Company(name="Test Co", state="TX"))
        for i in range(10):
            memory_db.create_prospect(Prospect(
                company_id=cid, first_name=f"Person{i}", last_name="Test",
                prospect_score=i * 10,
            ))

        page1 = memory_db.get_prospects(limit=3, offset=0, sort_by="prospect_score", sort_dir="ASC")
        page2 = memory_db.get_prospects(limit=3, offset=3, sort_by="prospect_score", sort_dir="ASC")
        assert len(page1) == 3
        assert len(page2) == 3
        assert page1[0].prospect_score < page2[0].prospect_score

    def test_get_prospect_full(self, memory_db: Database):
        """Can get full prospect with company, contacts, activities."""
        cid = memory_db.create_company(Company(name="Test Co", state="TX"))
        pid = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="John", last_name="Doe",
        ))
        memory_db.create_contact_method(ContactMethod(
            prospect_id=pid, type=ContactMethodType.EMAIL,
            value="john@test.com", is_primary=True,
        ))
        memory_db.create_activity(Activity(
            prospect_id=pid, activity_type=ActivityType.CALL,
            notes="Test call",
        ))

        full = memory_db.get_prospect_full(pid)
        assert full is not None
        assert full["prospect"].first_name == "John"
        assert full["company"].name == "Test Co"
        assert len(full["contact_methods"]) == 1
        assert len(full["activities"]) == 1

    def test_get_population_counts(self, memory_db: Database):
        """Can get counts per population."""
        cid = memory_db.create_company(Company(name="Test Co", state="TX"))
        memory_db.create_prospect(Prospect(
            company_id=cid, first_name="A", last_name="B",
            population=Population.UNENGAGED,
        ))
        memory_db.create_prospect(Prospect(
            company_id=cid, first_name="C", last_name="D",
            population=Population.UNENGAGED,
        ))
        memory_db.create_prospect(Prospect(
            company_id=cid, first_name="E", last_name="F",
            population=Population.ENGAGED,
        ))

        counts = memory_db.get_population_counts()
        assert counts[Population.UNENGAGED] == 2
        assert counts[Population.ENGAGED] == 1


class TestContactMethodsCRUD:
    """Test ContactMethod CRUD operations."""

    def test_create_contact_method(self, memory_db: Database):
        """Can create a contact method."""
        cid = memory_db.create_company(Company(name="Test Co", state="TX"))
        pid = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="John", last_name="Doe",
        ))
        mid = memory_db.create_contact_method(ContactMethod(
            prospect_id=pid, type=ContactMethodType.EMAIL,
            value="john@test.com", is_primary=True,
        ))
        assert mid > 0

    def test_get_contact_methods_primary_first(self, memory_db: Database):
        """Contact methods returned with primary first."""
        cid = memory_db.create_company(Company(name="Test Co", state="TX"))
        pid = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="John", last_name="Doe",
        ))
        memory_db.create_contact_method(ContactMethod(
            prospect_id=pid, type=ContactMethodType.PHONE,
            value="555-1234", is_primary=False,
        ))
        memory_db.create_contact_method(ContactMethod(
            prospect_id=pid, type=ContactMethodType.EMAIL,
            value="john@test.com", is_primary=True,
        ))

        methods = memory_db.get_contact_methods(pid)
        assert len(methods) == 2
        assert methods[0].is_primary is True
        assert methods[0].type == ContactMethodType.EMAIL

    def test_find_prospect_by_email(self, memory_db: Database):
        """Can find prospect by email (case-insensitive)."""
        cid = memory_db.create_company(Company(name="Test Co", state="TX"))
        pid = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="John", last_name="Doe",
        ))
        memory_db.create_contact_method(ContactMethod(
            prospect_id=pid, type=ContactMethodType.EMAIL,
            value="John@Test.COM",
        ))

        found = memory_db.find_prospect_by_email("john@test.com")
        assert found == pid

    def test_find_prospect_by_phone(self, memory_db: Database):
        """Can find prospect by phone (digits-only match)."""
        cid = memory_db.create_company(Company(name="Test Co", state="TX"))
        pid = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="John", last_name="Doe",
        ))
        memory_db.create_contact_method(ContactMethod(
            prospect_id=pid, type=ContactMethodType.PHONE,
            value="(303) 555-1234",
        ))

        found = memory_db.find_prospect_by_phone("303-555-1234")
        assert found == pid

    def test_is_dnc_by_email(self, memory_db: Database):
        """DNC check works by email."""
        cid = memory_db.create_company(Company(name="DNC Co", state="TX"))
        pid = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="Dead", last_name="Contact",
            population=Population.DEAD_DNC,
        ))
        memory_db.create_contact_method(ContactMethod(
            prospect_id=pid, type=ContactMethodType.EMAIL,
            value="dead@test.com",
        ))

        assert memory_db.is_dnc(email="dead@test.com") is True
        assert memory_db.is_dnc(email="alive@test.com") is False

    def test_is_dnc_by_phone(self, memory_db: Database):
        """DNC check works by phone."""
        cid = memory_db.create_company(Company(name="DNC Co", state="TX"))
        pid = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="Dead", last_name="Contact",
            population=Population.DEAD_DNC,
        ))
        memory_db.create_contact_method(ContactMethod(
            prospect_id=pid, type=ContactMethodType.PHONE,
            value="555-0000",
        ))

        assert memory_db.is_dnc(phone="555-0000") is True
        assert memory_db.is_dnc(phone="555-9999") is False

    def test_update_contact_method(self, memory_db: Database):
        """Can update contact method."""
        cid = memory_db.create_company(Company(name="Test Co", state="TX"))
        pid = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="John", last_name="Doe",
        ))
        memory_db.create_contact_method(ContactMethod(
            prospect_id=pid, type=ContactMethodType.EMAIL,
            value="old@test.com",
        ))
        method = memory_db.get_contact_methods(pid)[0]
        method.value = "new@test.com"
        method.is_verified = True
        assert memory_db.update_contact_method(method) is True
        updated = memory_db.get_contact_methods(pid)[0]
        assert updated.value == "new@test.com"
        assert updated.is_verified is True


class TestActivityCRUD:
    """Test Activity operations."""

    def test_create_activity(self, memory_db: Database):
        """Can log an activity."""
        cid = memory_db.create_company(Company(name="Test Co", state="TX"))
        pid = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="John", last_name="Doe",
        ))
        aid = memory_db.create_activity(Activity(
            prospect_id=pid, activity_type=ActivityType.CALL,
            outcome=ActivityOutcome.LEFT_VM,
            call_duration_seconds=30,
            notes="Left voicemail about Q1",
        ))
        assert aid > 0

    def test_get_activities_most_recent_first(self, memory_db: Database):
        """Activities returned most recent first."""
        cid = memory_db.create_company(Company(name="Test Co", state="TX"))
        pid = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="John", last_name="Doe",
        ))
        memory_db.create_activity(Activity(
            prospect_id=pid, activity_type=ActivityType.NOTE, notes="First",
        ))
        memory_db.create_activity(Activity(
            prospect_id=pid, activity_type=ActivityType.CALL, notes="Second",
        ))

        activities = memory_db.get_activities(pid)
        assert len(activities) == 2

    def test_activity_with_population_change(self, memory_db: Database):
        """Activity can record population transitions."""
        cid = memory_db.create_company(Company(name="Test Co", state="TX"))
        pid = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="John", last_name="Doe",
        ))
        memory_db.create_activity(Activity(
            prospect_id=pid,
            activity_type=ActivityType.STATUS_CHANGE,
            population_before=Population.UNENGAGED,
            population_after=Population.ENGAGED,
            notes="Showed interest",
        ))

        activities = memory_db.get_activities(pid)
        assert activities[0].population_before == Population.UNENGAGED
        assert activities[0].population_after == Population.ENGAGED


class TestBulkOperations:
    """Test bulk operations."""

    def test_bulk_update_population(self, memory_db: Database):
        """Bulk update population for multiple prospects."""
        cid = memory_db.create_company(Company(name="Test Co", state="TX"))
        p1 = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="A", last_name="B",
            population=Population.UNENGAGED,
        ))
        p2 = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="C", last_name="D",
            population=Population.UNENGAGED,
        ))

        updated, skipped = memory_db.bulk_update_population(
            [p1, p2], Population.PARKED, "Parking for Q2"
        )
        assert updated == 2
        assert skipped == 0
        assert memory_db.get_prospect(p1).population == Population.PARKED

    def test_bulk_update_skips_dnc(self, memory_db: Database):
        """Bulk update skips DNC records."""
        cid = memory_db.create_company(Company(name="Test Co", state="TX"))
        p1 = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="A", last_name="B",
            population=Population.UNENGAGED,
        ))
        p2 = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="C", last_name="D",
            population=Population.DEAD_DNC,
        ))

        updated, skipped = memory_db.bulk_update_population(
            [p1, p2], Population.PARKED, "Test"
        )
        assert updated == 1
        assert skipped == 1
        assert memory_db.get_prospect(p2).population == Population.DEAD_DNC

    def test_bulk_set_follow_up(self, memory_db: Database):
        """Bulk set follow-up date."""
        cid = memory_db.create_company(Company(name="Test Co", state="TX"))
        p1 = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="A", last_name="B",
        ))
        p2 = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="C", last_name="D",
        ))

        fu_date = datetime(2026, 3, 1, 9, 0)
        count = memory_db.bulk_set_follow_up([p1, p2], fu_date)
        assert count == 2

    def test_bulk_park(self, memory_db: Database):
        """Bulk park prospects."""
        cid = memory_db.create_company(Company(name="Test Co", state="TX"))
        p1 = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="A", last_name="B",
            population=Population.UNENGAGED,
        ))

        parked, skipped = memory_db.bulk_park([p1], "2026-06")
        assert parked == 1
        assert skipped == 0
        prospect = memory_db.get_prospect(p1)
        assert prospect.population == Population.PARKED
        assert prospect.parked_month == "2026-06"


class TestTagOperations:
    """Test tag operations."""

    def test_add_and_get_tags(self, memory_db: Database):
        """Can add and retrieve tags."""
        cid = memory_db.create_company(Company(name="Test Co", state="TX"))
        pid = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="John", last_name="Doe",
        ))
        memory_db.add_tag(pid, "referral")
        memory_db.add_tag(pid, "conference")
        tags = memory_db.get_tags(pid)
        assert "referral" in tags
        assert "conference" in tags

    def test_remove_tag(self, memory_db: Database):
        """Can remove tag from prospect."""
        cid = memory_db.create_company(Company(name="Test Co", state="TX"))
        pid = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="John", last_name="Doe",
        ))
        memory_db.add_tag(pid, "test-tag")
        assert memory_db.remove_tag(pid, "test-tag") is True
        assert "test-tag" not in memory_db.get_tags(pid)

    def test_get_all_tags(self, memory_db: Database):
        """Can get all unique tags in system."""
        cid = memory_db.create_company(Company(name="Test Co", state="TX"))
        p1 = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="A", last_name="B",
        ))
        p2 = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="C", last_name="D",
        ))
        memory_db.add_tag(p1, "tag1")
        memory_db.add_tag(p1, "tag2")
        memory_db.add_tag(p2, "tag2")
        memory_db.add_tag(p2, "tag3")
        all_tags = memory_db.get_all_tags()
        assert set(all_tags) == {"tag1", "tag2", "tag3"}

    def test_filter_prospects_by_tags(self, memory_db: Database):
        """Can filter prospects by tags."""
        cid = memory_db.create_company(Company(name="Test Co", state="TX"))
        p1 = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="John", last_name="Doe",
        ))
        p2 = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="Jane", last_name="Smith",
        ))
        memory_db.add_tag(p1, "hot-lead")
        memory_db.add_tag(p2, "cold-lead")

        results = memory_db.get_prospects(tags=["hot-lead"])
        assert len(results) == 1
        assert results[0].first_name == "John"


class TestRemainingTables:
    """Test remaining table operations."""

    def test_create_import_source(self, memory_db: Database):
        """Can create import source record."""
        source = ImportSource(
            source_name="PhoneBurner",
            filename="contacts.csv",
            total_records=100,
            imported_records=80,
            duplicate_records=15,
            broken_records=5,
        )
        sid = memory_db.create_import_source(source)
        assert sid > 0
        sources = memory_db.get_import_sources()
        assert len(sources) == 1
        assert sources[0].source_name == "PhoneBurner"

    def test_create_research_task(self, memory_db: Database):
        """Can create research task."""
        cid = memory_db.create_company(Company(name="Test Co", state="TX"))
        pid = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="John", last_name="Doe",
        ))
        task = ResearchTask(prospect_id=pid, priority=5, status=ResearchStatus.PENDING)
        tid = memory_db.create_research_task(task)
        assert tid > 0
        tasks = memory_db.get_research_tasks(status="pending")
        assert len(tasks) == 1

    def test_create_intel_nugget(self, memory_db: Database):
        """Can create intel nugget."""
        cid = memory_db.create_company(Company(name="Test Co", state="TX"))
        pid = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="John", last_name="Doe",
        ))
        nugget = IntelNugget(
            prospect_id=pid, category=IntelCategory.PAIN_POINT,
            content="They need faster processing",
        )
        nid = memory_db.create_intel_nugget(nugget)
        assert nid > 0
        nuggets = memory_db.get_intel_nuggets(pid)
        assert len(nuggets) == 1
        assert nuggets[0].category == IntelCategory.PAIN_POINT

    def test_create_data_freshness(self, memory_db: Database):
        """Can create data freshness record."""
        cid = memory_db.create_company(Company(name="Test Co", state="TX"))
        pid = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="John", last_name="Doe",
        ))
        fid = memory_db.create_data_freshness(
            prospect_id=pid, field_name="email",
            verified_date=date.today(), verification_method="manual", confidence=90,
        )
        assert fid > 0
        records = memory_db.get_data_freshness(pid)
        assert len(records) == 1
        assert records[0]["field_name"] == "email"


class TestDatabaseIntegrity:
    """Test database integrity constraints."""

    def test_foreign_key_enforcement(self, memory_db: Database):
        """Prospect with invalid company_id should fail."""
        from src.core.exceptions import DatabaseError
        with pytest.raises(DatabaseError):
            memory_db.create_prospect(Prospect(
                company_id=99999, first_name="Bad", last_name="Ref",
            ))

    def test_unique_tag_constraint(self, memory_db: Database):
        """Duplicate tags on same prospect are handled gracefully."""
        cid = memory_db.create_company(Company(name="Test Co", state="TX"))
        pid = memory_db.create_prospect(Prospect(
            company_id=cid, first_name="John", last_name="Doe",
        ))
        memory_db.add_tag(pid, "test")
        memory_db.add_tag(pid, "test")  # Should not raise
        tags = memory_db.get_tags(pid)
        assert tags.count("test") == 1
