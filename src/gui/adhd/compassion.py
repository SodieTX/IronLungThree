"""Compassionate messages - No guilt trips. Ever."""

from src.core.logging import get_logger

logger = get_logger(__name__)


def get_welcome_message() -> str:
    """Get appropriate welcome message based on context."""
    raise NotImplementedError("Phase 6, Step 6.7")


def get_encouragement() -> str:
    """Get contextual encouragement."""
    raise NotImplementedError("Phase 6, Step 6.7")


def get_break_suggestion() -> str:
    """Suggest break if warranted."""
    raise NotImplementedError("Phase 6, Step 6.7")


def get_rescue_intro() -> str:
    """Get intro for rescue mode - no guilt."""
    raise NotImplementedError("Phase 6, Step 6.7")
