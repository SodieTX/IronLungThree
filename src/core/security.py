"""Security utilities for IronLung 3.

Provides:
    - Secure file creation with restricted permissions
    - Sensitive data redaction for logging
    - Input validation for URLs and file paths
    - API key format validation

All file operations that handle secrets, PII, or credentials should
use these helpers instead of raw open()/Path.write_text().
"""

import os
import re
import stat
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# File permission helpers
# ---------------------------------------------------------------------------

# Owner-only read/write (0600)
_FILE_MODE_OWNER_RW = stat.S_IRUSR | stat.S_IWUSR

# Owner-only read/write/execute for directories (0700)
_DIR_MODE_OWNER_RWX = stat.S_IRWXU


def secure_write_file(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write a file with owner-only permissions (0600).

    Creates parent directories with 0700 permissions if they don't exist.

    Args:
        path: Path to write to
        content: File content
        encoding: Text encoding (default utf-8)
    """
    path = Path(path)
    # Create parent directories with restricted permissions
    secure_mkdir(path.parent)

    # Save old umask and set restrictive umask
    old_umask = os.umask(0o077)
    try:
        with open(path, "w", encoding=encoding) as f:
            f.write(content)
        # Explicitly set permissions in case file already existed
        os.chmod(path, _FILE_MODE_OWNER_RW)
    finally:
        os.umask(old_umask)


def secure_mkdir(path: Path) -> None:
    """Create a directory with owner-only permissions (0700).

    Args:
        path: Directory to create (parents created as needed)
    """
    path = Path(path)
    if path.exists():
        return
    old_umask = os.umask(0o077)
    try:
        path.mkdir(parents=True, exist_ok=True)
    finally:
        os.umask(old_umask)


def restrict_permissions(path: Path) -> None:
    """Restrict an existing file or directory to owner-only access.

    Args:
        path: Path to restrict
    """
    path = Path(path)
    if not path.exists():
        return

    if path.is_dir():
        os.chmod(path, _DIR_MODE_OWNER_RWX)
    else:
        os.chmod(path, _FILE_MODE_OWNER_RW)


# ---------------------------------------------------------------------------
# Sensitive data redaction
# ---------------------------------------------------------------------------

# Patterns that look like API keys or secrets
_SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_-]+"),  # Anthropic API key
    re.compile(r"[A-Za-z0-9]{32,}"),  # Generic long tokens (32+ chars)
]

# Fields whose values should be redacted in logs
SENSITIVE_LOG_FIELDS = frozenset(
    {
        "api_key",
        "api_token",
        "access_token",
        "client_secret",
        "password",
        "token",
        "secret",
        "credential",
        "authorization",
    }
)


def redact_api_key(key: Optional[str]) -> str:
    """Redact an API key for safe logging, showing only last 4 chars.

    Args:
        key: API key to redact

    Returns:
        Redacted string like "sk-...ab12" or "<not set>"
    """
    if not key:
        return "<not set>"
    if len(key) <= 8:
        return "****"
    return f"{key[:3]}...{key[-4:]}"


def redact_email(email: Optional[str]) -> str:
    """Redact an email address for safe logging.

    "john.doe@example.com" -> "j***e@example.com"

    Args:
        email: Email to redact

    Returns:
        Redacted email or "<not set>"
    """
    if not email or "@" not in email:
        return "<redacted>"
    local, domain = email.rsplit("@", 1)
    if len(local) <= 2:
        redacted_local = "*" * len(local)
    else:
        redacted_local = f"{local[0]}***{local[-1]}"
    return f"{redacted_local}@{domain}"


# ---------------------------------------------------------------------------
# URL validation (SSRF prevention)
# ---------------------------------------------------------------------------

# Allowed hostnames/domains for each integration
_ALLOWED_DOMAINS: dict[str, list[str]] = {
    "activecampaign": [".api-us1.com", ".api-us2.com", ".activehosted.com"],
    "microsoft_graph": ["graph.microsoft.com", "login.microsoftonline.com"],
    "google_search": ["www.googleapis.com", "googleapis.com"],
    "anthropic": ["api.anthropic.com"],
}

# Private/internal IP ranges that should never be target of API calls
_BLOCKED_IP_PATTERNS = [
    re.compile(r"^127\."),  # Loopback
    re.compile(r"^10\."),  # RFC1918
    re.compile(r"^172\.(1[6-9]|2\d|3[01])\."),  # RFC1918
    re.compile(r"^192\.168\."),  # RFC1918
    re.compile(r"^169\.254\."),  # Link-local
    re.compile(r"^0\."),  # Current network
    re.compile(r"^::1$"),  # IPv6 loopback
    re.compile(r"^fc00:"),  # IPv6 unique local
    re.compile(r"^fe80:"),  # IPv6 link-local
]


def validate_api_url(url: str, integration: Optional[str] = None) -> str:
    """Validate an API URL to prevent SSRF attacks.

    Checks:
        - URL uses HTTPS (unless localhost for testing)
        - Hostname is not a private/internal IP
        - If integration is specified, hostname matches allowed domains

    Args:
        url: URL to validate
        integration: Integration name for domain allowlist check

    Returns:
        Validated URL (stripped of trailing whitespace)

    Raises:
        ValueError: If URL is invalid or fails security checks
    """
    url = url.strip()
    if not url:
        raise ValueError("URL is empty")

    parsed = urlparse(url)

    # Must have a scheme
    if not parsed.scheme:
        raise ValueError(f"URL missing scheme (http/https): {url}")

    # Require HTTPS for all external APIs
    if parsed.scheme != "https":
        raise ValueError(f"API URLs must use HTTPS, got: {parsed.scheme}")

    hostname = parsed.hostname or ""
    if not hostname:
        raise ValueError(f"URL has no hostname: {url}")

    # Block private/internal IPs
    for pattern in _BLOCKED_IP_PATTERNS:
        if pattern.match(hostname):
            raise ValueError(f"API URL must not target private/internal addresses: {hostname}")

    # Block localhost
    if hostname in ("localhost", "0.0.0.0"):
        raise ValueError(f"API URL must not target localhost: {hostname}")

    # If integration specified, check against allowed domains
    if integration and integration in _ALLOWED_DOMAINS:
        allowed = _ALLOWED_DOMAINS[integration]
        if not any(hostname == d or hostname.endswith(d) for d in allowed):
            raise ValueError(
                f"URL hostname '{hostname}' not in allowed domains for " f"{integration}: {allowed}"
            )

    return url


# ---------------------------------------------------------------------------
# Path traversal prevention
# ---------------------------------------------------------------------------


def validate_safe_path(path: Path, allowed_parent: Path) -> Path:
    """Validate that a path is within the allowed parent directory.

    Prevents path traversal attacks (e.g., ../../etc/passwd).

    Args:
        path: Path to validate
        allowed_parent: Parent directory that path must be within

    Returns:
        Resolved absolute path

    Raises:
        ValueError: If path escapes the allowed parent
    """
    resolved = Path(path).resolve()
    parent = Path(allowed_parent).resolve()

    if not str(resolved).startswith(str(parent)):
        raise ValueError(f"Path traversal detected: {path} resolves outside of {allowed_parent}")

    return resolved


# ---------------------------------------------------------------------------
# API key format validation
# ---------------------------------------------------------------------------


def validate_api_key_format(key: str, provider: str) -> bool:
    """Basic format validation for API keys.

    Checks that keys match expected patterns to catch obvious
    misconfigurations (pasting wrong keys, truncated values, etc.).

    Args:
        key: API key to validate
        provider: Provider name ("anthropic", "activecampaign", "google")

    Returns:
        True if key appears to be in valid format
    """
    if not key or not key.strip():
        return False

    key = key.strip()

    if provider == "anthropic":
        # Anthropic keys start with "sk-ant-" and are 40+ chars
        return key.startswith("sk-ant-") and len(key) >= 40

    if provider == "google":
        # Google API keys are typically 39 chars, alphanumeric with dashes
        return len(key) >= 20 and re.match(r"^[A-Za-z0-9_-]+$", key) is not None

    if provider == "activecampaign":
        # AC keys are typically 64-char hex strings
        return len(key) >= 20 and re.match(r"^[A-Za-z0-9]+$", key) is not None

    # Unknown provider - just check it's not empty and reasonably long
    return len(key) >= 10
