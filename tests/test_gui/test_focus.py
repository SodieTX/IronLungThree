"""Tests for focus mode — distraction-free card processing."""

import pytest

from src.gui.adhd.focus import FocusManager


@pytest.fixture
def fm() -> FocusManager:
    return FocusManager()


class TestFocusMode:
    def test_not_active_initially(self, fm: FocusManager) -> None:
        assert fm.is_focus_mode() is False

    def test_enter_focus_mode(self, fm: FocusManager) -> None:
        assert fm.enter_focus_mode() is True
        assert fm.is_focus_mode() is True

    def test_enter_already_active_returns_false(self, fm: FocusManager) -> None:
        fm.enter_focus_mode()
        assert fm.enter_focus_mode() is False

    def test_exit_focus_mode(self, fm: FocusManager) -> None:
        fm.enter_focus_mode()
        assert fm.exit_focus_mode() is True
        assert fm.is_focus_mode() is False

    def test_exit_not_active_returns_false(self, fm: FocusManager) -> None:
        assert fm.exit_focus_mode() is False

    def test_toggle_on(self, fm: FocusManager) -> None:
        state = fm.toggle()
        assert state is True
        assert fm.is_focus_mode() is True

    def test_toggle_off(self, fm: FocusManager) -> None:
        fm.enter_focus_mode()
        state = fm.toggle()
        assert state is False
        assert fm.is_focus_mode() is False


class TestCallbacks:
    def test_on_enter_callback(self, fm: FocusManager) -> None:
        entered: list[bool] = []
        fm.on_enter(lambda: entered.append(True))
        fm.enter_focus_mode()
        assert len(entered) == 1

    def test_on_exit_callback(self, fm: FocusManager) -> None:
        exited: list[bool] = []
        fm.on_exit(lambda: exited.append(True))
        fm.enter_focus_mode()
        fm.exit_focus_mode()
        assert len(exited) == 1


class TestAutoTrigger:
    def test_auto_trigger_at_streak(self) -> None:
        fm = FocusManager(auto_trigger_streak=5)
        assert fm.check_auto_trigger(5) is True
        assert fm.is_focus_mode() is True

    def test_no_auto_trigger_below_streak(self) -> None:
        fm = FocusManager(auto_trigger_streak=5)
        assert fm.check_auto_trigger(3) is False
        assert fm.is_focus_mode() is False

    def test_no_auto_trigger_if_already_active(self) -> None:
        fm = FocusManager(auto_trigger_streak=5)
        fm.enter_focus_mode()
        assert fm.check_auto_trigger(5) is False

    def test_no_auto_trigger_when_disabled(self) -> None:
        fm = FocusManager(auto_trigger_streak=None)
        assert fm.check_auto_trigger(5) is False
