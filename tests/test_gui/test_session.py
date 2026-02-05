"""Tests for session manager — time tracking, energy, undo, recovery."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.gui.adhd.session import (
    UNDO_STACK_SIZE,
    EnergyLevel,
    SessionManager,
    UndoableAction,
)


def _make_clock(dt: datetime):
    """Return a callable that returns a fixed datetime."""
    return lambda: dt


@pytest.fixture
def session(tmp_path: Path) -> SessionManager:
    """Session manager with 10:00 AM clock and temp persistence."""
    morning = datetime(2026, 2, 5, 10, 0, 0)
    return SessionManager(data_dir=tmp_path, now_fn=_make_clock(morning))


class TestSessionLifecycle:
    def test_start_session(self, session: SessionManager) -> None:
        session.start_session()
        assert session.is_active()
        assert session.get_session_start() is not None

    def test_end_session(self, session: SessionManager) -> None:
        session.start_session()
        session.end_session()
        assert not session.is_active()

    def test_not_active_initially(self, session: SessionManager) -> None:
        assert not session.is_active()

    def test_elapsed_zero_before_start(self, session: SessionManager) -> None:
        assert session.get_elapsed_minutes() == 0


class TestTimeTracking:
    def test_elapsed_minutes(self, tmp_path: Path) -> None:
        start = datetime(2026, 2, 5, 10, 0, 0)
        later = datetime(2026, 2, 5, 10, 45, 0)
        sm = SessionManager(data_dir=tmp_path, now_fn=_make_clock(start))
        sm.start_session()
        # Simulate time passing
        sm._now_fn = _make_clock(later)
        assert sm.get_elapsed_minutes() == 45

    def test_time_warning_fires_once(self, tmp_path: Path) -> None:
        start = datetime(2026, 2, 5, 10, 0, 0)
        sm = SessionManager(
            data_dir=tmp_path,
            now_fn=_make_clock(start),
            warning_intervals=[30],
        )
        sm.start_session()
        sm._now_fn = _make_clock(start + timedelta(minutes=35))
        assert sm.check_time_warnings() == 30
        # Second check — already fired
        assert sm.check_time_warnings() is None

    def test_warn_time_elapsed_specific_threshold(self, tmp_path: Path) -> None:
        start = datetime(2026, 2, 5, 10, 0, 0)
        sm = SessionManager(data_dir=tmp_path, now_fn=_make_clock(start))
        sm.start_session()
        sm._now_fn = _make_clock(start + timedelta(minutes=65))
        assert sm.warn_time_elapsed(60) is True
        # Already fired
        assert sm.warn_time_elapsed(60) is False

    def test_warn_time_not_reached(self, session: SessionManager) -> None:
        session.start_session()
        assert session.warn_time_elapsed(60) is False

    def test_warn_time_no_session(self, session: SessionManager) -> None:
        assert session.warn_time_elapsed(60) is False


class TestEnergyLevel:
    def test_high_energy_morning(self, tmp_path: Path) -> None:
        morning = datetime(2026, 2, 5, 9, 0, 0)
        sm = SessionManager(data_dir=tmp_path, now_fn=_make_clock(morning))
        assert sm.get_energy_level() == EnergyLevel.HIGH

    def test_medium_energy_afternoon(self, tmp_path: Path) -> None:
        afternoon = datetime(2026, 2, 5, 14, 30, 0)
        sm = SessionManager(data_dir=tmp_path, now_fn=_make_clock(afternoon))
        assert sm.get_energy_level() == EnergyLevel.MEDIUM

    def test_low_energy_late(self, tmp_path: Path) -> None:
        late = datetime(2026, 2, 5, 16, 30, 0)
        sm = SessionManager(data_dir=tmp_path, now_fn=_make_clock(late))
        assert sm.get_energy_level() == EnergyLevel.LOW

    def test_is_low_energy(self, tmp_path: Path) -> None:
        late = datetime(2026, 2, 5, 17, 0, 0)
        sm = SessionManager(data_dir=tmp_path, now_fn=_make_clock(late))
        assert sm.is_low_energy() is True

    def test_not_low_energy_morning(self, session: SessionManager) -> None:
        assert session.is_low_energy() is False

    def test_boundary_2pm_is_medium(self, tmp_path: Path) -> None:
        boundary = datetime(2026, 2, 5, 14, 0, 0)
        sm = SessionManager(data_dir=tmp_path, now_fn=_make_clock(boundary))
        assert sm.get_energy_level() == EnergyLevel.MEDIUM

    def test_boundary_4pm_is_low(self, tmp_path: Path) -> None:
        boundary = datetime(2026, 2, 5, 16, 0, 0)
        sm = SessionManager(data_dir=tmp_path, now_fn=_make_clock(boundary))
        assert sm.get_energy_level() == EnergyLevel.LOW


class TestUndoStack:
    def _make_action(self, n: int) -> UndoableAction:
        return UndoableAction(
            action_type="status_change",
            prospect_id=n,
            before_state={"population": "unengaged"},
            after_state={"population": "engaged"},
        )

    def test_push_and_pop(self, session: SessionManager) -> None:
        action = self._make_action(1)
        session.push_undo(action)
        popped = session.pop_undo()
        assert popped is not None
        assert popped.prospect_id == 1
        assert popped.timestamp is not None

    def test_pop_empty_returns_none(self, session: SessionManager) -> None:
        assert session.pop_undo() is None

    def test_lifo_order(self, session: SessionManager) -> None:
        session.push_undo(self._make_action(1))
        session.push_undo(self._make_action(2))
        session.push_undo(self._make_action(3))
        assert session.pop_undo().prospect_id == 3
        assert session.pop_undo().prospect_id == 2
        assert session.pop_undo().prospect_id == 1

    def test_stack_capped_at_max_size(self, session: SessionManager) -> None:
        for i in range(UNDO_STACK_SIZE + 3):
            session.push_undo(self._make_action(i))
        assert session.undo_depth() == UNDO_STACK_SIZE
        # Oldest (0, 1, 2) dropped; first available is 3
        assert session.pop_undo().prospect_id == UNDO_STACK_SIZE + 2

    def test_peek_does_not_remove(self, session: SessionManager) -> None:
        session.push_undo(self._make_action(42))
        peeked = session.peek_undo()
        assert peeked is not None
        assert peeked.prospect_id == 42
        assert session.undo_depth() == 1

    def test_peek_empty_returns_none(self, session: SessionManager) -> None:
        assert session.peek_undo() is None


class TestSessionRecovery:
    def test_save_and_load(self, tmp_path: Path) -> None:
        start = datetime(2026, 2, 5, 10, 0, 0)
        sm1 = SessionManager(data_dir=tmp_path, now_fn=_make_clock(start))
        sm1.start_session()
        sm1.push_undo(
            UndoableAction(
                action_type="move",
                prospect_id=99,
                before_state={"pop": "unengaged"},
                after_state={"pop": "engaged"},
            )
        )
        sm1.save_session_state()

        # New instance loads state
        sm2 = SessionManager(data_dir=tmp_path, now_fn=_make_clock(start))
        assert sm2.load_session_state() is True
        assert sm2.is_active()
        assert sm2.undo_depth() == 1

    def test_load_no_file_returns_false(self, tmp_path: Path) -> None:
        sm = SessionManager(data_dir=tmp_path)
        assert sm.load_session_state() is False

    def test_load_corrupt_file(self, tmp_path: Path) -> None:
        (tmp_path / "session_state.json").write_text("broken", encoding="utf-8")
        sm = SessionManager(data_dir=tmp_path)
        assert sm.load_session_state() is False

    def test_clear_recovery_state(self, tmp_path: Path) -> None:
        start = datetime(2026, 2, 5, 10, 0, 0)
        sm = SessionManager(data_dir=tmp_path, now_fn=_make_clock(start))
        sm.start_session()
        sm.save_session_state()
        assert (tmp_path / "session_state.json").exists()
        sm.clear_recovery_state()
        assert not (tmp_path / "session_state.json").exists()
