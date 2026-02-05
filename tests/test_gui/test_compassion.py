"""Tests for compassionate messages — no guilt trips."""

from datetime import datetime, timedelta

import pytest

from src.gui.adhd.compassion import (
    _BREAK_SUGGESTIONS,
    _ENCOURAGEMENT_EARLY,
    _ENCOURAGEMENT_LATE,
    _ENCOURAGEMENT_MID,
    _ENCOURAGEMENT_STREAK,
    _LOW_PRODUCTIVITY,
    _MISSED_FOLLOWUPS,
    _QUEUE_EMPTY,
    _RESCUE_INTROS,
    _WELCOME_BACK_LONG,
    _WELCOME_BACK_SHORT,
    _WELCOME_FRESH,
    CompassionEngine,
)


def _make_clock(dt: datetime):
    return lambda: dt


class TestWelcomeMessage:
    def test_fresh_session(self) -> None:
        ce = CompassionEngine()
        msg = ce.get_welcome_message(last_session_end=None)
        assert msg in _WELCOME_FRESH

    def test_short_gap(self) -> None:
        now = datetime(2026, 2, 5, 10, 0, 0)
        ce = CompassionEngine(now_fn=_make_clock(now))
        last = now - timedelta(hours=2)
        msg = ce.get_welcome_message(last_session_end=last)
        assert any(msg.startswith(m) for m in _WELCOME_BACK_SHORT)

    def test_long_gap(self) -> None:
        now = datetime(2026, 2, 5, 10, 0, 0)
        ce = CompassionEngine(now_fn=_make_clock(now))
        last = now - timedelta(days=2)
        msg = ce.get_welcome_message(last_session_end=last)
        assert any(msg.startswith(m) for m in _WELCOME_BACK_LONG)

    def test_missed_followups_appended(self) -> None:
        now = datetime(2026, 2, 5, 10, 0, 0)
        ce = CompassionEngine(now_fn=_make_clock(now))
        last = now - timedelta(days=1)
        msg = ce.get_welcome_message(last_session_end=last, missed_followups=5)
        assert "5 follow-ups" in msg

    def test_single_missed_followup_no_plural(self) -> None:
        now = datetime(2026, 2, 5, 10, 0, 0)
        ce = CompassionEngine(now_fn=_make_clock(now))
        last = now - timedelta(days=1)
        msg = ce.get_welcome_message(last_session_end=last, missed_followups=1)
        assert "1 follow-up " in msg
        assert "follow-ups" not in msg


class TestEncouragement:
    def test_early_morning(self) -> None:
        ce = CompassionEngine(now_fn=_make_clock(datetime(2026, 2, 5, 9, 0, 0)))
        msg = ce.get_encouragement()
        assert msg in _ENCOURAGEMENT_EARLY

    def test_midday(self) -> None:
        ce = CompassionEngine(now_fn=_make_clock(datetime(2026, 2, 5, 14, 0, 0)))
        msg = ce.get_encouragement()
        assert msg in _ENCOURAGEMENT_MID

    def test_late(self) -> None:
        ce = CompassionEngine(now_fn=_make_clock(datetime(2026, 2, 5, 17, 0, 0)))
        msg = ce.get_encouragement()
        assert msg in _ENCOURAGEMENT_LATE

    def test_streak_overrides_time(self) -> None:
        ce = CompassionEngine(now_fn=_make_clock(datetime(2026, 2, 5, 9, 0, 0)))
        msg = ce.get_encouragement(current_streak=10)
        assert msg in _ENCOURAGEMENT_STREAK


class TestBreakSuggestion:
    def test_no_break_under_45_min(self) -> None:
        ce = CompassionEngine()
        assert ce.get_break_suggestion(session_minutes=30) is None

    def test_break_suggested_over_45_min(self) -> None:
        ce = CompassionEngine()
        msg = ce.get_break_suggestion(session_minutes=60)
        assert msg is not None
        assert msg in _BREAK_SUGGESTIONS


class TestOtherMessages:
    def test_queue_empty(self) -> None:
        ce = CompassionEngine()
        msg = ce.get_queue_empty_message()
        assert msg in _QUEUE_EMPTY

    def test_missed_followups(self) -> None:
        ce = CompassionEngine()
        msg = ce.get_missed_followup_message(3)
        assert msg in _MISSED_FOLLOWUPS

    def test_low_productivity(self) -> None:
        ce = CompassionEngine()
        msg = ce.get_low_productivity_message()
        assert msg in _LOW_PRODUCTIVITY

    def test_rescue_intro(self) -> None:
        ce = CompassionEngine()
        msg = ce.get_rescue_intro()
        assert msg in _RESCUE_INTROS


class TestNoGuiltTrips:
    """Verify that NO message contains guilt-inducing language."""

    GUILT_WORDS = [
        "should have",
        "you need to",
        "why didn't",
        "you failed",
        "disappointing",
        "behind",
        "lazy",
        "not enough",
        "you forgot",
        "shame",
    ]

    def _check_no_guilt(self, messages: list[str]) -> None:
        for msg in messages:
            lower = msg.lower()
            for word in self.GUILT_WORDS:
                assert word not in lower, f"Guilt word '{word}' found in: {msg}"

    def test_welcome_no_guilt(self) -> None:
        self._check_no_guilt(_WELCOME_FRESH + _WELCOME_BACK_SHORT + _WELCOME_BACK_LONG)

    def test_encouragement_no_guilt(self) -> None:
        self._check_no_guilt(
            _ENCOURAGEMENT_EARLY + _ENCOURAGEMENT_MID + _ENCOURAGEMENT_LATE + _ENCOURAGEMENT_STREAK
        )

    def test_break_no_guilt(self) -> None:
        self._check_no_guilt(_BREAK_SUGGESTIONS)

    def test_queue_empty_no_guilt(self) -> None:
        self._check_no_guilt(_QUEUE_EMPTY)

    def test_missed_no_guilt(self) -> None:
        self._check_no_guilt(_MISSED_FOLLOWUPS)

    def test_low_prod_no_guilt(self) -> None:
        self._check_no_guilt(_LOW_PRODUCTIVITY)

    def test_rescue_no_guilt(self) -> None:
        self._check_no_guilt(_RESCUE_INTROS)
