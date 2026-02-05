"""Bria softphone integration for click-to-call.

Uses tel: URI scheme to initiate calls through Bria.
Falls back to clipboard copy when Bria is unavailable or offline.

Usage:
    from src.integrations.bria import BriaDialer

    dialer = BriaDialer()
    if dialer.dial("713-555-1234"):
        print("Dialing...")
    else:
        print("Copied to clipboard")
"""

import platform
import shutil
import webbrowser

from src.core.logging import get_logger
from src.integrations.base import IntegrationBase

logger = get_logger(__name__)

# Known Bria executable names by platform
_BRIA_EXECUTABLES = {
    "Windows": ["Bria.exe", "BriaSolo.exe"],
    "Darwin": ["Bria"],
    "Linux": ["bria"],
}


class BriaDialer(IntegrationBase):
    """Bria softphone dialer.

    Initiates calls via URI scheme (tel:).
    Falls back to clipboard copy if unavailable.
    """

    def __init__(self) -> None:
        """Initialize Bria dialer."""
        self._available: bool | None = None

    def health_check(self) -> bool:
        """Check if Bria is available.

        Returns:
            True if Bria appears to be installed
        """
        return self.is_available()

    def is_configured(self) -> bool:
        """Bria requires no configuration - always returns True."""
        return True

    def is_available(self) -> bool:
        """Check if Bria is installed and findable on the system.

        On Windows, checks if Bria executable is on PATH or in
        common install locations. Result is cached after first check.

        Returns:
            True if Bria can likely receive dial requests
        """
        if self._available is not None:
            return self._available

        system = platform.system()
        executables = _BRIA_EXECUTABLES.get(system, [])

        for exe in executables:
            if shutil.which(exe):
                self._available = True
                logger.info(f"Bria found: {exe}")
                return True

        # On Windows, also check common install paths
        if system == "Windows":
            try:
                import winreg

                # Check for Bria in registry (installed programs)
                for key_path in [
                    r"SOFTWARE\CounterPath\Bria",
                    r"SOFTWARE\WOW6432Node\CounterPath\Bria",
                ]:
                    try:
                        winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
                        self._available = True
                        logger.info("Bria found via Windows registry")
                        return True
                    except FileNotFoundError:
                        continue
            except ImportError:
                pass

        self._available = False
        logger.info("Bria not found on system")
        return False

    def dial(self, phone_number: str) -> bool:
        """Initiate call via Bria using tel: URI scheme.

        If Bria is unavailable, copies the number to clipboard instead.

        Args:
            phone_number: Number to dial (any format)

        Returns:
            True if dial initiated via Bria,
            False if copied to clipboard (fallback)
        """
        normalized = self._normalize_for_dial(phone_number)
        if not normalized:
            logger.warning(f"Invalid phone number: {phone_number}")
            return False

        if self.is_available():
            try:
                uri = f"tel:{normalized}"
                webbrowser.open(uri)
                logger.info(
                    f"Dialing via Bria: {normalized}",
                    extra={"context": {"phone": normalized}},
                )
                return True
            except Exception as e:
                logger.warning(f"Bria dial failed, falling back to clipboard: {e}")

        # Fallback: copy to clipboard
        copied = self._copy_to_clipboard(normalized)
        if copied:
            logger.info(
                f"Copied to clipboard (Bria unavailable): {normalized}",
                extra={"context": {"phone": normalized, "fallback": True}},
            )
        return False

    def _normalize_for_dial(self, phone: str) -> str:
        """Normalize phone number for dialing.

        Removes non-digit characters except + prefix.
        """
        if phone.startswith("+"):
            return "+" + "".join(c for c in phone[1:] if c.isdigit())
        return "".join(c for c in phone if c.isdigit())

    def _copy_to_clipboard(self, text: str) -> bool:
        """Copy text to clipboard.

        Uses tkinter (ships with Python on Windows).
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
