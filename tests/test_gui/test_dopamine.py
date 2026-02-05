"""Tests for dopamine engine — streaks, celebrations, achievements."""

import json
from pathlib import Path

import pytest

from src.gui.adhd.dopamine import (
    ACHIEVEMENT_DEFS,
    STREAK_MILESTONES,
    Achievement,
    DopamineEngine,
    WinType,
)


@pytest.fixture
def engine(tmp_path: Path) -> DopamineEngine:
    """Fresh dopamine engine with temp persistence."""
    return DopamineEngine(data_dir=tmp_path)


@pytest.fixture
def engine_no_persist() -> DopamineEngine:
    """Dopamine engine without persistence (in-memory only)."""
    return DopamineEngine(data_dir=None)


class TestMicroWins:
    def test_record_win_increments_streak(self, engine: DopamineEngine) -> None:
        engine.record_win(WinType.CARD_PROCESSED)
        assert engine.get_streak() == 1

    def test_record_multiple_wins(self, engine: DopamineEngine) -> None:
        for _ in range(7):
            engine.record_win(WinType.CARD_PROCESSED)
        assert engine.get_streak() == 7
        assert engine.get_total_wins() == 7

    def test_different_win_types_tracked(self, engine: DopamineEngine) -> None:
        engine.record_win(WinType.CARD_PROCESSED)
        engine.record_win(WinType.EMAIL_SENT)
        engine.record_win(WinType.CALL_COMPLETED)
        wins = engine.get_session_wins()
        assert wins["card_processed"] == 1
        assert wins["email_sent"] == 1
        assert wins["call_completed"] == 1

    def test_break_streak_resets_to_zero(self, engine: DopamineEngine) -> None:
        for _ in range(3):
            engine.record_win(WinType.CARD_PROCESSED)
        assert engine.get_streak() == 3
        engine.break_streak()
        assert engine.get_streak() == 0

    def test_break_streak_preserves_total(self, engine: DopamineEngine) -> None:
        for _ in range(3):
            engine.record_win(WinType.CARD_PROCESSED)
        engine.break_streak()
        assert engine.get_total_wins() == 3

    def test_break_streak_on_zero_is_noop(self, engine: DopamineEngine) -> None:
        engine.break_streak()
        assert engine.get_streak() == 0


class TestStreakMilestones:
    def test_milestone_at_5(self, engine: DopamineEngine) -> None:
        for i in range(5):
            result = engine.record_win(WinType.CARD_PROCESSED)
        assert result == 5

    def test_milestone_at_10(self, engine: DopamineEngine) -> None:
        result = None
        for i in range(10):
            result = engine.record_win(WinType.CARD_PROCESSED)
        assert result == 10

    def test_milestone_at_20(self, engine: DopamineEngine) -> None:
        result = None
        for i in range(20):
            result = engine.record_win(WinType.CARD_PROCESSED)
        assert result == 20

    def test_milestone_at_50(self, engine: DopamineEngine) -> None:
        result = None
        for i in range(50):
            result = engine.record_win(WinType.CARD_PROCESSED)
        assert result == 50

    def test_no_milestone_at_6(self, engine: DopamineEngine) -> None:
        for i in range(6):
            result = engine.record_win(WinType.CARD_PROCESSED)
        assert result is None

    def test_celebration_callback_fires(self, engine: DopamineEngine) -> None:
        celebrations: list[tuple[str, int]] = []
        engine.on_celebration(lambda t, v: celebrations.append((t, v)))
        for _ in range(5):
            engine.record_win(WinType.CARD_PROCESSED)
        assert len(celebrations) == 1
        assert celebrations[0] == ("streak", 5)


class TestAchievements:
    def test_all_achievements_defined(self, engine: DopamineEngine) -> None:
        achs = engine.get_achievements()
        names = {a.name for a in achs}
        for expected in ACHIEVEMENT_DEFS:
            assert expected in names

    def test_no_achievements_earned_initially(self, engine: DopamineEngine) -> None:
        earned = engine.get_earned_achievements()
        assert len(earned) == 0

    def test_check_achievement_awards(self, engine: DopamineEngine) -> None:
        result = engine.check_achievement("first_call")
        assert result is True
        earned = engine.get_earned_achievements()
        assert len(earned) == 1
        assert earned[0].name == "first_call"
        assert earned[0].earned is True
        assert earned[0].earned_at is not None

    def test_check_achievement_idempotent(self, engine: DopamineEngine) -> None:
        engine.check_achievement("first_call")
        result = engine.check_achievement("first_call")
        assert result is False  # Already earned

    def test_unknown_achievement_returns_false(self, engine: DopamineEngine) -> None:
        result = engine.check_achievement("nonexistent")
        assert result is False

    def test_achievement_callback_fires(self, engine: DopamineEngine) -> None:
        unlocked: list[Achievement] = []
        engine.on_achievement(lambda a: unlocked.append(a))
        engine.check_achievement("first_demo")
        assert len(unlocked) == 1
        assert unlocked[0].name == "first_demo"


class TestPersistence:
    def test_state_persists_across_instances(self, tmp_path: Path) -> None:
        engine1 = DopamineEngine(data_dir=tmp_path)
        for _ in range(7):
            engine1.record_win(WinType.CARD_PROCESSED)
        engine1.check_achievement("first_call")

        engine2 = DopamineEngine(data_dir=tmp_path)
        assert engine2.get_streak() == 7
        assert engine2.get_total_wins() == 7
        earned = engine2.get_earned_achievements()
        assert len(earned) == 1
        assert earned[0].name == "first_call"

    def test_corrupt_state_file_handled(self, tmp_path: Path) -> None:
        state_file = tmp_path / "dopamine_state.json"
        state_file.write_text("not valid json", encoding="utf-8")
        engine = DopamineEngine(data_dir=tmp_path)
        # Should start fresh, no crash
        assert engine.get_streak() == 0

    def test_no_persist_without_data_dir(self, engine_no_persist: DopamineEngine) -> None:
        engine_no_persist.record_win(WinType.CARD_PROCESSED)
        assert engine_no_persist.get_streak() == 1
        # No exception — just works in memory


class TestSessionReset:
    def test_reset_session_clears_session_wins(self, engine: DopamineEngine) -> None:
        engine.record_win(WinType.CARD_PROCESSED)
        engine.record_win(WinType.EMAIL_SENT)
        engine.reset_session()
        wins = engine.get_session_wins()
        assert all(v == 0 for v in wins.values())
