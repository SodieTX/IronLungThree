"""Dopamine engine - Micro-wins, streaks, achievements.

Every small victory gets a hit. Consecutive productive actions
build streaks with celebrations at milestones. Achievements
track career firsts and personal bests.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from src.core.logging import get_logger

logger = get_logger(__name__)


class WinType(str, Enum):
    CARD_PROCESSED = "card_processed"
    EMAIL_SENT = "email_sent"
    CALL_COMPLETED = "call_completed"
    DEMO_SCHEDULED = "demo_scheduled"
    FOLLOW_UP_SET = "follow_up_set"


# Streak milestones that trigger celebrations
STREAK_MILESTONES = [5, 10, 20, 50]


@dataclass
class Achievement:
    name: str
    description: str
    earned: bool = False
    earned_at: Optional[datetime] = None


# Achievement definitions — the triggers are checked by check_achievement()
ACHIEVEMENT_DEFS: dict[str, str] = {
    "first_call": "Complete your first call",
    "first_demo": "Schedule your first demo",
    "first_close": "Close your first deal",
    "power_hour": "20+ calls in 60 minutes",
    "queue_cleared": "Process the entire daily queue",
    "perfect_day": "Complete all engaged follow-ups in a day",
    "streak_master": "50 cards without a skip",
}


class DopamineEngine:
    """Tracks micro-wins, streaks, and achievements.

    State is kept in memory during a session and persisted to a JSON file
    in the user's data directory so streaks survive restarts.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self._streak: int = 0
        self._total_wins: int = 0
        self._session_wins: dict[str, int] = {wt.value: 0 for wt in WinType}
        self._achievements: dict[str, Achievement] = {
            name: Achievement(name=name, description=desc)
            for name, desc in ACHIEVEMENT_DEFS.items()
        }
        self._celebration_callback: Optional[Callable[[str, int], None]] = None
        self._achievement_callback: Optional[Callable[[Achievement], None]] = None
        self._data_dir = data_dir
        self._load_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_win(self, win_type: WinType) -> Optional[int]:
        """Record a micro-win. Returns milestone streak count if hit, else None."""
        self._streak += 1
        self._total_wins += 1
        self._session_wins[win_type.value] = self._session_wins.get(win_type.value, 0) + 1

        logger.debug(
            "Micro-win recorded",
            extra={
                "context": {
                    "win_type": win_type.value,
                    "streak": self._streak,
                    "total": self._total_wins,
                }
            },
        )

        milestone = self._check_streak_milestone()
        if milestone is not None and self._celebration_callback:
            self._celebration_callback("streak", milestone)

        self._save_state()
        return milestone

    def break_streak(self) -> None:
        """Break the current streak (e.g., on skip)."""
        if self._streak > 0:
            logger.debug(
                "Streak broken",
                extra={"context": {"was": self._streak}},
            )
            self._streak = 0
            self._save_state()

    def get_streak(self) -> int:
        """Get current streak count."""
        return self._streak

    def get_total_wins(self) -> int:
        """Get total wins this session."""
        return self._total_wins

    def get_session_wins(self) -> dict[str, int]:
        """Get per-type win counts for the current session."""
        return dict(self._session_wins)

    def get_achievements(self) -> list[Achievement]:
        """Get all achievements with earned status."""
        return list(self._achievements.values())

    def get_earned_achievements(self) -> list[Achievement]:
        """Get only earned achievements."""
        return [a for a in self._achievements.values() if a.earned]

    def check_achievement(self, achievement_name: str) -> bool:
        """Award an achievement if not already earned.

        Returns True if newly awarded, False if already earned or unknown.
        """
        ach = self._achievements.get(achievement_name)
        if ach is None:
            logger.warning(
                "Unknown achievement",
                extra={"context": {"name": achievement_name}},
            )
            return False

        if ach.earned:
            return False

        ach.earned = True
        ach.earned_at = datetime.now()

        logger.info(
            "Achievement earned",
            extra={"context": {"name": achievement_name, "description": ach.description}},
        )

        if self._achievement_callback:
            self._achievement_callback(ach)

        self._save_state()
        return True

    def on_celebration(self, callback: Callable[[str, int], None]) -> None:
        """Register callback for streak celebrations.

        callback(celebration_type: str, value: int)
        """
        self._celebration_callback = callback

    def on_achievement(self, callback: Callable[[Achievement], None]) -> None:
        """Register callback for achievement unlocks."""
        self._achievement_callback = callback

    def reset_session(self) -> None:
        """Reset session counters (keeps achievements and total wins)."""
        self._session_wins = {wt.value: 0 for wt in WinType}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _check_streak_milestone(self) -> Optional[int]:
        """Check if current streak hit a milestone. Returns milestone or None."""
        if self._streak in STREAK_MILESTONES:
            return self._streak
        return None

    def _state_path(self) -> Optional[Path]:
        """Get path to persisted state file."""
        if self._data_dir is None:
            return None
        return self._data_dir / "dopamine_state.json"

    def _save_state(self) -> None:
        """Persist state to disk."""
        path = self._state_path()
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            state: dict[str, Any] = {
                "streak": self._streak,
                "total_wins": self._total_wins,
                "achievements": {
                    name: {
                        "earned": ach.earned,
                        "earned_at": ach.earned_at.isoformat() if ach.earned_at else None,
                    }
                    for name, ach in self._achievements.items()
                },
            }
            path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except OSError:
            logger.warning("Failed to save dopamine state", exc_info=True)

    def _load_state(self) -> None:
        """Restore state from disk."""
        path = self._state_path()
        if path is None or not path.exists():
            return
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            self._streak = state.get("streak", 0)
            self._total_wins = state.get("total_wins", 0)
            saved_achs = state.get("achievements", {})
            for name, data in saved_achs.items():
                if name in self._achievements:
                    self._achievements[name].earned = data.get("earned", False)
                    earned_at = data.get("earned_at")
                    if earned_at:
                        self._achievements[name].earned_at = datetime.fromisoformat(earned_at)
        except (OSError, json.JSONDecodeError, KeyError):
            logger.warning("Failed to load dopamine state, starting fresh", exc_info=True)
