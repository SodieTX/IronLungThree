"""IronLung 3 Test Suite.

Test organization mirrors src/ structure:
    tests/
    ├── conftest.py          # Shared fixtures
    ├── test_core/           # Core utilities tests
    ├── test_db/             # Database tests
    ├── test_integrations/   # Integration tests
    ├── test_engine/         # Business logic tests
    ├── test_ai/             # AI component tests
    ├── test_autonomous/     # Autonomous process tests
    ├── test_gui/            # GUI tests
    └── test_content/        # Content generation tests

Markers:
    - @pytest.mark.slow: Tests taking > 1 second
    - @pytest.mark.integration: Tests requiring external services
    - @pytest.mark.database: Tests requiring database
"""
