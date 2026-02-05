"""Focus mode - Distraction-free card processing.

Current card fills screen, queue hidden. Only visible:
card, dictation bar, action buttons. Tunnel vision by design.

Activation: Ctrl+Shift+F or programmatic
Exit: Escape, "exit focus" command, or queue empty
"""

from typing import Callable, Optional

from src.core.logging import get_logger

logger = get_logger(__name__)


class FocusManager:
    """Manages focus mode state.

    Focus mode is a UI state where distractions are hidden.
    The actual UI changes are driven by callbacks — this manager
    tracks the logical state.
    """

    def __init__(self, auto_trigger_streak: Optional[int] = None):
        self._active: bool = False
        self._auto_trigger_streak = auto_trigger_streak
        self._on_enter: Optional[Callable[[], None]] = None
        self._on_exit: Optional[Callable[[], None]] = None

    def enter_focus_mode(self) -> bool:
        """Enter distraction-free focus mode.

        Returns True if mode was entered, False if already active.
        """
        if self._active:
            return False
        self._active = True
        logger.info("Focus mode entered")
        if self._on_enter:
            self._on_enter()
        return True

    def exit_focus_mode(self) -> bool:
        """Exit focus mode.

        Returns True if mode was exited, False if not active.
        """
        if not self._active:
            return False
        self._active = False
        logger.info("Focus mode exited")
        if self._on_exit:
            self._on_exit()
        return True

    def is_focus_mode(self) -> bool:
        """Check if focus mode is active."""
        return self._active

    def toggle(self) -> bool:
        """Toggle focus mode. Returns new state."""
        if self._active:
            self.exit_focus_mode()
        else:
            self.enter_focus_mode()
        return self._active

    def check_auto_trigger(self, current_streak: int) -> bool:
        """Check if streak should auto-trigger focus mode.

        Returns True if focus mode was auto-entered.
        """
        if self._auto_trigger_streak is None:
            return False
        if self._active:
            return False
        if current_streak == self._auto_trigger_streak:
            self.enter_focus_mode()
            logger.info(
                "Focus mode auto-triggered by streak",
                extra={"context": {"streak": current_streak}},
            )
            return True
        return False

    def on_enter(self, callback: Callable[[], None]) -> None:
        """Register callback for entering focus mode."""
        self._on_enter = callback

    def on_exit(self, callback: Callable[[], None]) -> None:
        """Register callback for exiting focus mode."""
        self._on_exit = callback
