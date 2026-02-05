# Layer 1: The Slab

**Database, Models, Config, Logging, Exceptions**

Version: 1.0
Date: February 5, 2026
Parent: Blueprint v3.2

---

## Overview

Layer 1 is the foundation. Nothing above it works without it. Built first, never changes underneath other layers.

**Components:**
- SQLite Database (`db/database.py`)
- Data Models (`db/models.py`)
- Backup System (`db/backup.py`)
- Intake Funnel (`db/intake.py`)
- Configuration (`core/config.py`)
- Logging (`core/logging.py`)
- Exceptions (`core/exceptions.py`)
- Task Management (`core/tasks.py`)

---

## Database (`db/database.py`)

### Connection Management

- Single SQLite file at `~/.ironlung/ironlung3.db`
- WAL mode enabled for concurrent read/write
- Foreign keys enforced
- Connection pooling not needed (single-user desktop app)

### Core Functions

```python
def initialize() -> None:
    """Create all tables and indexes if they don't exist."""

def get_connection() -> sqlite3.Connection:
    """Return the database connection."""

def close() -> None:
    """Close the database connection cleanly."""
```

### Company Operations

```python
def create_company(company: Company) -> int:
    """Insert company, return ID. Auto-normalize name, auto-assign timezone."""

def get_company(company_id: int) -> Optional[Company]:
    """Get company by ID."""

def get_company_by_normalized_name(name: str) -> Optional[Company]:
    """Find company by normalized name for dedup."""

def update_company(company: Company) -> bool:
    """Update company fields. Returns True if updated."""

def search_companies(query: str) -> list[Company]:
    """Search companies by partial name (LIKE query)."""
```

### Prospect Operations

```python
def create_prospect(prospect: Prospect) -> int:
    """Insert prospect, return ID."""

def get_prospect(prospect_id: int) -> Optional[Prospect]:
    """Get prospect by ID (basic fields only)."""

def get_prospect_full(prospect_id: int) -> Optional[ProspectFull]:
    """Get prospect with company, contact methods, activities."""

def update_prospect(prospect: Prospect) -> bool:
    """Update prospect fields."""

def get_prospects(
    population: Optional[Population] = None,
    company_id: Optional[int] = None,
    state: Optional[str] = None,
    score_min: Optional[int] = None,
    score_max: Optional[int] = None,
    search_query: Optional[str] = None,
    sort_by: str = "prospect_score",
    sort_dir: str = "DESC",
    limit: int = 100,
    offset: int = 0
) -> list[Prospect]:
    """Get prospects with filtering and pagination."""

def get_population_counts() -> dict[Population, int]:
    """Return count of prospects in each population."""
```

### Contact Method Operations

```python
def create_contact_method(method: ContactMethod) -> int:
    """Add contact method to prospect."""

def get_contact_methods(prospect_id: int) -> list[ContactMethod]:
    """Get all contact methods for prospect, primary first."""

def update_contact_method(method: ContactMethod) -> bool:
    """Update contact method."""

def find_prospect_by_email(email: str) -> Optional[int]:
    """Find prospect ID by email (case-insensitive)."""

def find_prospect_by_phone(phone: str) -> Optional[int]:
    """Find prospect ID by phone (digits-only match)."""

def is_dnc(email: Optional[str] = None, phone: Optional[str] = None) -> bool:
    """Check if email or phone belongs to a DNC prospect."""
```

### Activity Operations

```python
def create_activity(activity: Activity) -> int:
    """Log an activity."""

def get_activities(prospect_id: int, limit: int = 50) -> list[Activity]:
    """Get activities for prospect, most recent first."""
```

### Bulk Operations

```python
def bulk_update_population(
    prospect_ids: list[int],
    population: Population,
    reason: str
) -> tuple[int, int]:
    """Update population for multiple prospects. Returns (updated, skipped_dnc)."""

def bulk_set_follow_up(prospect_ids: list[int], follow_up_date: datetime) -> int:
    """Set follow-up date for multiple prospects."""

def bulk_park(prospect_ids: list[int], parked_month: str) -> tuple[int, int]:
    """Park prospects in a month (YYYY-MM). Returns (parked, skipped_dnc)."""
```

---

## Data Models (`db/models.py`)

### Enumerations

All enums inherit from `str, Enum` for SQLite TEXT storage.

| Enum | Values | Purpose |
|------|--------|---------|
| Population | broken, unengaged, engaged, parked, dead_dnc, lost, partnership, closed_won | Pipeline location |
| EngagementStage | pre_demo, demo_scheduled, post_demo, closing | Within Engaged only |
| ActivityType | call, voicemail, email_sent, etc. | Activity classification |
| ActivityOutcome | no_answer, left_vm, spoke_with, etc. | Activity result |
| ContactMethodType | email, phone | Contact method type |
| AttemptType | personal, automated | Distinguishes Jeff from system |

### Dataclasses

All dataclasses use `frozen=False` for mutability during processing.

- **Company** - Company record with auto-normalized name
- **Prospect** - Contact with pipeline position and scoring
- **ContactMethod** - Email or phone with verification status
- **Activity** - Audit trail entry
- **ImportSource** - Import batch metadata
- **ResearchTask** - Broken prospect research queue entry
- **IntelNugget** - Extracted fact for call cheat sheet

### Utility Functions

```python
def normalize_company_name(name: str) -> str:
    """Strip legal suffixes (LLC, Inc, Corp). Preserve identity terms."""

def timezone_from_state(state: Optional[str]) -> str:
    """Return timezone for state. Default: 'central'."""

def assess_completeness(prospect: Prospect, methods: list[ContactMethod]) -> Population:
    """Return 'unengaged' if has email AND phone, else 'broken'."""
```

---

## Backup System (`db/backup.py`)

### Core Functions

```python
def create_backup(label: str = "manual") -> Path:
    """Create timestamped backup. Returns backup path."""

def list_backups() -> list[BackupInfo]:
    """List all backups, newest first."""

def restore_backup(backup_path: Path) -> bool:
    """Restore from backup. Creates safety backup first."""

def cleanup_old_backups(keep_days: int = 30) -> int:
    """Remove backups older than keep_days. Returns count removed."""

def sync_to_cloud() -> bool:
    """Copy latest backup to OneDrive sync folder."""
```

### Backup Naming

Format: `ironlung3_YYYYMMDD_HHMMSS_label.db`

Labels:
- `manual` - User-triggered
- `nightly` - Nightly cycle
- `pre_import` - Before bulk import
- `pre_restore` - Safety backup before restore

---

## Configuration (`core/config.py`)

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| IRONLUNG_DB_PATH | ~/.ironlung/ironlung3.db | Database location |
| IRONLUNG_LOG_PATH | ~/.ironlung/logs | Log directory |
| IRONLUNG_BACKUP_PATH | ~/.ironlung/backups | Backup directory |
| IRONLUNG_CLOUD_SYNC_PATH | ~/OneDrive/IronLung | Cloud sync destination |
| OUTLOOK_CLIENT_ID | (required for Phase 3) | Microsoft app ID |
| OUTLOOK_CLIENT_SECRET | (required for Phase 3) | Microsoft app secret |
| OUTLOOK_TENANT_ID | (required for Phase 3) | Microsoft tenant ID |
| CLAUDE_API_KEY | (required for Phase 4) | Anthropic API key |
| ACTIVECAMPAIGN_API_KEY | (optional) | ActiveCampaign API key |
| ACTIVECAMPAIGN_URL | (optional) | ActiveCampaign URL |

### Functions

```python
def load_config() -> Config:
    """Load config from environment and .env file."""

def validate_config() -> list[str]:
    """Validate config. Returns list of issues (empty = valid)."""

def get_config() -> Config:
    """Return cached config singleton."""
```

---

## Logging (`core/logging.py`)

### Format

JSON with fields:
- `timestamp` - ISO 8601
- `level` - DEBUG/INFO/WARNING/ERROR/CRITICAL
- `module` - Source module name
- `message` - Log message
- `context` - Optional dict with prospect_id, company_id, etc.

### Setup

```python
def setup_logging() -> None:
    """Initialize logging. Called once at startup."""

def get_logger(name: str) -> Logger:
    """Get logger for module."""
```

### Levels

- DEBUG - File only (verbose)
- INFO - Console + file (normal operations)
- WARNING - Console + file (recoverable issues)
- ERROR - Console + file (failures)
- CRITICAL - Console + file (unrecoverable)

---

## Exceptions (`core/exceptions.py`)

### Hierarchy

```
IronLungError (base)
├── ConfigurationError
├── ValidationError
├── DatabaseError
├── IntegrationError
│   ├── OutlookError
│   ├── BriaError
│   └── ActiveCampaignError
├── ImportError_
└── PipelineError
    └── DNCViolationError
```

### DNCViolationError

Special handling - never swallowed, always surfaced. Raised when:
- Attempting to transition FROM DNC
- Attempting to merge into DNC record
- Bulk operation includes DNC record (skipped, not raised)

---

## Performance Targets

| Operation | Target |
|-----------|--------|
| Database creation | < 1 second |
| Insert 500 prospects | < 2 seconds |
| get_prospects (100 records) | < 200ms |
| Search query (500 records) | < 200ms |
| Backup creation | < 5 seconds |

---

## Dependencies

- sqlite3 (stdlib)
- dataclasses (stdlib)
- enum (stdlib)
- pathlib (stdlib)
- json (stdlib)
- logging (stdlib)
- os (stdlib)
- shutil (stdlib)

No external dependencies for Layer 1 core. Only `openpyxl` for XLSX import support.

---

## Build Phases

- **Phase 1**: Full implementation (Steps 1.1-1.11)
- **Phase 2+**: No changes expected

---

**See also:**
- `SCHEMA-SPEC.md` - Complete DDL
- `../build/PHASE-1-SLAB.md` - Build steps and tests
- `../patterns/LOGGING-SPEC.md` - Logging details
- `../patterns/CONFIG-SPEC.md` - Configuration details
