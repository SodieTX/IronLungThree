"""Bria softphone integration for click-to-call.

Uses tel: or sip: URI schemes to initiate calls through Bria.
Falls back to clipboard copy when Bria is unavailable or offline.

Usage:
    from src.integrations.bria import BriaDialer

    dialer = BriaDialer()
    if dialer.dial("713-555-1234"):
        print("Dialing...")
"""

import subprocess
import webbrowser
from typing import Optional

from src.integrations.base import IntegrationBase
from src.core.logging import get_logger

logger = get_logger(__name__)


class BriaDialer(IntegrationBase):
    """Bria softphone dialer.

    Initiates calls via URI scheme (tel: or sip:).
    Falls back to clipboard copy if unavailable.
    """

    def health_check(self) -> bool:
        """Check if Bria is available.

        Returns:
            True if Bria appears to be installed
        """
        raise NotImplementedError("Phase 3, Step 3.3")

    def is_configured(self) -> bool:
        """Bria requires no configuration - always returns True."""
        return True

    def is_available(self) -> bool:
        """Check if Bria is installed and running.

        Returns:
            True if Bria can receive dial requests
        """
        raise NotImplementedError("Phase 3, Step 3.3")

    def dial(self, phone_number: str) -> bool:
        """Initiate call via Bria.

        If Bria unavailable, copies number to clipboard.

        Args:
            phone_number: Number to dial (any format)

        Returns:
            True if dial initiated, False if copied to clipboard
        """
        raise NotImplementedError("Phase 3, Step 3.3")

    def _normalize_for_dial(self, phone: str) -> str:
        """Normalize phone number for dialing.

        Removes non-digit characters except + prefix.
        """
        # Keep + prefix for international
        if phone.startswith("+"):
            return "+" + "".join(c for c in phone[1:] if c.isdigit())
        return "".join(c for c in phone if c.isdigit())

    def _copy_to_clipboard(self, text: str) -> bool:
        """Copy text to clipboard.

        Uses pyperclip if available, falls back to tkinter.
        """
        try:
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update()
            root.destroy()
            return True
        except Exception as e:
            logger.error(f"Failed to copy to clipboard: {e}")
            return False
