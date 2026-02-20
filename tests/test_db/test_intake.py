"""Tests for import intake funnel."""

import pytest

from src.db.database import Database
from src.db.intake import AnalysisResult, ImportPreview, ImportRecord, ImportResult, IntakeFunnel
from src.db.models import (
    Activity,
    ActivityType,
    Company,
    ContactMethod,
    ContactMethodType,
    Population,
    Prospect,
)

# =========================================================================
# HELPERS
# =========================================================================


def _setup_existing_prospect(
    db: Database,
    first_name: str = "John",
    last_name: str = "Doe",
    company_name: str = "Acme Corp",
    email: str | None = "john@acme.com",
    phone: str | None = "7135551234",
    population: Population = Population.UNENGAGED,
) -> int:
    """Insert a company + prospect + contact methods, return prospect_id."""
    company = Company(name=company_name, state="TX")
    company_id = db.create_company(company)

    prospect = Prospect(
        company_id=company_id,
        first_name=first_name,
        last_name=last_name,
        population=population,
    )
    prospect_id = db.create_prospect(prospect)

    if email:
        db.create_contact_method(
            ContactMethod(
                prospect_id=prospect_id,
                type=ContactMethodType.EMAIL,
                value=email.lower(),
                is_primary=True,
            )
        )
    if phone:
        db.create_contact_method(
            ContactMethod(
                prospect_id=prospect_id,
                type=ContactMethodType.PHONE,
                value=phone,
            )
        )

    return prospect_id


# =========================================================================
# INTAKE FUNNEL TESTS
# =========================================================================


class TestAnalyzeNewRecords:
    """Test that new records are correctly identified."""

    def test_single_new_record(self, memory_db):
        """A record with no match is classified as new."""
        funnel = IntakeFunnel(memory_db)
        records = [
            ImportRecord(
                first_name="Alice",
                last_name="Wonder",
                email="alice@wonder.com",
                phone="5551234567",
                company_name="WonderCo",
            )
        ]
        preview = funnel.analyze(records, source_name="test")
        assert len(preview.new_records) == 1
        assert preview.new_records[0].status == "new"

    def test_multiple_new_records(self, memory_db):
        """Multiple unmatched records all classified as new."""
        funnel = IntakeFunnel(memory_db)
        records = [
            ImportRecord(first_name="Alice", last_name="A", email="a@a.com"),
            ImportRecord(first_name="Bob", last_name="B", email="b@b.com"),
            ImportRecord(first_name="Carol", last_name="C", email="c@c.com"),
        ]
        preview = funnel.analyze(records, source_name="test")
        assert len(preview.new_records) == 3
        assert preview.total_records == 3

    def test_preview_metadata(self, memory_db):
        """Preview carries source_name and filename."""
        funnel = IntakeFunnel(memory_db)
        records = [ImportRecord(first_name="X", last_name="Y")]
        preview = funnel.analyze(records, source_name="LinkedIn", filename="leads.csv")
        assert preview.source_name == "LinkedIn"
        assert preview.filename == "leads.csv"
        assert preview.can_import is True


class TestAnalyzeDuplicateDetection:
    """Test three-pass deduplication."""

    def test_email_exact_match(self, memory_db):
        """Pass 1: Exact email match → merge."""
        _setup_existing_prospect(memory_db, email="john@acme.com")
        funnel = IntakeFunnel(memory_db)
        records = [
            ImportRecord(
                first_name="Johnny",
                last_name="Doe",
                email="john@acme.com",
                company_name="Acme Corp",
            )
        ]
        preview = funnel.analyze(records)
        assert len(preview.merge_records) == 1
        assert preview.merge_records[0].match_reason == "email"
        assert preview.merge_records[0].match_confidence == 1.0

    def test_email_match_case_insensitive(self, memory_db):
        """Email match is case-insensitive (db stores lowercase)."""
        _setup_existing_prospect(memory_db, email="john@acme.com")
        funnel = IntakeFunnel(memory_db)
        records = [
            ImportRecord(
                first_name="John",
                last_name="Doe",
                email="JOHN@ACME.COM",
                company_name="Acme Corp",
            )
        ]
        preview = funnel.analyze(records)
        assert len(preview.merge_records) == 1
        assert preview.merge_records[0].match_reason == "email"

    def test_fuzzy_name_company_match(self, memory_db):
        """Pass 2: Fuzzy name + same company → merge."""
        _setup_existing_prospect(
            memory_db,
            first_name="Jonathan",
            last_name="Doe",
            company_name="Acme Corp",
            email="jon@acme.com",
        )
        funnel = IntakeFunnel(memory_db)
        # Very similar name, same company
        records = [
            ImportRecord(
                first_name="Jonathon",
                last_name="Doe",
                email="newjohn@other.com",
                company_name="Acme Corp, LLC",
            )
        ]
        preview = funnel.analyze(records)
        assert len(preview.merge_records) == 1
        assert preview.merge_records[0].match_reason == "fuzzy_name"
        assert preview.merge_records[0].match_confidence >= 0.85

    def test_fuzzy_match_below_threshold_is_new(self, memory_db):
        """Names too different don't match even in same company."""
        _setup_existing_prospect(
            memory_db,
            first_name="John",
            last_name="Doe",
            company_name="Acme Corp",
        )
        funnel = IntakeFunnel(memory_db)
        records = [
            ImportRecord(
                first_name="Xavier",
                last_name="Smith",
                email="x@other.com",
                company_name="Acme Corp",
            )
        ]
        preview = funnel.analyze(records)
        assert len(preview.new_records) == 1
        assert len(preview.merge_records) == 0

    def test_phone_match_needs_review(self, memory_db):
        """Pass 3: Phone match → needs_review (not auto-merge)."""
        _setup_existing_prospect(memory_db, phone="7135551234", email="old@acme.com")
        funnel = IntakeFunnel(memory_db)
        records = [
            ImportRecord(
                first_name="Completely",
                last_name="Different",
                phone="7135551234",
                company_name="Other Corp",
            )
        ]
        preview = funnel.analyze(records)
        assert len(preview.needs_review) == 1
        assert preview.needs_review[0].match_reason == "phone"

    def test_email_match_takes_priority_over_phone(self, memory_db):
        """Email match fires before phone match."""
        _setup_existing_prospect(memory_db, email="john@acme.com", phone="7135551234")
        funnel = IntakeFunnel(memory_db)
        records = [
            ImportRecord(
                first_name="John",
                last_name="Doe",
                email="john@acme.com",
                phone="7135551234",
                company_name="Acme",
            )
        ]
        preview = funnel.analyze(records)
        # Should be merge via email, not needs_review via phone
        assert len(preview.merge_records) == 1
        assert preview.merge_records[0].match_reason == "email"
        assert len(preview.needs_review) == 0


class TestDNCBlocking:
    """DNC is sacred - checked BEFORE dedup."""

    def test_dnc_email_blocked(self, memory_db):
        """Record matching DNC email is blocked."""
        _setup_existing_prospect(
            memory_db,
            email="dead@blocked.com",
            phone="9999999999",
            population=Population.DEAD_DNC,
        )
        funnel = IntakeFunnel(memory_db)
        records = [
            ImportRecord(
                first_name="Ghost",
                last_name="Person",
                email="dead@blocked.com",
                company_name="Ghost Inc",
            )
        ]
        preview = funnel.analyze(records)
        assert len(preview.blocked_dnc) == 1
        assert preview.blocked_dnc[0].status == "blocked_dnc"
        assert len(preview.merge_records) == 0

    def test_dnc_phone_blocked(self, memory_db):
        """Record matching DNC phone is blocked."""
        _setup_existing_prospect(
            memory_db,
            phone="5550001111",
            email="dead@phone.com",
            population=Population.DEAD_DNC,
        )
        funnel = IntakeFunnel(memory_db)
        records = [
            ImportRecord(
                first_name="Ghost",
                last_name="Person",
                phone="5550001111",
                company_name="Ghost Inc",
            )
        ]
        preview = funnel.analyze(records)
        assert len(preview.blocked_dnc) == 1
        assert len(preview.new_records) == 0

    def test_dnc_checked_before_dedup(self, memory_db):
        """DNC blocks even if email would match for merge."""
        _setup_existing_prospect(
            memory_db,
            email="john@dnc.com",
            population=Population.DEAD_DNC,
        )
        funnel = IntakeFunnel(memory_db)
        records = [
            ImportRecord(
                first_name="John",
                last_name="Doe",
                email="john@dnc.com",
                company_name="Test",
            )
        ]
        preview = funnel.analyze(records)
        # Should be blocked, NOT merged
        assert len(preview.blocked_dnc) == 1
        assert len(preview.merge_records) == 0

    def test_non_dnc_same_email_merges_normally(self, memory_db):
        """Non-DNC prospect with matching email merges normally."""
        _setup_existing_prospect(
            memory_db,
            email="alive@acme.com",
            population=Population.UNENGAGED,
        )
        funnel = IntakeFunnel(memory_db)
        records = [
            ImportRecord(
                first_name="Alive",
                last_name="Person",
                email="alive@acme.com",
            )
        ]
        preview = funnel.analyze(records)
        assert len(preview.merge_records) == 1
        assert len(preview.blocked_dnc) == 0


class TestIncompleteRecords:
    """Records missing required data."""

    def test_no_name_is_incomplete(self, memory_db):
        """Record with no first or last name → incomplete."""
        funnel = IntakeFunnel(memory_db)
        records = [ImportRecord(email="noname@test.com")]
        preview = funnel.analyze(records)
        assert len(preview.incomplete) == 1
        assert preview.incomplete[0].status == "incomplete"

    def test_first_name_only_is_ok(self, memory_db):
        """Record with only first name is not incomplete."""
        funnel = IntakeFunnel(memory_db)
        records = [ImportRecord(first_name="Madonna")]
        preview = funnel.analyze(records)
        assert len(preview.incomplete) == 0
        assert len(preview.new_records) == 1

    def test_last_name_only_is_ok(self, memory_db):
        """Record with only last name is not incomplete."""
        funnel = IntakeFunnel(memory_db)
        records = [ImportRecord(last_name="Smith")]
        preview = funnel.analyze(records)
        assert len(preview.incomplete) == 0
        assert len(preview.new_records) == 1


class TestCommitNewRecords:
    """Test committing new records to database."""

    def test_commit_creates_prospect_and_company(self, memory_db):
        """Commit creates company and prospect in DB."""
        funnel = IntakeFunnel(memory_db)
        records = [
            ImportRecord(
                first_name="Alice",
                last_name="Wonder",
                email="alice@wonder.com",
                phone="5551234567",
                company_name="WonderCo",
            )
        ]
        preview = funnel.analyze(records, source_name="test-import")
        result = funnel.commit(preview)

        assert result.imported_count == 1
        assert result.source_id is not None

        # Verify prospect was created
        prospects = memory_db.get_prospects()
        assert len(prospects) == 1
        assert prospects[0].first_name == "Alice"

    def test_commit_creates_contact_methods(self, memory_db):
        """Commit creates email and phone contact methods."""
        funnel = IntakeFunnel(memory_db)
        records = [
            ImportRecord(
                first_name="Bob",
                last_name="Builder",
                email="bob@build.com",
                phone="5559876543",
                company_name="BuildCo",
            )
        ]
        preview = funnel.analyze(records, source_name="test")
        funnel.commit(preview)

        prospects = memory_db.get_prospects()
        methods = memory_db.get_contact_methods(prospects[0].id)
        emails = [m for m in methods if m.type == ContactMethodType.EMAIL]
        phones = [m for m in methods if m.type == ContactMethodType.PHONE]
        assert len(emails) == 1
        assert emails[0].value == "bob@build.com"
        assert len(phones) == 1
        assert phones[0].value == "5559876543"

    def test_commit_with_email_and_phone_is_unengaged(self, memory_db):
        """Prospect with both email and phone → UNENGAGED."""
        funnel = IntakeFunnel(memory_db)
        records = [
            ImportRecord(
                first_name="Full",
                last_name="Data",
                email="full@data.com",
                phone="5551111111",
                company_name="FullCo",
            )
        ]
        preview = funnel.analyze(records)
        result = funnel.commit(preview)

        assert result.broken_count == 0
        prospects = memory_db.get_prospects()
        assert prospects[0].population == Population.UNENGAGED

    def test_commit_missing_contact_is_broken(self, memory_db):
        """Prospect missing email or phone → BROKEN + research_queue entry."""
        funnel = IntakeFunnel(memory_db)
        records = [
            ImportRecord(
                first_name="No",
                last_name="Phone",
                email="no@phone.com",
                company_name="NoCo",
            )
        ]
        preview = funnel.analyze(records)
        result = funnel.commit(preview)

        assert result.broken_count == 1
        prospects = memory_db.get_prospects()
        assert prospects[0].population == Population.BROKEN

        # Broken records are queued for research
        tasks = memory_db.get_research_tasks()
        assert len(tasks) == 1
        assert tasks[0].prospect_id == prospects[0].id

    def test_commit_complete_record_no_research_task(self, memory_db):
        """Complete record (email + phone) does NOT create research_queue entry."""
        funnel = IntakeFunnel(memory_db)
        records = [
            ImportRecord(
                first_name="Complete",
                last_name="Person",
                email="complete@test.com",
                phone="5551234567",
                company_name="CompleteCo",
            )
        ]
        preview = funnel.analyze(records)
        funnel.commit(preview)

        tasks = memory_db.get_research_tasks()
        assert len(tasks) == 0

    def test_commit_logs_import_activity(self, memory_db):
        """Commit logs an IMPORT activity for each new record."""
        funnel = IntakeFunnel(memory_db)
        records = [
            ImportRecord(
                first_name="Log",
                last_name="Test",
                email="log@test.com",
                phone="5552222222",
                company_name="LogCo",
            )
        ]
        preview = funnel.analyze(records, source_name="CSV Upload")
        funnel.commit(preview)

        prospects = memory_db.get_prospects()
        activities = memory_db.get_activities(prospects[0].id)
        assert len(activities) == 1
        assert activities[0].activity_type == ActivityType.IMPORT
        assert "CSV Upload" in activities[0].notes

    def test_commit_creates_import_source(self, memory_db):
        """Commit creates import_source tracking record."""
        funnel = IntakeFunnel(memory_db)
        records = [
            ImportRecord(first_name="A", last_name="B", email="a@b.com", phone="1111111111"),
            ImportRecord(first_name="C", last_name="D", email="c@d.com", phone="2222222222"),
        ]
        preview = funnel.analyze(records, source_name="Batch Import", filename="batch.csv")
        result = funnel.commit(preview)

        sources = memory_db.get_import_sources()
        assert len(sources) == 1
        assert sources[0].source_name == "Batch Import"
        assert sources[0].imported_records == 2
        assert sources[0].total_records == 2

    def test_commit_unknown_company(self, memory_db):
        """No company_name → creates 'Unknown' company."""
        funnel = IntakeFunnel(memory_db)
        records = [
            ImportRecord(
                first_name="No",
                last_name="Company",
                email="no@company.com",
                phone="5553333333",
            )
        ]
        preview = funnel.analyze(records)
        funnel.commit(preview)

        prospects = memory_db.get_prospects()
        company = memory_db.get_company(prospects[0].company_id)
        assert company.name == "Unknown"


class TestCommitMergeRecords:
    """Test committing merge records."""

    def test_merge_fills_empty_fields(self, memory_db):
        """Merge updates empty title on existing prospect."""
        pid = _setup_existing_prospect(memory_db, email="john@acme.com")

        funnel = IntakeFunnel(memory_db)
        records = [
            ImportRecord(
                first_name="John",
                last_name="Doe",
                email="john@acme.com",
                title="VP Sales",
                company_name="Acme",
            )
        ]
        preview = funnel.analyze(records, source_name="enrich")
        result = funnel.commit(preview)

        assert result.merged_count == 1
        updated = memory_db.get_prospect(pid)
        assert updated.title == "VP Sales"

    def test_merge_does_not_overwrite(self, memory_db):
        """Merge does NOT overwrite existing fields."""
        pid = _setup_existing_prospect(memory_db, email="john@acme.com")
        # Set title on existing
        prospect = memory_db.get_prospect(pid)
        prospect.title = "CTO"
        memory_db.update_prospect(prospect)

        funnel = IntakeFunnel(memory_db)
        records = [
            ImportRecord(
                first_name="John",
                last_name="Doe",
                email="john@acme.com",
                title="VP Sales",
            )
        ]
        preview = funnel.analyze(records)
        funnel.commit(preview)

        updated = memory_db.get_prospect(pid)
        assert updated.title == "CTO"  # unchanged

    def test_merge_adds_new_contact_methods(self, memory_db):
        """Merge adds new email/phone not already on prospect."""
        pid = _setup_existing_prospect(memory_db, email="john@acme.com", phone="7135551234")

        funnel = IntakeFunnel(memory_db)
        records = [
            ImportRecord(
                first_name="John",
                last_name="Doe",
                email="john.doe@personal.com",
                phone="7135551234",
                company_name="Acme",
            )
        ]
        preview = funnel.analyze(records)
        funnel.commit(preview)

        methods = memory_db.get_contact_methods(pid)
        emails = [m.value for m in methods if m.type == ContactMethodType.EMAIL]
        assert "john@acme.com" in emails
        assert "john.doe@personal.com" in emails

    def test_merge_does_not_duplicate_contact_methods(self, memory_db):
        """Merge doesn't add email/phone that already exists."""
        pid = _setup_existing_prospect(memory_db, email="john@acme.com", phone="7135551234")

        funnel = IntakeFunnel(memory_db)
        records = [
            ImportRecord(
                first_name="John",
                last_name="Doe",
                email="john@acme.com",
                phone="7135551234",
            )
        ]
        preview = funnel.analyze(records)
        funnel.commit(preview)

        methods = memory_db.get_contact_methods(pid)
        assert len(methods) == 2  # still just 1 email + 1 phone

    def test_merge_logs_enrichment_activity(self, memory_db):
        """Merge logs ENRICHMENT activity with match reason."""
        _setup_existing_prospect(memory_db, email="john@acme.com")

        funnel = IntakeFunnel(memory_db)
        records = [
            ImportRecord(
                first_name="John",
                last_name="Doe",
                email="john@acme.com",
            )
        ]
        preview = funnel.analyze(records, source_name="enrich-test")
        funnel.commit(preview)

        prospects = memory_db.get_prospects()
        activities = memory_db.get_activities(prospects[0].id)
        enrichment = [a for a in activities if a.activity_type == ActivityType.ENRICHMENT]
        assert len(enrichment) == 1
        assert "email" in enrichment[0].notes


class TestImportPreview:
    """Test ImportPreview properties."""

    def test_total_records(self):
        """total_records sums all categories."""
        preview = ImportPreview()
        preview.new_records = [AnalysisResult(record=ImportRecord())] * 3
        preview.merge_records = [AnalysisResult(record=ImportRecord())] * 2
        preview.blocked_dnc = [AnalysisResult(record=ImportRecord())] * 1
        assert preview.total_records == 6

    def test_can_import_with_new(self):
        """can_import True when there are new records."""
        preview = ImportPreview()
        preview.new_records = [AnalysisResult(record=ImportRecord())]
        assert preview.can_import is True

    def test_can_import_with_merge(self):
        """can_import True when there are merge records."""
        preview = ImportPreview()
        preview.merge_records = [AnalysisResult(record=ImportRecord())]
        assert preview.can_import is True

    def test_cannot_import_only_blocked(self):
        """can_import False when only DNC blocked records."""
        preview = ImportPreview()
        preview.blocked_dnc = [AnalysisResult(record=ImportRecord())]
        assert preview.can_import is False


class TestMixedImport:
    """Test a batch with mixed record types."""

    def test_mixed_batch(self, memory_db):
        """Batch with new, merge, DNC blocked, and incomplete records."""
        # Set up existing prospect
        _setup_existing_prospect(memory_db, email="existing@acme.com")
        # Set up DNC prospect
        _setup_existing_prospect(
            memory_db,
            first_name="Dead",
            last_name="Contact",
            email="dead@blocked.com",
            company_name="Dead Corp",
            population=Population.DEAD_DNC,
        )

        funnel = IntakeFunnel(memory_db)
        records = [
            # New record
            ImportRecord(first_name="New", last_name="Person", email="new@new.com"),
            # Merge (email match)
            ImportRecord(first_name="Existing", last_name="Match", email="existing@acme.com"),
            # DNC blocked
            ImportRecord(first_name="Dead", last_name="Match", email="dead@blocked.com"),
            # Incomplete (no name)
            ImportRecord(email="nameless@test.com"),
        ]
        preview = funnel.analyze(records)

        assert len(preview.new_records) == 1
        assert len(preview.merge_records) == 1
        assert len(preview.blocked_dnc) == 1
        assert len(preview.incomplete) == 1
        assert preview.total_records == 4

        result = funnel.commit(preview)
        assert result.imported_count == 1
        assert result.merged_count == 1


# =========================================================================
# NAME SIMILARITY TESTS
# =========================================================================


class TestNameSimilarity:
    """Test name similarity functions."""

    def test_exact_match(self):
        """Exact names have high similarity."""
        similarity = IntakeFunnel.name_similarity("John Smith", "John Smith")
        assert similarity >= 0.9

    def test_different_names_low_similarity(self):
        """Different names have low similarity."""
        similarity = IntakeFunnel.name_similarity("John Smith", "Jane Doe")
        assert similarity < 0.5

    def test_case_insensitive(self):
        """Similarity is case-insensitive."""
        similarity = IntakeFunnel.name_similarity("JOHN SMITH", "john smith")
        assert similarity == 1.0

    def test_similar_names_high(self):
        """Similar names (typo) have high similarity."""
        similarity = IntakeFunnel.name_similarity("Jonathan Doe", "Jonathon Doe")
        assert similarity >= 0.85


# =========================================================================
# PHONE NORMALIZATION TESTS
# =========================================================================


class TestPhoneNormalization:
    """Test phone normalization."""

    def test_normalize_with_country_code(self):
        """Strips US country code prefix for consistent DNC matching."""
        assert IntakeFunnel.normalize_phone("+1 (303) 555-1234") == "3035551234"

    def test_normalize_various_formats(self):
        """Handles various formats."""
        assert IntakeFunnel.normalize_phone("303-555-1234") == "3035551234"
        assert IntakeFunnel.normalize_phone("303.555.1234") == "3035551234"
        assert IntakeFunnel.normalize_phone("(303) 555-1234") == "3035551234"
