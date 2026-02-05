# Error Handling Pattern

## Overview

IronLung 3 uses a custom exception hierarchy for domain-specific errors, with special treatment for DNC violations.

## Exception Hierarchy

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

## Usage

### Raising Exceptions

```python
from src.core.exceptions import ValidationError, DNCViolationError

def set_follow_up(prospect, date):
    if date < datetime.now():
        raise ValidationError(f"Follow-up date must be in future: {date}")

    if prospect.population == Population.DNC:
        raise DNCViolationError(f"Cannot set follow-up for DNC: {prospect.id}")
```

### Catching Exceptions

```python
from src.core.exceptions import IronLungError, DatabaseError

try:
    db.save_prospect(prospect)
except DatabaseError as e:
    logger.error("Database save failed", extra={"error": str(e)})
    # Handle database-specific recovery
except IronLungError as e:
    logger.error("Operation failed", extra={"error": str(e)})
    # Handle general error
```

## DNC Violation Handling

**DNCViolationError is NEVER swallowed.** It must always propagate up and be visible.

```python
# WRONG - Never do this
try:
    transition_prospect(prospect, new_population)
except DNCViolationError:
    pass  # Silently ignored

# RIGHT - Let it propagate or handle explicitly
try:
    transition_prospect(prospect, new_population)
except DNCViolationError as e:
    logger.critical("DNC violation attempted!", extra={
        "prospect_id": prospect.id,
        "error": str(e),
    })
    show_error_dialog("Cannot modify DNC record")
    raise  # Re-raise for audit trail
```

## Error Messages

### For Users (GUI)

- Clear and actionable
- No technical jargon
- Suggest next steps

```python
# Good
"Could not connect to Outlook. Check your internet connection and try again."

# Bad
"OutlookError: OAuth2 token refresh failed with status 401"
```

### For Logs (Technical)

- Include context
- Include exception chain
- Include relevant IDs

```python
logger.error("Outlook connection failed", extra={
    "error_type": type(e).__name__,
    "status_code": getattr(e, 'status_code', None),
    "retry_count": retry_count,
}, exc_info=True)
```

## Retry Pattern

For transient failures:

```python
from src.integrations.base import with_retry

@with_retry(max_attempts=3, delay=1.0, backoff=2.0)
def fetch_emails():
    return outlook.get_recent_emails()
```

Retry when:
- Network timeouts
- Rate limiting (429)
- Server errors (5xx)

Don't retry when:
- Authentication failures (401, 403)
- Validation errors
- DNC violations

## Graceful Degradation

When external services fail, degrade gracefully:

```python
def get_prospect_data(prospect_id):
    prospect = db.get_prospect(prospect_id)

    try:
        prospect.ai_insights = ai.get_insights(prospect)
    except IntegrationError:
        prospect.ai_insights = None  # Continue without AI
        logger.warning("AI insights unavailable", extra={
            "prospect_id": prospect_id,
        })

    return prospect
```

## Crash Recovery

Session state is saved periodically for crash recovery:

```python
from src.gui.adhd.session import save_session_state

# Called after each card disposition
save_session_state()
```

On restart, user can resume from saved state.

## See Also

- `src/core/exceptions.py` - Exception definitions
- `src/integrations/base.py` - Retry decorator
- `tests/test_core/test_exceptions.py` - Tests
