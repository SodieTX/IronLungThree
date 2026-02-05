"""Configuration management for IronLung 3.

Loads configuration from environment variables and .env file.
Provides validation and sensible defaults.

Usage:
    from src.core.config import get_config, validate_config

    config = get_config()
    issues = validate_config(config)
    if issues:
        for issue in issues:
            print(f"Config issue: {issue}")
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.core.exceptions import ConfigurationError


@dataclass
class Config:
    """Application configuration.

    Attributes:
        db_path: Path to SQLite database file
        log_path: Directory for log files
        backup_path: Directory for database backups
        cloud_sync_path: OneDrive sync directory (optional)
        outlook_client_id: Microsoft Graph client ID (Phase 3)
        outlook_client_secret: Microsoft Graph client secret (Phase 3)
        outlook_tenant_id: Microsoft Graph tenant ID (Phase 3)
        claude_api_key: Anthropic Claude API key (Phase 4)
        activecampaign_api_key: ActiveCampaign API key (Phase 5)
        activecampaign_url: ActiveCampaign API URL (Phase 5)
        google_api_key: Google Custom Search API key (Phase 5)
        google_cx: Google Custom Search Engine ID (Phase 5)
        debug: Enable debug mode
        dry_run: Log but don't send emails
    """

    db_path: Path = field(default_factory=lambda: Path.home() / ".ironlung" / "ironlung3.db")
    log_path: Path = field(default_factory=lambda: Path.home() / ".ironlung" / "logs")
    backup_path: Path = field(default_factory=lambda: Path.home() / ".ironlung" / "backups")
    cloud_sync_path: Optional[Path] = field(
        default_factory=lambda: Path.home() / "OneDrive" / "IronLung"
    )

    # Phase 3: Outlook
    outlook_client_id: Optional[str] = None
    outlook_client_secret: Optional[str] = None
    outlook_tenant_id: Optional[str] = None
    outlook_user_email: Optional[str] = None

    # Phase 4: Claude
    claude_api_key: Optional[str] = None

    # Phase 5: ActiveCampaign
    activecampaign_api_key: Optional[str] = None
    activecampaign_url: Optional[str] = None

    # Phase 5: Google Custom Search
    google_api_key: Optional[str] = None
    google_cx: Optional[str] = None

    # Feature flags
    debug: bool = False
    dry_run: bool = False


def load_env_file(path: Path) -> dict[str, str]:
    """Parse .env file.

    Handles:
        - KEY=VALUE format
        - Comments (lines starting with #)
        - Blank lines
        - Quoted values

    Args:
        path: Path to .env file

    Returns:
        Dictionary of environment variables
    """
    env_vars: dict[str, str] = {}

    if not path.exists():
        return env_vars

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            # Skip blank lines and comments
            if not line or line.startswith("#"):
                continue

            # Parse KEY=VALUE
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()

                # Remove quotes if present
                if value and value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]

                if key:
                    env_vars[key] = value

    return env_vars


def _get_path(key: str, default: Path, env_vars: dict[str, str]) -> Path:
    """Get path from environment, expanding ~ and resolving."""
    value = os.environ.get(key) or env_vars.get(key)
    if value:
        return Path(value).expanduser().resolve()
    return default


def _get_optional_path(
    key: str, default: Optional[Path], env_vars: dict[str, str]
) -> Optional[Path]:
    """Get optional path from environment."""
    value = os.environ.get(key) or env_vars.get(key)
    if value:
        return Path(value).expanduser().resolve()
    return default


def _get_str(key: str, env_vars: dict[str, str]) -> Optional[str]:
    """Get string from environment."""
    return os.environ.get(key) or env_vars.get(key) or None


def _get_bool(key: str, default: bool, env_vars: dict[str, str]) -> bool:
    """Get boolean from environment."""
    value = os.environ.get(key) or env_vars.get(key)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes", "on")


# Default paths (defined once, used by both Config and load_config)
DEFAULT_DB_PATH = Path.home() / ".ironlung" / "ironlung3.db"
DEFAULT_LOG_PATH = Path.home() / ".ironlung" / "logs"
DEFAULT_BACKUP_PATH = Path.home() / ".ironlung" / "backups"
DEFAULT_CLOUD_SYNC_PATH = Path.home() / "OneDrive" / "IronLung"


def load_config(env_file: Optional[Path] = None) -> Config:
    """Load configuration from environment and .env file.

    Priority:
        1. Environment variables (highest)
        2. .env file
        3. Default values (lowest)

    Args:
        env_file: Path to .env file. Defaults to .env in current directory.

    Returns:
        Loaded configuration
    """
    if env_file is None:
        env_file = Path.cwd() / ".env"

    env_vars = load_env_file(env_file)

    return Config(
        db_path=_get_path("IRONLUNG_DB_PATH", DEFAULT_DB_PATH, env_vars),
        log_path=_get_path("IRONLUNG_LOG_PATH", DEFAULT_LOG_PATH, env_vars),
        backup_path=_get_path("IRONLUNG_BACKUP_PATH", DEFAULT_BACKUP_PATH, env_vars),
        cloud_sync_path=_get_optional_path(
            "IRONLUNG_CLOUD_SYNC_PATH", DEFAULT_CLOUD_SYNC_PATH, env_vars
        ),
        outlook_client_id=_get_str("OUTLOOK_CLIENT_ID", env_vars),
        outlook_client_secret=_get_str("OUTLOOK_CLIENT_SECRET", env_vars),
        outlook_tenant_id=_get_str("OUTLOOK_TENANT_ID", env_vars),
        outlook_user_email=_get_str("OUTLOOK_USER_EMAIL", env_vars),
        claude_api_key=_get_str("CLAUDE_API_KEY", env_vars),
        activecampaign_api_key=_get_str("ACTIVECAMPAIGN_API_KEY", env_vars),
        activecampaign_url=_get_str("ACTIVECAMPAIGN_URL", env_vars),
        google_api_key=_get_str("GOOGLE_API_KEY", env_vars),
        google_cx=_get_str("GOOGLE_CX", env_vars),
        debug=_get_bool("IRONLUNG_DEBUG", False, env_vars),
        dry_run=_get_bool("IRONLUNG_DRY_RUN", False, env_vars),
    )


def validate_config(config: Config) -> list[str]:
    """Validate configuration.

    Checks:
        - Required paths exist or can be created
        - Paths are writable
        - Credential combinations are complete

    Args:
        config: Configuration to validate

    Returns:
        List of issues (empty if valid)
    """
    issues: list[str] = []

    # Check database directory
    db_dir = config.db_path.parent
    try:
        db_dir.mkdir(parents=True, exist_ok=True)
        if not os.access(db_dir, os.W_OK):
            issues.append(f"Database directory not writable: {db_dir}")
    except OSError as e:
        issues.append(f"Cannot create database directory {db_dir}: {e}")

    # Check log directory
    try:
        config.log_path.mkdir(parents=True, exist_ok=True)
        if not os.access(config.log_path, os.W_OK):
            issues.append(f"Log directory not writable: {config.log_path}")
    except OSError as e:
        issues.append(f"Cannot create log directory {config.log_path}: {e}")

    # Check backup directory
    try:
        config.backup_path.mkdir(parents=True, exist_ok=True)
        if not os.access(config.backup_path, os.W_OK):
            issues.append(f"Backup directory not writable: {config.backup_path}")
    except OSError as e:
        issues.append(f"Cannot create backup directory {config.backup_path}: {e}")

    # Check cloud sync (optional - just warn if missing)
    if config.cloud_sync_path and not config.cloud_sync_path.exists():
        issues.append(
            f"Cloud sync directory does not exist: {config.cloud_sync_path} (OneDrive may not be installed)"
        )

    # Check Outlook credentials (Phase 3 - all or none)
    outlook_creds = {
        "OUTLOOK_CLIENT_ID": config.outlook_client_id,
        "OUTLOOK_CLIENT_SECRET": config.outlook_client_secret,
        "OUTLOOK_TENANT_ID": config.outlook_tenant_id,
    }
    present = [k for k, v in outlook_creds.items() if v]
    missing = [k for k, v in outlook_creds.items() if not v]

    if present and missing:
        issues.append(
            f"CRITICAL: Partial Outlook credentials will cause auth failures. "
            f"Have: {', '.join(present)}. Missing: {', '.join(missing)}. "
            f"Provide all four Outlook variables or remove them entirely."
        )
    if all(outlook_creds.values()) and not config.outlook_user_email:
        issues.append(
            "CRITICAL: Outlook credentials present but OUTLOOK_USER_EMAIL is missing. "
            "Email send/receive will fail."
        )

    # Check ActiveCampaign credentials (Phase 5 - all or none)
    ac_creds = {
        "ACTIVECAMPAIGN_API_KEY": config.activecampaign_api_key,
        "ACTIVECAMPAIGN_URL": config.activecampaign_url,
    }
    ac_present = [k for k, v in ac_creds.items() if v]
    ac_missing = [k for k, v in ac_creds.items() if not v]

    if ac_present and ac_missing:
        issues.append(
            f"Partial ActiveCampaign credentials. "
            f"Have: {', '.join(ac_present)}. Missing: {', '.join(ac_missing)}."
        )

    # Check Google Search credentials (Phase 5 - all or none)
    google_creds = {
        "GOOGLE_API_KEY": config.google_api_key,
        "GOOGLE_CX": config.google_cx,
    }
    google_present = [k for k, v in google_creds.items() if v]
    google_missing = [k for k, v in google_creds.items() if not v]

    if google_present and google_missing:
        issues.append(
            f"Partial Google Search credentials. "
            f"Have: {', '.join(google_present)}. Missing: {', '.join(google_missing)}."
        )

    return issues


# Singleton config
_config: Optional[Config] = None


def get_config() -> Config:
    """Return cached configuration singleton.

    Loads configuration on first call, returns cached version thereafter.

    Returns:
        Application configuration
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reset_config() -> None:
    """Reset cached configuration.

    Used primarily for testing.
    """
    global _config
    _config = None
