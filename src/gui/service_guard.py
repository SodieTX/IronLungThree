"""Service availability guard for GUI operations.

Provides a simple check-before-you-act pattern for any GUI code that
needs an external service (Outlook, Claude, ActiveCampaign). Instead
of letting the operation crash deep in an API call, we check at the
button-press level and show a clear message.

Usage in any GUI tab or dialog:

    from src.gui.service_guard import check_service

    def on_send_email(self):
        if not check_service("outlook", parent=self.frame):
            return  # User was shown a clear message, bail out
        # ... proceed with email send

    def on_generate_email(self):
        if not check_service("claude", parent=self.frame):
            return
        # ... proceed with AI generation
"""

import tkinter as tk
from tkinter import messagebox
from typing import Optional

from src.core.logging import get_logger
from src.core.services import get_service_registry

logger = get_logger(__name__)


def check_service(
    service_key: str,
    parent: Optional[tk.Widget] = None,
    silent: bool = False,
) -> bool:
    """Check if a service is available before attempting to use it.

    If the service is unavailable, shows a messagebox explaining what's
    missing and how to fix it (unless silent=True).

    Args:
        service_key: Service to check ("outlook", "claude", etc.)
        parent: Parent widget for the messagebox
        silent: If True, skip the messagebox (just return bool)

    Returns:
        True if the service is available and ready to use
    """
    registry = get_service_registry()

    try:
        status = registry.check(service_key)
    except KeyError:
        logger.error(f"Unknown service key in GUI: {service_key}")
        return False

    if status.available:
        return True

    if not silent:
        # Build a helpful message
        if status.credentials_missing:
            missing_list = "\n".join(f"  - {k}" for k in status.credentials_missing)
            message = (
                f"{status.name} is not configured.\n\n"
                f"Missing credentials:\n{missing_list}\n\n"
                f"Add these to your .env file and restart IronLung."
            )
        else:
            message = (
                f"{status.name} is not available.\n\n"
                f"Reason: {status.reason}\n\n"
                f"Check your .env file and restart IronLung."
            )

        logger.info(
            f"Service check failed for '{service_key}' in GUI",
            extra={"context": {"service": service_key, "reason": status.reason}},
        )

        messagebox.showwarning(
            f"{status.name} Unavailable",
            message,
            parent=parent,  # type: ignore[arg-type]
        )

    return False


def get_service_status_text() -> str:
    """Get a formatted service status string for display in Settings tab.

    Returns:
        Multi-line string showing all service statuses
    """
    registry = get_service_registry()
    report = registry.readiness_report()
    return report.summary
