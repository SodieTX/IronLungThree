# Logging Pattern

## Overview

IronLung 3 uses structured JSON logging for machine-readable logs and human-friendly console output.

## Configuration

```python
from src.core.logging import setup_logging, get_logger

# Initialize at startup (once)
setup_logging(log_path="logs/")

# Get logger in each module
logger = get_logger(__name__)
```

## Log Levels

| Level | When to Use |
|-------|-------------|
| DEBUG | Detailed diagnostic information |
| INFO | Normal operation events (startup, major actions) |
| WARNING | Unexpected but recoverable situations |
| ERROR | Failures that prevent operation completion |
| CRITICAL | System-wide failures requiring immediate attention |

## Structured Fields

Always include relevant context:

```python
# Good
logger.info("Prospect updated", extra={
    "prospect_id": prospect.id,
    "old_population": old_pop.value,
    "new_population": new_pop.value,
})

# Bad
logger.info(f"Updated prospect {prospect.id} from {old_pop} to {new_pop}")
```

## Output Formats

### Console (Human-readable)
```
2026-02-05 09:15:23 INFO     [db.database] Connected to database
2026-02-05 09:15:24 WARNING  [engine.cadence] 3 orphaned engaged records
```

### File (JSON)
```json
{"timestamp": "2026-02-05T09:15:23.456Z", "level": "INFO", "logger": "db.database", "message": "Connected to database", "db_path": "data/ironlung.db"}
```

## Sensitive Data

Never log:
- Full email addresses (use `j***@company.com`)
- Phone numbers (use last 4 digits only)
- API keys or tokens
- Personal notes content

```python
# Good
logger.info("Email sent", extra={"recipient": mask_email(email)})

# Bad
logger.info(f"Email sent to {email}")
```

## Performance Logging

For operations >100ms:

```python
import time

start = time.time()
# ... operation ...
elapsed = time.time() - start

if elapsed > 0.1:
    logger.warning("Slow operation", extra={
        "operation": "database_query",
        "elapsed_ms": round(elapsed * 1000),
    })
```

## Error Logging

Always include exception info:

```python
try:
    # operation
except SomeError as e:
    logger.error("Operation failed", extra={
        "error_type": type(e).__name__,
        "error_message": str(e),
    }, exc_info=True)
```

## Log Rotation

- File logs rotate at 10MB
- Keep 5 backup files
- Automatic cleanup after 30 days

## See Also

- `src/core/logging.py` - Implementation
- `tests/test_core/test_logging.py` - Tests
