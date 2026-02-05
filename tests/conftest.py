"""Shared pytest fixtures for IronLung 3 tests.

Fixtures:
    - temp_db: Fresh in-memory SQLite database
    - sample_company: Sample Company record
    - sample_prospect: Sample Prospect record
    - sample_activity: Sample Activity record
    - mock_config: Test configuration
    - mock_outlook: Mocked Outlook client
"""

import pytest
from datetime import datetime, date
from pathlib import Path
from typing import Generator
from decimal import Decimal

# Import models
from src.db.models import (
    Company,
    Prospect,
    Activity,
    ContactMethod,
    Population,
    EngagementStage,
    ActivityType,
    ContactMethodType,
)
from src.db.database import Database
from src.core.config import Config


@pytest.fixture
def temp_db(tmp_path: Path) -> Generator[Database, None, None]:
    """Create a temporary database for testing.
    
    Yields:
        Database connected to temp file, cleaned up after test
    """
    db_path = tmp_path / "test.db"
    db = Database(str(db_path))
    db.initialize_schema()
    yield db
    db.close()


@pytest.fixture
def memory_db() -> Generator[Database, None, None]:
    """Create an in-memory database for fast tests.
    
    Yields:
        Database using :memory:, no cleanup needed
    """
    db = Database(":memory:")
    db.initialize_schema()
    yield db
    db.close()


@pytest.fixture
def sample_company() -> Company:
    """Sample Company record for testing."""
    return Company(
        id=1,
        name="Acme Corp",
        name_normalized="acme",
        domain="acme.com",
        size="medium",
        state="CO",
        timezone="mountain",
        notes="Sample company for testing",
    )


@pytest.fixture
def sample_prospect(sample_company: Company) -> Prospect:
    """Sample Prospect record for testing."""
    return Prospect(
        id=1,
        company_id=sample_company.id,
        first_name="John",
        last_name="Doe",
        title="VP of Operations",
        population=Population.UNENGAGED,
        engagement_stage=None,
        follow_up_date=datetime(2026, 2, 10, 9, 0),
        attempt_count=2,
        prospect_score=75,
        data_confidence=80,
        source="LinkedIn Import",
    )


@pytest.fixture
def sample_engaged_prospect(sample_company: Company) -> Prospect:
    """Sample Engaged Prospect for testing."""
    return Prospect(
        id=2,
        company_id=sample_company.id,
        first_name="Jane",
        last_name="Smith",
        title="CEO",
        population=Population.ENGAGED,
        engagement_stage=EngagementStage.PRE_DEMO,
        follow_up_date=datetime(2026, 2, 6, 14, 0),
        last_contact_date=date(2026, 2, 1),
        attempt_count=3,
        prospect_score=90,
        data_confidence=95,
        source="Referral",
    )


@pytest.fixture
def sample_contact_method(sample_prospect: Prospect) -> ContactMethod:
    """Sample ContactMethod for testing."""
    return ContactMethod(
        id=1,
        prospect_id=sample_prospect.id,
        type=ContactMethodType.WORK_EMAIL,
        value="john.doe@acme.com",
        is_verified=True,
    )


@pytest.fixture
def sample_activity(sample_prospect: Prospect) -> Activity:
    """Sample Activity record for testing."""
    return Activity(
        id=1,
        prospect_id=sample_prospect.id,
        type=ActivityType.CALL_OUTBOUND,
        outcome="left_voicemail",
        notes="Left voicemail about Q1 priorities",
        activity_date=datetime(2026, 2, 1, 10, 30),
    )


@pytest.fixture
def mock_config(tmp_path: Path) -> Config:
    """Test configuration with temp paths."""
    return Config(
        db_path=str(tmp_path / "test.db"),
        backup_path=str(tmp_path / "backups"),
        log_path=str(tmp_path / "logs"),
        data_path=str(tmp_path / "data"),
        debug_mode=True,
    )


@pytest.fixture
def populated_db(
    memory_db: Database,
    sample_company: Company,
    sample_prospect: Prospect,
    sample_engaged_prospect: Prospect,
    sample_contact_method: ContactMethod,
    sample_activity: Activity,
) -> Database:
    """Database pre-populated with sample data.
    
    Contains:
        - 1 company
        - 2 prospects (1 unengaged, 1 engaged)
        - 1 contact method
        - 1 activity
    """
    # Note: These would insert data once save methods are implemented
    # For now, fixture just provides populated database concept
    return memory_db


# Markers for different test types
def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests requiring external services"
    )
    config.addinivalue_line(
        "markers", "database: marks tests requiring database"
    )
