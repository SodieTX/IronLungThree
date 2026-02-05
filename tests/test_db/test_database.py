"""Tests for database operations."""

import pytest
from pathlib import Path
from src.db.database import Database
from src.db.models import Company, Prospect, Population


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
    
    @pytest.mark.skip(reason="Stub not implemented")
    def test_initialize_schema(self, memory_db: Database):
        """Schema initialization creates tables."""
        # Would verify tables exist
        pass


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
