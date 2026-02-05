"""Session manager - Time tracking and energy levels.

Tracks session duration, warns about time blindness, manages energy-level
transitions throughout the day, maintains an undo stack, and persists
session state for crash recovery.
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

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
    before_state: dict[str, Any]
    after_state: dict[str, Any]
    timestamp: Optional[str] = None


# Maximum undo history depth
UNDO_STACK_SIZE = 5

# Default time warning intervals (minutes)
DEFAULT_WARNING_INTERVALS = [60, 90, 120]


class SessionManager:
    """Tracks session state, energy, time, and undo history.

    Manages:
      - Session start/elapsed time with time-blindness warnings
      - Energy level based on time of day
      - Undo stack for last N actions
      - Session state persistence for crash recovery
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        warning_intervals: Optional[list[int]] = None,
        now_fn: Optional[Any] = None,
    ):
        self._session_start: Optional[datetime] = None
        self._undo_stack: list[UndoableAction] = []
        self._warnings_fired: set[int] = set()
        self._warning_intervals = warning_intervals or DEFAULT_WARNING_INTERVALS
        self._data_dir = data_dir
        self._active = False
        # Injectable clock for testing
        self._now_fn = now_fn or datetime.now

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def start_session(self) -> None:
        """Start tracking a new session."""
        self._session_start = self._now_fn()
        self._warnings_fired.clear()
        self._undo_stack.clear()
        self._active = True
        logger.info(
            "Session started",
            extra={"context": {"start": self._session_start.isoformat()}},
        )
        self.save_session_state()

    def end_session(self) -> None:
        """End the current session."""
        self._active = False
        elapsed = self.get_elapsed_minutes()
        logger.info(
            "Session ended",
            extra={"context": {"elapsed_minutes": elapsed}},
        )

    def is_active(self) -> bool:
        """Check if a session is active."""
        return self._active

    def get_session_start(self) -> Optional[datetime]:
        """Get session start time."""
        return self._session_start

    def get_elapsed_minutes(self) -> int:
        """Get minutes elapsed since session start."""
        if self._session_start is None:
            return 0
        delta = self._now_fn() - self._session_start
        return int(delta.total_seconds() / 60)

    # ------------------------------------------------------------------
    # Time blindness warnings
    # ------------------------------------------------------------------

    def check_time_warnings(self) -> Optional[int]:
        """Check if a time warning should fire.

        Returns the threshold (minutes) that was exceeded, or None.
        Each threshold fires only once per session.
        """
        if self._session_start is None:
            return None

        elapsed = self.get_elapsed_minutes()
        for threshold in sorted(self._warning_intervals):
            if elapsed >= threshold and threshold not in self._warnings_fired:
                self._warnings_fired.add(threshold)
                logger.info(
                    "Time warning fired",
                    extra={"context": {"threshold": threshold, "elapsed": elapsed}},
                )
                return threshold
        return None

    def warn_time_elapsed(self, threshold_minutes: int) -> bool:
        """Check if a specific threshold has been exceeded.

        Returns True if the threshold was just exceeded (fires once).
        """
        if self._session_start is None:
            return False
        elapsed = self.get_elapsed_minutes()
        if elapsed >= threshold_minutes and threshold_minutes not in self._warnings_fired:
            self._warnings_fired.add(threshold_minutes)
            return True
        return False

    # ------------------------------------------------------------------
    # Energy level
    # ------------------------------------------------------------------

    def get_energy_level(self) -> EnergyLevel:
        """Get current energy level based on time of day.

        HIGH: before 2 PM
        MEDIUM: 2 PM - 4 PM
        LOW: after 4 PM
        """
        now = self._now_fn()
        hour = now.hour
        if hour < 14:
            return EnergyLevel.HIGH
        elif hour < 16:
            return EnergyLevel.MEDIUM
        else:
            return EnergyLevel.LOW

    def is_low_energy(self) -> bool:
        """Check if in low-energy mode."""
        return self.get_energy_level() == EnergyLevel.LOW

    # ------------------------------------------------------------------
    # Undo stack
    # ------------------------------------------------------------------

    def push_undo(self, action: UndoableAction) -> None:
        """Push action onto undo stack. Oldest dropped if stack full."""
        action.timestamp = self._now_fn().isoformat()
        self._undo_stack.append(action)
        if len(self._undo_stack) > UNDO_STACK_SIZE:
            self._undo_stack.pop(0)
        logger.debug(
            "Action pushed to undo stack",
            extra={
                "context": {
                    "action": action.action_type,
                    "prospect_id": action.prospect_id,
                    "depth": len(self._undo_stack),
                }
            },
        )

    def pop_undo(self) -> Optional[UndoableAction]:
        """Pop and return last action from undo stack."""
        if not self._undo_stack:
            return None
        action = self._undo_stack.pop()
        logger.debug(
            "Action popped from undo stack",
            extra={
                "context": {
                    "action": action.action_type,
                    "prospect_id": action.prospect_id,
                }
            },
        )
        return action

    def peek_undo(self) -> Optional[UndoableAction]:
        """Peek at last action without removing."""
        if not self._undo_stack:
            return None
        return self._undo_stack[-1]

    def undo_depth(self) -> int:
        """Number of undoable actions available."""
        return len(self._undo_stack)

    # ------------------------------------------------------------------
    # Session persistence (crash recovery)
    # ------------------------------------------------------------------

    def save_session_state(self) -> None:
        """Persist session state for crash recovery."""
        if self._data_dir is None:
            return
        path = self._data_dir / "session_state.json"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            state: dict[str, Any] = {
                "active": self._active,
                "session_start": self._session_start.isoformat() if self._session_start else None,
                "elapsed_minutes": self.get_elapsed_minutes(),
                "undo_stack": [
                    {
                        "action_type": a.action_type,
                        "prospect_id": a.prospect_id,
                        "before_state": a.before_state,
                        "after_state": a.after_state,
                        "timestamp": a.timestamp,
                    }
                    for a in self._undo_stack
                ],
            }
            path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except OSError:
            logger.warning("Failed to save session state", exc_info=True)

    def load_session_state(self) -> bool:
        """Load session state from crash recovery file.

        Returns True if a valid previous session was found.
        """
        if self._data_dir is None:
            return False
        path = self._data_dir / "session_state.json"
        if not path.exists():
            return False
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            if not state.get("active", False):
                return False
            start_str = state.get("session_start")
            if start_str:
                self._session_start = datetime.fromisoformat(start_str)
                self._active = True
                # Restore undo stack
                for item in state.get("undo_stack", []):
                    self._undo_stack.append(
                        UndoableAction(
                            action_type=item["action_type"],
                            prospect_id=item["prospect_id"],
                            before_state=item["before_state"],
                            after_state=item["after_state"],
                            timestamp=item.get("timestamp"),
                        )
                    )
                logger.info(
                    "Session recovered",
                    extra={"context": {"start": start_str}},
                )
                return True
            return False
        except (OSError, json.JSONDecodeError, KeyError):
            logger.warning("Failed to load session state", exc_info=True)
            return False

    def clear_recovery_state(self) -> None:
        """Clear the recovery file after successful session end."""
        if self._data_dir is None:
            return
        path = self._data_dir / "session_state.json"
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass
