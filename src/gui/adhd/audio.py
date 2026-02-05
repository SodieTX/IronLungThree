"""Audio feedback for actions."""

from enum import Enum

from src.core.logging import get_logger

logger = get_logger(__name__)


class Sound(str, Enum):
    CARD_DONE = "card_done"
    EMAIL_SENT = "email_sent"
    DEMO_SET = "demo_set"
    DEAL_CLOSED = "deal_closed"
    ERROR = "error"
    STREAK = "streak"


_muted = False


def play_sound(sound: Sound) -> None:
    """Play sound effect."""
    raise NotImplementedError("Phase 6, Step 6.4")


def set_muted(muted: bool) -> None:
    """Set mute state."""
    global _muted
    _muted = muted


def is_muted() -> bool:
    """Check mute state."""
    return _muted
