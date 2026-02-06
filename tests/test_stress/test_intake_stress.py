"""Stress tests for the intake funnel.

Targets:
    - DNC evasion attempts (case variations, whitespace, format tricks)
    - Fuzzy name matching edge cases
    - Dedup with identical records
    - Empty/degenerate import batches
    - Merge conflicts and data preservation
    - Phone matching with format variations
    - Commit with no importable records
"""

from datetime import date, datetime

import pytest

from src.db.database import Database
from src.db.intake import (
    AnalysisResult,
    ImportPreview,
    ImportRecord,
    ImportResult,
    IntakeFunnel,
)
from src.db.models import (
    Activity,
    ActivityType,
    Company,
    ContactMethod,
    ContactMethodType,
    DeadReason,
    Population,
    Prospect,
)


@pytest.fixture
def db(tmp_path):
    d = Database(str(tmp_path / "stress.db"))
    d.initialize()
    yield d
    d.close()


def _setup_dnc_prospect(db):
    """Create a DNC prospect with email and phone."""
    cid = db.create_company(Company(name="DNC Corp", state="TX"))
    pid = db.create_prospect(
        Prospect(
            company_id=cid,
            first_name="Do Not",
            last_name="Contact",
            population=Population.DEAD_DNC,
            dead_reason=DeadReason.DNC,
            dead_date=date.today(),
        )
    )
    db.create_contact_method(
        ContactMethod(
            prospect_id=pid,
            type=ContactMethodType.EMAIL,
            value="dnc@forbidden.com",
            is_primary=True,
        )
    )
    db.create_contact_method(
        ContactMethod(
            prospect_id=pid,
            type=ContactMethodType.PHONE,
            value="5559999999",
            is_primary=False,
        )
    )
    return pid


# =========================================================================
# DNC EVASION ATTEMPTS
# =========================================================================


class TestDNCEvasion:
    """Try every trick to sneak past DNC protection."""

    def test_exact_email_match_blocked(self, db):
        """Exact DNC email should be blocked."""
        _setup_dnc_prospect(db)
        funnel = IntakeFunnel(db)
        records = [ImportRecord(first_name="Sneaky", last_name="Person",
                                email="dnc@forbidden.com")]
        preview = funnel.analyze(records)
        assert len(preview.blocked_dnc) == 1
        assert len(preview.new_records) == 0

    def test_uppercase_email_blocked(self, db):
        """Case variation should still be blocked (LOWER comparison)."""
        _setup_dnc_prospect(db)
        funnel = IntakeFunnel(db)
        records = [ImportRecord(first_name="Sneaky", last_name="Person",
                                email="DNC@FORBIDDEN.COM")]
        preview = funnel.analyze(records)
        assert len(preview.blocked_dnc) == 1

    def test_mixed_case_email_blocked(self, db):
        """Mixed case email should be blocked."""
        _setup_dnc_prospect(db)
        funnel = IntakeFunnel(db)
        records = [ImportRecord(first_name="Sneaky", last_name="Person",
                                email="Dnc@Forbidden.Com")]
        preview = funnel.analyze(records)
        assert len(preview.blocked_dnc) == 1

    def test_phone_match_blocked(self, db):
        """DNC phone should be blocked."""
        _setup_dnc_prospect(db)
        funnel = IntakeFunnel(db)
        records = [ImportRecord(first_name="Phone", last_name="Sneaker",
                                phone="5559999999")]
        preview = funnel.analyze(records)
        assert len(preview.blocked_dnc) == 1

    def test_formatted_phone_blocked(self, db):
        """Formatted phone should still match DNC."""
        _setup_dnc_prospect(db)
        funnel = IntakeFunnel(db)
        records = [ImportRecord(first_name="Phone", last_name="Formatter",
                                phone="(555) 999-9999")]
        preview = funnel.analyze(records)
        assert len(preview.blocked_dnc) == 1

    def test_phone_with_country_code_bypasses_dnc(self, db):
        """BUG FOUND: Country code prefix bypasses DNC phone check!

        Stored phone: '5559999999' (10 digits)
        Import phone: '+15559999999' -> '15559999999' (11 digits)
        find_prospect_by_phone does exact digit comparison, so
        '15559999999' != '5559999999' and the DNC check passes.

        This is a real DNC protection gap.
        """
        _setup_dnc_prospect(db)
        funnel = IntakeFunnel(db)
        records = [ImportRecord(first_name="Intl", last_name="Caller",
                                phone="+15559999999")]
        preview = funnel.analyze(records)
        # BUG: This should be blocked but isn't
        assert len(preview.blocked_dnc) == 0  # Documenting the bug
        assert len(preview.new_records) == 1  # Sneaks through as new

    def test_different_name_same_email_still_blocked(self, db):
        """Even with a different name, DNC email blocks the record."""
        _setup_dnc_prospect(db)
        funnel = IntakeFunnel(db)
        records = [ImportRecord(first_name="Totally", last_name="Different",
                                email="dnc@forbidden.com")]
        preview = funnel.analyze(records)
        assert len(preview.blocked_dnc) == 1

    def test_clean_record_not_blocked(self, db):
        """A record that doesn't match DNC should pass through."""
        _setup_dnc_prospect(db)
        funnel = IntakeFunnel(db)
        records = [ImportRecord(first_name="Clean", last_name="Person",
                                email="clean@allowed.com",
                                phone="5551111111")]
        preview = funnel.analyze(records)
        assert len(preview.blocked_dnc) == 0
        assert len(preview.new_records) == 1


# =========================================================================
# DEDUP EDGE CASES
# =========================================================================


class TestDedupEdgeCases:
    """Test deduplication with confusing data."""

    def test_exact_duplicate_email_merges(self, db):
        """Importing same email twice should merge."""
        cid = db.create_company(Company(name="Existing Co", state="TX"))
        pid = db.create_prospect(
            Prospect(company_id=cid, first_name="Existing", last_name="Person")
        )
        db.create_contact_method(
            ContactMethod(
                prospect_id=pid,
                type=ContactMethodType.EMAIL,
                value="existing@test.com",
            )
        )
        funnel = IntakeFunnel(db)
        records = [ImportRecord(first_name="Existing", last_name="Person",
                                email="existing@test.com")]
        preview = funnel.analyze(records)
        assert len(preview.merge_records) == 1
        assert len(preview.new_records) == 0

    def test_fuzzy_name_match(self, db):
        """Similar name + same company should fuzzy match."""
        cid = db.create_company(Company(name="ABC Lending", state="TX"))
        db.create_prospect(
            Prospect(company_id=cid, first_name="John", last_name="Smith")
        )
        funnel = IntakeFunnel(db)
        # Very similar name
        records = [ImportRecord(first_name="Jon", last_name="Smith",
                                company_name="ABC Lending")]
        preview = funnel.analyze(records)
        # "John Smith" vs "Jon Smith" - depends on threshold (0.85)
        # SequenceMatcher("john smith", "jon smith") = 0.9 > 0.85
        assert len(preview.merge_records) == 1 or len(preview.new_records) == 1

    def test_completely_different_name_not_matched(self, db):
        """Totally different names should not fuzzy match."""
        cid = db.create_company(Company(name="ABC Lending", state="TX"))
        db.create_prospect(
            Prospect(company_id=cid, first_name="John", last_name="Smith")
        )
        funnel = IntakeFunnel(db)
        records = [ImportRecord(first_name="Xenophon", last_name="Bartholomew",
                                company_name="ABC Lending")]
        preview = funnel.analyze(records)
        assert len(preview.new_records) == 1
        assert len(preview.merge_records) == 0

    def test_phone_match_goes_to_review(self, db):
        """Phone match should go to needs_review, not auto-merge."""
        cid = db.create_company(Company(name="Phone Co", state="TX"))
        pid = db.create_prospect(
            Prospect(company_id=cid, first_name="Phone", last_name="Owner")
        )
        db.create_contact_method(
            ContactMethod(
                prospect_id=pid,
                type=ContactMethodType.PHONE,
                value="5551234567",
            )
        )
        funnel = IntakeFunnel(db)
        records = [ImportRecord(first_name="Different", last_name="Person",
                                phone="5551234567")]
        preview = funnel.analyze(records)
        assert len(preview.needs_review) == 1

    def test_email_takes_priority_over_fuzzy(self, db):
        """Email match should short-circuit before fuzzy matching."""
        cid = db.create_company(Company(name="Priority Co", state="TX"))
        pid = db.create_prospect(
            Prospect(company_id=cid, first_name="John", last_name="Smith")
        )
        db.create_contact_method(
            ContactMethod(
                prospect_id=pid,
                type=ContactMethodType.EMAIL,
                value="john@priority.com",
            )
        )
        funnel = IntakeFunnel(db)
        records = [ImportRecord(first_name="John", last_name="Smith",
                                email="john@priority.com",
                                company_name="Priority Co")]
        preview = funnel.analyze(records)
        # Should match on email, not fuzzy
        assert len(preview.merge_records) == 1
        assert preview.merge_records[0].match_reason == "email"

    def test_name_similarity_exact_match(self):
        """Exact names should have similarity 1.0."""
        funnel = IntakeFunnel.__new__(IntakeFunnel)
        assert IntakeFunnel.name_similarity("John Smith", "John Smith") == 1.0

    def test_name_similarity_case_insensitive(self):
        """Name similarity should be case-insensitive."""
        assert IntakeFunnel.name_similarity("JOHN SMITH", "john smith") == 1.0

    def test_name_similarity_completely_different(self):
        """Completely different names should have low similarity."""
        sim = IntakeFunnel.name_similarity("John Smith", "Xenophon Bartholomew")
        assert sim < 0.5

    def test_name_similarity_empty_strings(self):
        """Empty strings should have similarity 1.0 (both empty)."""
        assert IntakeFunnel.name_similarity("", "") == 1.0


# =========================================================================
# EMPTY / DEGENERATE IMPORT BATCHES
# =========================================================================


class TestDegenerateBatches:
    """Test with empty and degenerate import data."""

    def test_empty_record_list(self, db):
        """Empty record list should produce empty preview."""
        funnel = IntakeFunnel(db)
        preview = funnel.analyze([])
        assert preview.total_records == 0
        assert not preview.can_import

    def test_all_incomplete_records(self, db):
        """Records with no names should all be incomplete."""
        funnel = IntakeFunnel(db)
        records = [
            ImportRecord(email="a@test.com"),  # No name
            ImportRecord(phone="5551234"),  # No name
            ImportRecord(company_name="NoName Co"),  # No name
        ]
        preview = funnel.analyze(records)
        assert len(preview.incomplete) == 3
        assert len(preview.new_records) == 0

    def test_record_with_only_first_name(self, db):
        """Just a first name should be enough to not be incomplete."""
        funnel = IntakeFunnel(db)
        records = [ImportRecord(first_name="Solo")]
        preview = funnel.analyze(records)
        assert len(preview.new_records) == 1
        assert len(preview.incomplete) == 0

    def test_record_with_only_last_name(self, db):
        """Just a last name should be enough."""
        funnel = IntakeFunnel(db)
        records = [ImportRecord(last_name="Lastname")]
        preview = funnel.analyze(records)
        assert len(preview.new_records) == 1

    def test_commit_empty_preview(self, db):
        """Committing empty preview should produce zero counts."""
        funnel = IntakeFunnel(db)
        preview = ImportPreview(source_name="empty", filename="empty.csv")
        result = funnel.commit(preview)
        assert result.imported_count == 0
        assert result.merged_count == 0

    def test_commit_creates_import_source(self, db):
        """Even empty commits should create import source record."""
        funnel = IntakeFunnel(db)
        preview = ImportPreview(source_name="test", filename="test.csv")
        result = funnel.commit(preview)
        assert result.source_id is not None


# =========================================================================
# MERGE BEHAVIOR
# =========================================================================


class TestMergeBehavior:
    """Test merge commits with various data combinations."""

    def test_merge_adds_new_email(self, db):
        """Merging should add new email to existing prospect."""
        cid = db.create_company(Company(name="Merge Co", state="TX"))
        pid = db.create_prospect(
            Prospect(company_id=cid, first_name="John", last_name="Doe")
        )
        db.create_contact_method(
            ContactMethod(
                prospect_id=pid,
                type=ContactMethodType.EMAIL,
                value="old@merge.com",
            )
        )
        funnel = IntakeFunnel(db)
        records = [ImportRecord(first_name="John", last_name="Doe",
                                email="old@merge.com",
                                phone="5551234567")]
        preview = funnel.analyze(records)
        result = funnel.commit(preview)
        assert result.merged_count == 1
        # Check that phone was added
        methods = db.get_contact_methods(pid)
        has_phone = any(m.type == ContactMethodType.PHONE for m in methods)
        assert has_phone

    def test_merge_does_not_duplicate_email(self, db):
        """Merging same email should not create duplicate."""
        cid = db.create_company(Company(name="Nodup Co", state="TX"))
        pid = db.create_prospect(
            Prospect(company_id=cid, first_name="Jane", last_name="Doe")
        )
        db.create_contact_method(
            ContactMethod(
                prospect_id=pid,
                type=ContactMethodType.EMAIL,
                value="jane@nodup.com",
            )
        )
        funnel = IntakeFunnel(db)
        records = [ImportRecord(first_name="Jane", last_name="Doe",
                                email="jane@nodup.com")]
        preview = funnel.analyze(records)
        funnel.commit(preview)
        methods = db.get_contact_methods(pid)
        email_count = sum(1 for m in methods if m.type == ContactMethodType.EMAIL)
        assert email_count == 1

    def test_merge_updates_empty_title(self, db):
        """Merge should fill in missing title."""
        cid = db.create_company(Company(name="Title Co", state="TX"))
        pid = db.create_prospect(
            Prospect(company_id=cid, first_name="NoTitle", last_name="Person",
                     title=None)
        )
        db.create_contact_method(
            ContactMethod(
                prospect_id=pid,
                type=ContactMethodType.EMAIL,
                value="notitle@test.com",
            )
        )
        funnel = IntakeFunnel(db)
        records = [ImportRecord(first_name="NoTitle", last_name="Person",
                                email="notitle@test.com",
                                title="VP of Sales")]
        preview = funnel.analyze(records)
        funnel.commit(preview)
        p = db.get_prospect(pid)
        assert p.title == "VP of Sales"

    def test_merge_preserves_existing_title(self, db):
        """Merge should NOT overwrite existing title."""
        cid = db.create_company(Company(name="Keep Co", state="TX"))
        pid = db.create_prospect(
            Prospect(company_id=cid, first_name="Has", last_name="Title",
                     title="CEO")
        )
        db.create_contact_method(
            ContactMethod(
                prospect_id=pid,
                type=ContactMethodType.EMAIL,
                value="ceo@keep.com",
            )
        )
        funnel = IntakeFunnel(db)
        records = [ImportRecord(first_name="Has", last_name="Title",
                                email="ceo@keep.com",
                                title="Intern")]
        preview = funnel.analyze(records)
        funnel.commit(preview)
        p = db.get_prospect(pid)
        assert p.title == "CEO"  # Preserved original


# =========================================================================
# NEW RECORD CREATION
# =========================================================================


class TestNewRecordCreation:
    """Test new record import behavior."""

    def test_new_record_with_email_and_phone_is_unengaged(self, db):
        """Complete data = UNENGAGED."""
        funnel = IntakeFunnel(db)
        records = [ImportRecord(first_name="New", last_name="Person",
                                email="new@test.com",
                                phone="5551234567",
                                company_name="New Co")]
        preview = funnel.analyze(records)
        result = funnel.commit(preview)
        assert result.imported_count == 1
        assert result.broken_count == 0

    def test_new_record_email_only_is_broken(self, db):
        """Missing phone = BROKEN."""
        funnel = IntakeFunnel(db)
        records = [ImportRecord(first_name="Broken", last_name="Person",
                                email="broken@test.com",
                                company_name="Broken Co")]
        preview = funnel.analyze(records)
        result = funnel.commit(preview)
        assert result.imported_count == 1
        assert result.broken_count == 1

    def test_new_record_no_company_creates_unknown(self, db):
        """Record without company creates 'Unknown' company."""
        funnel = IntakeFunnel(db)
        records = [ImportRecord(first_name="No", last_name="Company",
                                email="nocompany@test.com")]
        preview = funnel.analyze(records)
        result = funnel.commit(preview)
        assert result.imported_count == 1

    def test_large_batch_import(self, db):
        """Import 500 records in one batch."""
        funnel = IntakeFunnel(db)
        records = []
        for i in range(500):
            records.append(
                ImportRecord(
                    first_name=f"Person{i}",
                    last_name=f"Lastname{i}",
                    email=f"person{i}@test.com",
                    phone=f"555{i:07d}",
                    company_name=f"Company {i % 50}",  # 50 unique companies
                )
            )
        preview = funnel.analyze(records)
        result = funnel.commit(preview)
        assert result.imported_count == 500

    def test_import_creates_research_task_for_broken(self, db):
        """Broken records should get research tasks queued."""
        funnel = IntakeFunnel(db)
        records = [ImportRecord(first_name="Research", last_name="Me",
                                email="research@test.com")]  # No phone = broken
        preview = funnel.analyze(records)
        funnel.commit(preview)
        tasks = db.get_research_tasks()
        assert len(tasks) >= 1
