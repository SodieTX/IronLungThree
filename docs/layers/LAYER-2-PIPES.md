# Layer 2: The Pipes

**External Integrations**

Version: 1.0  
Date: February 5, 2026  
Parent: Blueprint v3.2

---

## Overview

Layer 2 handles all communication with the outside world. Each integration is independent - none depend on each other.

**Components:**
- Integration Base (`integrations/base.py`)
- Outlook Client (`integrations/outlook.py`)
- Bria Dialer (`integrations/bria.py`)
- ActiveCampaign Client (`integrations/activecampaign.py`)
- Google Custom Search (`integrations/google_search.py`)
- CSV/XLSX Importer (`integrations/csv_importer.py`)
- Email CSV Importer (`integrations/email_importer.py`)

---

## Integration Base (`integrations/base.py`)

All integrations inherit from `IntegrationBase`.

### Interface

```python
class IntegrationBase(ABC):
    @abstractmethod
    def health_check(self) -> bool:
        """Return True if integration is healthy."""
    
    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if required credentials are present."""
    
    def with_retry(self, func: Callable, max_retries: int = 3) -> Any:
        """Execute function with exponential backoff retry."""
```

### Patterns

- **Health checks**: Called on startup and periodically
- **Rate limiting**: Per-integration, respects API limits
- **Error handling**: Raises `IntegrationError` subclass
- **Logging**: All operations logged with context

---

## Outlook Client (`integrations/outlook.py`)

Microsoft Graph API integration for email and calendar.

### Authentication

- OAuth2 with CLIENT_ID, CLIENT_SECRET, TENANT_ID
- Token refresh handled automatically
- Token stored in config directory

### Email Operations

```python
def send_email(
    to: str,
    subject: str,
    body: str,
    html: bool = False
) -> str:
    """Send email. Returns message ID."""

def create_draft(
    to: str,
    subject: str,
    body: str,
    html: bool = False
) -> str:
    """Create draft email. Returns draft ID."""

def get_inbox(since: datetime = None, limit: int = 50) -> list[EmailMessage]:
    """Get inbox messages. Polls every 30 minutes."""

def classify_reply(message: EmailMessage) -> ReplyClassification:
    """Classify reply: interested, not_interested, ooo, referral, unknown."""
```

### Calendar Operations

```python
def create_event(
    subject: str,
    start: datetime,
    duration_minutes: int = 30,
    attendees: list[str] = None,
    teams_meeting: bool = False
) -> str:
    """Create calendar event. Returns event ID."""

def get_events(start: datetime, end: datetime) -> list[CalendarEvent]:
    """Get events in date range."""

def update_event(event_id: str, **kwargs) -> bool:
    """Update event fields."""

def delete_event(event_id: str) -> bool:
    """Delete event."""
```

### Limitations

- Polling, not webhooks (desktop app can't receive push)
- Poll frequency: 30 minutes (configurable)
- No email recall (Outlook limitation for external recipients)

---

## Bria Dialer (`integrations/bria.py`)

Click-to-call through Bria softphone.

### Operations

```python
def dial(phone_number: str) -> bool:
    """Initiate call via Bria. Returns True if launched."""

def is_available() -> bool:
    """Check if Bria is installed and running."""
```

### Implementation

- Uses `tel:` or `sip:` URI scheme
- Falls back to clipboard copy if Bria unavailable
- Falls back to clipboard copy if offline

### Offline Behavior

When internet unavailable:
- `is_available()` returns False
- `dial()` copies number to clipboard
- UI shows "Copied to clipboard" instead of "Dialing..."

---

## ActiveCampaign Client (`integrations/activecampaign.py`)

Pull new prospects from AC pipelines.

### Operations

```python
def get_contacts(
    pipeline_id: Optional[int] = None,
    since: datetime = None
) -> list[ACContact]:
    """Get contacts from ActiveCampaign."""

def get_pipelines() -> list[ACPipeline]:
    """List available pipelines."""
```

### Usage

- Automated pull during nightly cycle
- Manual pull from Import tab
- Respects API rate limits

---

## Google Custom Search (`integrations/google_search.py`)

Free tier search for autonomous research.

### Operations

```python
def search(query: str, num_results: int = 10) -> list[SearchResult]:
    """Execute Google search. Free tier: 100 queries/day."""

def get_remaining_quota() -> int:
    """Return remaining searches for today."""
```

### Limitations

- 100 queries/day on free tier
- Used sparingly by autonomous research
- Prioritize company website scraping first

---

## CSV/XLSX Importer (`integrations/csv_importer.py`)

File import with column mapping.

### Operations

```python
def parse_file(path: Path) -> ParseResult:
    """Parse CSV or XLSX. Returns headers and sample rows."""

def detect_preset(headers: list[str]) -> Optional[str]:
    """Detect known format: 'phoneburner', 'aapl', or None."""

def apply_mapping(
    path: Path,
    mapping: dict[str, str],
    preset: Optional[str] = None
) -> list[ImportRecord]:
    """Apply column mapping, return normalized records."""
```

### Presets

| Preset | Source | Key Columns |
|--------|--------|-------------|
| phoneburner | PhoneBurner export | First Name, Last Name, Email, Phone, Company |
| aapl | AAPL directory | Contact Name, Email Address, Phone Number, Organization |

### Normalization

- Full name split: "John Smith" → first="John", last="Smith"
- Phone: "(713) 555-1234" → "7135551234"
- Email: "JOHN@ABC.COM" → "john@abc.com"
- Whitespace trimmed from all fields

### Error Handling

- Non-UTF8 files: try latin-1, then cp1252, then error
- Missing columns: mapping UI shows unmapped
- Zero data rows: return empty with message
- XLSX without openpyxl: clear install message

---

## Email CSV Importer (`integrations/email_importer.py`)

Import Outlook email exports to enrich cards.

### Operations

```python
def import_emails(path: Path) -> ImportResult:
    """Import email CSV. Match to prospects by email address."""
```

### Purpose

- Available before Graph API (Phase 3)
- Enriches prospect cards with email history
- Creates activity records for each email

### Matching

- Match sender/recipient email to contact_methods
- Create activity with email_subject, email_body, date
- Mark direction (sent/received)

---

## Build Phases

- **Phase 1**: CSV importer only (Steps 1.12-1.13)
- **Phase 3**: Outlook, Bria (Steps 3.1-3.3)
- **Phase 5**: ActiveCampaign, Google Search (Steps 5.1, 5.7)

---

## Performance Targets

| Operation | Target |
|-----------|--------|
| Parse 500-row CSV | < 2 seconds |
| Outlook send email | < 5 seconds |
| Bria dial launch | < 1 second |

---

**See also:**
- `../patterns/ERROR-HANDLING.md` - Retry strategies
- `../build/PHASE-1-SLAB.md` - CSV importer build steps
- `../build/PHASE-3-COMMUNICATOR.md` - Outlook/Bria build steps
