"""Focus mode - Distraction-free card processing."""

from src.core.logging import get_logger

logger = get_logger(__name__)

_focus_mode_active = False


def enter_focus_mode() -> None:
    """Enter distraction-free focus mode."""
    raise NotImplementedError("Phase 6, Step 6.3")


def exit_focus_mode() -> None:
    """Exit focus mode."""
    raise NotImplementedError("Phase 6, Step 6.3")


def is_focus_mode() -> bool:
    """Check if focus mode active."""
    return _focus_mode_active
