"""Tests for database operations."""

from pathlib import Path

import pytest

from src.db.database import Database
from src.db.models import Company, Population, Prospect


class TestDatabaseConnection:
    """Test database connection management."""

    def test_connect_creates_file(self, tmp_path: Path):
        """Connecting creates database file."""
        db_path = tmp_path / "new.db"
        db = Database(str(db_path))
        # Connection happens lazily on first use
        db.initialize()
        assert db_path.exists()
        db.close()

    def test_connect_memory_database(self):
        """Can connect to memory database."""
        db = Database(":memory:")
        # Connection happens lazily, so just close to verify no error
        db.close()

    def test_initialize_schema(self, memory_db: Database):
        """Schema initialization creates all required tables and indexes."""
        # Get list of tables
        conn = memory_db._get_connection()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [t[0] for t in tables]

        # Verify all 10 tables exist (9 data tables + schema_version)
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

        # Verify indexes exist
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

        # Verify schema version is 1
        version = conn.execute("SELECT version FROM schema_version").fetchone()
        assert version[0] == 1

    def test_wal_mode_enabled(self, tmp_path: Path):
        """WAL journal mode is enabled for file databases."""
        db_path = tmp_path / "test_wal.db"
        db = Database(str(db_path))
        db.initialize()

        journal_mode = db._get_connection().execute("PRAGMA journal_mode").fetchone()[0]
        assert journal_mode == "wal", f"Expected WAL mode, got {journal_mode}"
        db.close()

    def test_foreign_keys_enabled(self, memory_db: Database):
        """Foreign key constraints are enabled."""
        fk_status = memory_db._get_connection().execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk_status == 1, "Foreign keys should be enabled"


class TestCompanyCRUD:
    """Test Company CRUD operations."""

    @pytest.mark.skip(reason="Stub not implemented")
    def test_save_company(self, memory_db: Database, sample_company: Company):
        """Can save a company."""
        company_id = memory_db.save_company(sample_company)
        assert company_id > 0

    @pytest.mark.skip(reason="Stub not implemented")
    def test_get_company(self, memory_db: Database, sample_company: Company):
        """Can retrieve saved company."""
        memory_db.save_company(sample_company)
        retrieved = memory_db.get_company(sample_company.id)
        assert retrieved.name == sample_company.name


class TestProspectCRUD:
    """Test Prospect CRUD operations."""

    @pytest.mark.skip(reason="Stub not implemented")
    def test_save_prospect(self, memory_db: Database, sample_prospect: Prospect):
        """Can save a prospect."""
        pass

    @pytest.mark.skip(reason="Stub not implemented")
    def test_get_prospect_by_population(self, memory_db: Database):
        """Can query prospects by population."""
        pass


class TestDatabaseIntegrity:
    """Test database integrity constraints."""

    @pytest.mark.skip(reason="Stub not implemented")
    def test_foreign_key_enforcement(self, memory_db: Database):
        """Foreign keys are enforced."""
        # Prospect with invalid company_id should fail
        pass

    @pytest.mark.skip(reason="Stub not implemented")
    def test_dnc_population_protection(self, memory_db: Database):
        """DNC records cannot be reactivated via raw query."""
        pass
