"""Shared pytest fixtures for IronLung 3 tests.

Fixtures:
    - temp_db: Fresh in-memory SQLite database
    - sample_company: Sample Company record
    - sample_prospect: Sample Prospect record
    - sample_activity: Sample Activity record
    - mock_config: Test configuration
    - mock_outlook: Mocked Outlook client
"""

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Generator

import pytest

from src.core.config import Config
from src.db.database import Database

# Import models
from src.db.models import (
    Activity,
    ActivityType,
    Company,
    ContactMethod,
    ContactMethodType,
    EngagementStage,
    Population,
    Prospect,
)


@pytest.fixture
def temp_db(tmp_path: Path) -> Generator[Database, None, None]:
    """Create a temporary database for testing.

    Yields:
        Database connected to temp file, cleaned up after test
    """
    db_path = tmp_path / "test.db"
    db = Database(str(db_path))
    db.initialize()
    yield db
    db.close()


@pytest.fixture
def memory_db() -> Generator[Database, None, None]:
    """Create an in-memory database for fast tests.

    Yields:
        Database using :memory:, no cleanup needed
    """
    db = Database(":memory:")
    db.initialize()
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
        type=ContactMethodType.EMAIL,
        value="john.doe@acme.com",
        label="work",
        is_verified=True,
    )


@pytest.fixture
def sample_activity(sample_prospect: Prospect) -> Activity:
    """Sample Activity record for testing."""
    return Activity(
        id=1,
        prospect_id=sample_prospect.id,
        activity_type=ActivityType.CALL,
        notes="Left voicemail about Q1 priorities",
        created_at=datetime(2026, 2, 1, 10, 30),
    )


@pytest.fixture
def mock_config(tmp_path: Path) -> Config:
    """Test configuration with temp paths."""
    return Config(
        db_path=tmp_path / "test.db",
        backup_path=tmp_path / "backups",
        log_path=tmp_path / "logs",
        debug=True,
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
        - 1 company (Acme Corp)
        - 2 prospects (1 unengaged, 1 engaged)
        - 1 contact method (email on unengaged prospect)
        - 1 activity (call on unengaged prospect)
    """
    company_id = memory_db.create_company(sample_company)

    # Create unengaged prospect
    unengaged = Prospect(
        company_id=company_id,
        first_name=sample_prospect.first_name,
        last_name=sample_prospect.last_name,
        title=sample_prospect.title,
        population=sample_prospect.population,
        follow_up_date=sample_prospect.follow_up_date,
        attempt_count=sample_prospect.attempt_count,
        prospect_score=sample_prospect.prospect_score,
        data_confidence=sample_prospect.data_confidence,
        source=sample_prospect.source,
    )
    p1_id = memory_db.create_prospect(unengaged)

    # Create engaged prospect
    engaged = Prospect(
        company_id=company_id,
        first_name=sample_engaged_prospect.first_name,
        last_name=sample_engaged_prospect.last_name,
        title=sample_engaged_prospect.title,
        population=sample_engaged_prospect.population,
        engagement_stage=sample_engaged_prospect.engagement_stage,
        follow_up_date=sample_engaged_prospect.follow_up_date,
        last_contact_date=sample_engaged_prospect.last_contact_date,
        attempt_count=sample_engaged_prospect.attempt_count,
        prospect_score=sample_engaged_prospect.prospect_score,
        data_confidence=sample_engaged_prospect.data_confidence,
        source=sample_engaged_prospect.source,
    )
    memory_db.create_prospect(engaged)

    # Add contact method to unengaged prospect
    contact = ContactMethod(
        prospect_id=p1_id,
        type=sample_contact_method.type,
        value=sample_contact_method.value,
        label=sample_contact_method.label,
        is_verified=sample_contact_method.is_verified,
    )
    memory_db.create_contact_method(contact)

    # Add activity to unengaged prospect
    activity = Activity(
        prospect_id=p1_id,
        activity_type=sample_activity.activity_type,
        notes=sample_activity.notes,
    )
    memory_db.create_activity(activity)

    return memory_db


# Markers for different test types
def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests requiring external services")
    config.addinivalue_line("markers", "database: marks tests requiring database")
