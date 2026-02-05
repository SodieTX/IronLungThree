# Testing Pattern

## Overview

IronLung 3 uses pytest for testing with shared fixtures and clear test organization.

## Test Structure

```
tests/
├── __init__.py
├── conftest.py           # Shared fixtures
├── test_core/            # Core utilities
├── test_db/              # Database operations
├── test_integrations/    # External integrations
├── test_engine/          # Business logic
├── test_ai/              # AI components
├── test_autonomous/      # Background processes
├── test_gui/             # GUI logic (non-visual)
└── test_content/         # Content generation
```

## Running Tests

```bash
# All tests
pytest

# Specific module
pytest tests/test_db/

# Single test
pytest tests/test_db/test_models.py::TestProspectModel::test_full_name

# With coverage
pytest --cov=src --cov-report=html

# Skip slow tests
pytest -m "not slow"

# Only integration tests
pytest -m integration
```

## Fixtures

### Standard Fixtures (conftest.py)

```python
# Fresh database for each test
def test_something(memory_db):
    memory_db.save_company(company)

# Pre-populated database
def test_query(populated_db):
    results = populated_db.get_prospects_by_population(Population.UNENGAGED)

# Sample data objects
def test_prospect(sample_prospect, sample_company):
    assert sample_prospect.company_id == sample_company.id
```

### Creating Custom Fixtures

```python
@pytest.fixture
def engaged_prospects(memory_db, sample_company):
    """Multiple engaged prospects for testing."""
    prospects = []
    for i in range(5):
        p = Prospect(
            company_id=sample_company.id,
            first_name=f"Test{i}",
            last_name="User",
            population=Population.ENGAGED,
            engagement_stage=EngagementStage.DISCOVERY,
        )
        memory_db.save_prospect(p)
        prospects.append(p)
    return prospects
```

## Test Categories

### Unit Tests

Test individual functions/classes in isolation:

```python
class TestNameSimilarity:
    def test_exact_match(self):
        assert IntakeFunnel.name_similarity("John", "John") >= 0.9
    
    def test_different_names(self):
        assert IntakeFunnel.name_similarity("John", "Jane") < 0.5
```

### Integration Tests

Test components working together:

```python
@pytest.mark.integration
class TestOutlookIntegration:
    def test_send_email(self, outlook_client, sample_prospect):
        # Requires actual Outlook connection
        pass
```

### Database Tests

Test database operations:

```python
@pytest.mark.database
class TestProspectCRUD:
    def test_save_and_retrieve(self, memory_db, sample_prospect):
        prospect_id = memory_db.save_prospect(sample_prospect)
        retrieved = memory_db.get_prospect(prospect_id)
        assert retrieved.first_name == sample_prospect.first_name
```

## Markers

```python
# Slow tests (>1 second)
@pytest.mark.slow
def test_full_nightly_cycle():
    pass

# Requires external service
@pytest.mark.integration
def test_outlook_send():
    pass

# Requires database
@pytest.mark.database
def test_complex_query():
    pass
```

## Test Naming

```python
# Good: descriptive, specific
def test_dnc_prospect_cannot_transition_to_unengaged():
    pass

def test_follow_up_date_must_be_in_future():
    pass

# Bad: vague
def test_prospect():
    pass

def test_error():
    pass
```

## Assertions

```python
# Use specific assertions
assert prospect.population == Population.ENGAGED
assert "email" in error_message.lower()
assert len(results) == 5

# For exceptions
with pytest.raises(DNCViolationError, match="cannot transition"):
    transition_prospect(dnc_prospect, Population.UNENGAGED)

# For approximate values
assert score == pytest.approx(75.0, rel=0.1)
```

## Skipping Tests

```python
# Skip until implemented
@pytest.mark.skip(reason="Stub not implemented")
def test_future_feature():
    pass

# Skip conditionally
@pytest.mark.skipif(
    not os.getenv("OUTLOOK_CLIENT_ID"),
    reason="Outlook credentials not configured"
)
def test_outlook_integration():
    pass
```

## Code Coverage

Minimum coverage targets:
- `src/core/`: 90%
- `src/db/`: 85%
- `src/engine/`: 80%
- Overall: 75%

```bash
# Generate coverage report
pytest --cov=src --cov-report=html --cov-fail-under=75
```

## See Also

- `tests/conftest.py` - Shared fixtures
- `pytest.ini` - pytest configuration
- `pyproject.toml` - Coverage settings
