"""Session manager - Time tracking and energy levels."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
from src.core.logging import get_logger

logger = get_logger(__name__)


class EnergyLevel(str, Enum):
    HIGH = "high"  # Before 2 PM
    MEDIUM = "medium"  # 2 PM - 4 PM
    LOW = "low"  # After 4 PM


@dataclass
class UndoableAction:
    action_type: str
    prospect_id: int
    before_state: dict
    after_state: dict


def start_session() -> None:
    """Start tracking session."""
    raise NotImplementedError("Phase 6, Step 6.2")


def get_energy_level() -> EnergyLevel:
    """Get current energy level based on time."""
    raise NotImplementedError("Phase 6, Step 6.2")


def warn_time_elapsed(threshold_minutes: int) -> bool:
    """Check if warning should fire."""
    raise NotImplementedError("Phase 6, Step 6.2")


def push_undo(action: UndoableAction) -> None:
    """Push action to undo stack."""
    raise NotImplementedError("Phase 6, Step 6.2")


def pop_undo() -> Optional[UndoableAction]:
    """Pop and reverse last action."""
    raise NotImplementedError("Phase 6, Step 6.2")


def save_session_state() -> None:
    """Save state for crash recovery."""
    raise NotImplementedError("Phase 6, Step 6.2")
