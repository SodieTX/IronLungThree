# Configuration Pattern

## Overview

IronLung 3 uses environment variables for configuration, with a hierarchical loading order.

## Loading Order (Highest to Lowest Priority)

1. Environment variables
2. `.env` file in workspace root
3. Default values

## Configuration Sources

### Environment Variables

```bash
# Core paths
IRONLUNG_DB_PATH=data/ironlung.db
IRONLUNG_BACKUP_PATH=backups/
IRONLUNG_LOG_PATH=logs/
IRONLUNG_DATA_PATH=data/

# Debug mode
IRONLUNG_DEBUG=false

# Integration credentials
OUTLOOK_CLIENT_ID=xxx
OUTLOOK_CLIENT_SECRET=xxx
OUTLOOK_TENANT_ID=xxx

CLAUDE_API_KEY=xxx

ACTIVECAMPAIGN_URL=https://xxx.api-us1.com
ACTIVECAMPAIGN_API_KEY=xxx

# Feature flags
FEATURE_AUTONOMOUS_RESEARCH=true
FEATURE_NURTURE_SEQUENCES=true
```

### .env File

Create `.env` from `.env.example`:

```bash
cp .env.example .env
# Edit with your values
```

**Never commit `.env` to git** - it contains secrets.

## Usage in Code

```python
from src.core.config import get_config

# Get singleton config
config = get_config()

# Access values
db_path = config.db_path
debug = config.debug_mode

# Check credentials
if config.outlook_client_id:
    # Outlook is configured
    pass
```

## Validation

Config is validated at startup:

```python
from src.core.config import load_config, validate_config

config = load_config()
errors = validate_config(config)
if errors:
    for error in errors:
        print(f"Config error: {error}")
    sys.exit(1)
```

### Validation Rules

| Check | Requirement |
|-------|-------------|
| db_path | Parent directory exists and is writable |
| backup_path | Directory exists or can be created |
| log_path | Directory exists or can be created |
| Outlook credentials | All three (client_id, secret, tenant) or none |
| API keys | Non-empty if feature enabled |

## Adding New Config Values

1. Add to `Config` dataclass in `src/core/config.py`
2. Add environment variable name to `load_config()`
3. Add validation if needed
4. Update `.env.example` with example/description
5. Update this document

## Feature Flags

Feature flags enable/disable optional functionality:

```python
if config.feature_autonomous_research:
    research_engine.run_batch()
```

Use for:
- Features under development
- Features requiring external services
- Features Jeff may want to disable

## Secrets Management

Credentials are never:
- Logged (even at DEBUG level)
- Included in error messages
- Stored in database
- Exported to files

## See Also

- `src/core/config.py` - Implementation
- `.env.example` - Example configuration
- `tests/test_core/test_config.py` - Tests
