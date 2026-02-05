# Complete Pre-Coding Scaffolding for IronLung 3

This plan establishes the full project foundation before any implementation code is written. The goal is to have a skeleton where every file exists as a stub with type hints, docstrings, and interface contracts - so when Phase 1 coding begins, you're filling in implementations rather than creating structure.

---

## 1. Documentation Structure

### 1.1 Create Documentation Hierarchy

```
docs/
├── ARCHITECTURE-OVERVIEW.md      # High-level system overview (referenced by Schema Spec)
├── GLOSSARY.md                   # Terms: Population vs Stage vs Status, etc.
├── SCHEMA-SPEC.md                # Already exists
├── layers/
│   ├── LAYER-1-SLAB.md          # Database, models, config, logging, exceptions
│   ├── LAYER-2-PIPES.md         # Integrations specifications
│   ├── LAYER-3-ENGINE.md        # Business logic specifications
│   ├── LAYER-4-FACE.md          # GUI specifications
│   ├── LAYER-5-BRAIN.md         # Anne AI specifications
│   ├── LAYER-6-HEARTBEAT.md     # Autonomous operations specifications
│   └── LAYER-7-SOUL.md          # ADHD UX specifications
├── build/
│   ├── PHASE-1-SLAB.md          # Detailed Phase 1 build spec
│   ├── PHASE-2-GRIND.md         # Placeholder for Phase 2 spec
│   └── ... (one per phase)
├── adr/
│   ├── 001-sqlite-over-postgres.md
│   ├── 002-tkinter-over-electron.md
│   ├── 003-polling-over-webhooks.md
│   ├── 004-notes-as-memory.md
│   └── 005-dual-cadence-system.md
└── patterns/
    ├── LOGGING-SPEC.md          # JSON logging format, levels, fields
    ├── CONFIG-SPEC.md           # Environment variables, .env format
    ├── ERROR-HANDLING.md        # Exception patterns, recovery strategies
    └── TESTING-PATTERNS.md      # Fixtures, mocking, test organization
```

### 1.2 Key Documents to Create

**ARCHITECTURE-OVERVIEW.md** - One-page visual summary:

- Layer diagram with data flow arrows
- Key interfaces between layers
- Critical paths (morning brief, card processing, nightly cycle)

**GLOSSARY.md** - Define precisely:

- Population (where in pipeline) vs Stage (within Engaged) vs Status (active/inactive)
- Attempt vs Contact vs Interaction
- Card vs Prospect vs Contact
- System-paced vs Prospect-paced

**Phase 1 Build Spec** - Detailed expansion of Build Sequence steps 1.1-1.16:

- Exact function signatures with type hints
- Exact DDL statements (already in Schema Spec)
- Exact test cases with expected inputs/outputs
- Performance benchmarks with measurement code

---

## 2. Project Skeleton

### 2.1 Root Configuration Files

```
ironlung3/
├── ironlung3.py                  # Entry point stub
├── pyproject.toml                # Modern Python project config
├── requirements.txt              # Pinned dependencies
├── requirements-dev.txt          # Development dependencies (pytest, etc.)
├── .env.example                  # Template environment file
├── .gitignore                    # Already defined in Build Sequence
├── README.md                     # Project overview + quickstart
└── pytest.ini                    # pytest configuration
```

**pyproject.toml** - Modern Python configuration:

- Project metadata
- Python version requirement (3.11+)
- Tool configurations (black, isort, mypy)

**requirements.txt** - Phase 1 dependencies:

```
openpyxl>=3.1.0
python-dotenv>=1.0.0
```

**requirements-dev.txt**:

```
pytest>=8.0.0
pytest-cov>=4.1.0
mypy>=1.8.0
black>=24.0.0
isort>=5.13.0
```

### 2.2 Source Directory Structure

Create all directories and `__init__.py` files:

```
src/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── config.py
│   ├── exceptions.py
│   ├── logging.py
│   └── tasks.py
├── db/
│   ├── __init__.py
│   ├── database.py
│   ├── models.py
│   ├── backup.py
│   └── intake.py
├── integrations/
│   ├── __init__.py
│   ├── base.py
│   ├── outlook.py
│   ├── bria.py
│   ├── activecampaign.py
│   ├── google_search.py
│   ├── csv_importer.py
│   └── email_importer.py
├── engine/
│   ├── __init__.py
│   ├── populations.py
│   ├── cadence.py
│   ├── scoring.py
│   ├── research.py
│   ├── groundskeeper.py
│   ├── nurture.py
│   ├── learning.py
│   ├── intervention.py
│   ├── templates.py
│   ├── email_gen.py
│   ├── demo_prep.py
│   └── export.py
├── ai/
│   ├── __init__.py
│   ├── anne.py
│   ├── parser.py
│   ├── disposition.py
│   ├── copilot.py
│   ├── rescue.py
│   ├── style_learner.py
│   ├── card_story.py
│   ├── insights.py
│   └── contact_analyzer.py
├── autonomous/
│   ├── __init__.py
│   ├── nightly.py
│   ├── orchestrator.py
│   ├── scheduler.py
│   ├── reply_monitor.py
│   ├── email_sync.py
│   └── activity_capture.py
├── gui/
│   ├── __init__.py
│   ├── app.py
│   ├── theme.py
│   ├── dictation_bar.py
│   ├── cards.py
│   ├── shortcuts.py
│   ├── tabs/
│   │   ├── __init__.py
│   │   ├── today.py
│   │   ├── broken.py
│   │   ├── pipeline.py
│   │   ├── calendar.py
│   │   ├── demos.py
│   │   ├── partnerships.py
│   │   ├── import_tab.py
│   │   ├── settings.py
│   │   ├── troubled.py
│   │   ├── intel_gaps.py
│   │   └── analytics.py
│   ├── dialogs/
│   │   ├── __init__.py
│   │   ├── morning_brief.py
│   │   ├── edit_prospect.py
│   │   ├── import_preview.py
│   │   ├── quick_action.py
│   │   ├── closed_won.py
│   │   └── email_recall.py
│   └── adhd/
│       ├── __init__.py
│       ├── dopamine.py
│       ├── session.py
│       ├── focus.py
│       ├── audio.py
│       ├── command_palette.py
│       ├── dashboard.py
│       └── compassion.py
└── content/
    ├── __init__.py
    ├── morning_brief.py
    ├── daily_cockpit.py
    └── eod_summary.py
```

### 2.3 Test Directory Structure

```
tests/
├── __init__.py
├── conftest.py                   # Shared fixtures
├── test_core/
│   ├── __init__.py
│   ├── test_exceptions.py
│   ├── test_logging.py
│   └── test_config.py
├── test_db/
│   ├── __init__.py
│   ├── test_database.py
│   ├── test_models.py
│   ├── test_backup.py
│   └── test_intake.py
├── test_integrations/
│   ├── __init__.py
│   └── test_csv_importer.py
├── test_engine/
│   └── __init__.py
├── test_ai/
│   └── __init__.py
├── test_autonomous/
│   └── __init__.py
└── test_gui/
    └── __init__.py
```

### 2.4 Data and Config Directories

```
config/
├── .env.example
└── settings.py                   # Feature flags, cadence defaults

data/
├── backups/
│   └── .gitkeep
└── style_examples/
    └── .gitkeep

templates/
└── emails/
    ├── intro.html.j2
    ├── follow_up.html.j2
    ├── demo_confirmation.html.j2
    ├── demo_invite.html.j2
    ├── nurture_1.html.j2
    ├── nurture_2.html.j2
    ├── nurture_3.html.j2
    └── breakup.html.j2
```

---

## 3. Interface Definitions and Stubs

### 3.1 Layer 1: Core Interfaces

`**src/core/exceptions.py**` - Full exception hierarchy with docstrings:

```python
"""IronLung 3 Exception Hierarchy.

All custom exceptions inherit from IronLungError.
DNCViolationError is its own class because DNC violations
are categorically different from other pipeline errors.
"""

class IronLungError(Exception):
    """Base exception for all IronLung errors."""
    pass

class ConfigurationError(IronLungError):
    """Configuration is invalid or missing."""
    pass

class ValidationError(IronLungError):
    """Data validation failed."""
    pass

class DatabaseError(IronLungError):
    """Database operation failed."""
    pass

# ... full hierarchy from Blueprint lines 291-293
```

`**src/db/models.py**` - All enums and dataclasses with type hints:

```python
"""Data models and enumerations for IronLung 3.

All enums stored as TEXT in SQLite.
Dataclasses use frozen=False for mutability during processing.
"""
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Optional, List, Dict, Any

class Population(str, Enum):
    """Where a prospect lives in the pipeline."""
    BROKEN = "broken"
    UNENGAGED = "unengaged"
    ENGAGED = "engaged"
    # ... full enum from Schema Spec

@dataclass
class Company:
    """A company record."""
    id: Optional[int] = None
    name: str = ""
    name_normalized: str = ""
    # ... full definition from Schema Spec
```

### 3.2 Layer 2: Integration Base Classes

`**src/integrations/base.py**` - Abstract base for all integrations:

```python
"""Base classes for external integrations.

All integrations inherit from IntegrationBase, which provides:
- Health check interface
- Rate limiting
- Error handling with retry
- Logging patterns
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class IntegrationBase(ABC):
    """Abstract base class for all external integrations."""

    @abstractmethod
    def health_check(self) -> bool:
        """Return True if integration is healthy and available."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if required credentials are present."""
        pass
```

### 3.3 Layer 3: Engine Interfaces

`**src/engine/populations.py**` - Population transition contract:

```python
"""Population management and transition rules.

Valid transitions defined in VALID_TRANSITIONS.
DNC is terminal - no transitions out, ever.
"""
from typing import Set, Tuple
from src.db.models import Population, EngagementStage

# Explicit valid transitions
VALID_TRANSITIONS: Set[Tuple[Population, Population]] = {
    (Population.BROKEN, Population.UNENGAGED),
    (Population.UNENGAGED, Population.BROKEN),
    (Population.UNENGAGED, Population.ENGAGED),
    # ... full set from Blueprint lines 362-388
}

def can_transition(from_pop: Population, to_pop: Population) -> bool:
    """Check if a population transition is valid."""
    raise NotImplementedError("Phase 2")

def transition_prospect(prospect_id: int, to_population: Population,
                       reason: str = None) -> bool:
    """Execute a population transition with full logging."""
    raise NotImplementedError("Phase 2")
```

### 3.4 Layer 4: GUI Contracts

`**src/gui/tabs/__init__.py**` - Tab interface:

```python
"""Tab interface contract.

All tabs inherit from TabBase and implement:
- refresh() - reload data
- on_activate() - called when tab becomes visible
- on_deactivate() - called when leaving tab
"""
from abc import ABC, abstractmethod
import tkinter as tk

class TabBase(ABC):
    """Abstract base class for all tabs."""

    @abstractmethod
    def refresh(self) -> None:
        """Reload tab data from database."""
        pass

    @abstractmethod
    def on_activate(self) -> None:
        """Called when this tab becomes visible."""
        pass
```

### 3.5 Layers 5-7: AI, Autonomous, ADHD Interfaces

Similar stub files with docstrings and `raise NotImplementedError("Phase N")` for all methods.

---

## 4. Engineering Patterns Documentation

### 4.1 Logging Specification (`docs/patterns/LOGGING-SPEC.md`)

Define:

- JSON format with timestamp, level, module, message, context
- Log levels: DEBUG (file only), INFO (console + file), WARNING, ERROR, CRITICAL
- Context fields: prospect_id, company_id, activity_type, user_action
- Rotation: 10MB files, keep 5
- Location: `~/.ironlung/logs/`

### 4.2 Configuration Specification (`docs/patterns/CONFIG-SPEC.md`)

Define:

- All environment variables with defaults
- `.env` file format
- Settings hierarchy (env vars override file, file overrides defaults)
- Validation rules
- Sensitive value handling (never log API keys)

### 4.3 Error Handling Patterns (`docs/patterns/ERROR-HANDLING.md`)

Define:

- Exception hierarchy usage
- Retry strategies (exponential backoff for network)
- User-facing error messages
- Recovery strategies per error type
- DNC violation handling (always raise, never swallow)

### 4.4 Testing Patterns (`docs/patterns/TESTING-PATTERNS.md`)

Define:

- Fixture organization in conftest.py
- Factory functions for test data
- In-memory database setup
- Mocking external services
- Performance test patterns

---

## 5. Shared Test Fixtures

`**tests/conftest.py**` - Comprehensive fixtures:

```python
"""Shared test fixtures for IronLung 3.

All tests use in-memory SQLite - never touch real database.
Factory functions create consistent test data.
"""
import pytest
from typing import Generator
from src.db.database import Database
from src.db.models import Company, Prospect, Population

@pytest.fixture
def db() -> Generator[Database, None, None]:
    """In-memory database for testing."""
    database = Database(":memory:")
    database.initialize()
    yield database
    database.close()

@pytest.fixture
def sample_company() -> Company:
    """A complete company for testing."""
    return Company(
        name="ABC Lending, LLC",
        domain="abclending.com",
        state="TX",
        # ... complete fixture
    )

@pytest.fixture
def sample_prospect(sample_company: Company) -> Prospect:
    """A complete prospect for testing."""
    return Prospect(
        first_name="John",
        last_name="Smith",
        population=Population.UNENGAGED,
        # ... complete fixture
    )

# Factory functions for bulk test data
def prospect_factory(count: int, population: Population = Population.UNENGAGED) -> list[Prospect]:
    """Generate multiple prospects for performance testing."""
    raise NotImplementedError("Phase 1")
```

---

## 6. Deliverables Checklist

After completing this scaffolding:

- All 60+ source files exist as stubs with docstrings and type hints
- All 30+ test files exist with placeholder test functions
- All 15+ documentation files created
- `pyproject.toml` configured for modern Python tooling
- `requirements.txt` and `requirements-dev.txt` with pinned versions
- `conftest.py` with all shared fixtures
- `.gitignore` complete
- `pytest` runs successfully (all tests skip or pass trivially)
- `mypy src/` passes with no errors
- `black --check src/` passes
- Entry point `ironlung3.py` runs and prints startup message

This gives you a complete skeleton where Phase 1 implementation is filling in function bodies, not creating structure.

---

## Implementation Order

1. Create documentation structure (`docs/` hierarchy)
2. Create root configuration files
3. Create source directory structure with `__init__.py` files
4. Create test directory structure
5. Populate Layer 1 stubs (core, db) - these are Phase 1 targets
6. Populate Layer 2-7 stubs with NotImplementedError
7. Create conftest.py with fixtures
8. Create pattern documentation
9. Verify tooling (pytest, mypy, black all pass)
10. Initial git commit: "Project scaffolding complete"
