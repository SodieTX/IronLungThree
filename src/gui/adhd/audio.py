"""Audio feedback for actions.

Every action gets a sound. Different tones for different outcomes.
All configurable, all mutable.

On platforms where winsound is not available (Linux/macOS), audio
playback is logged but no sound is emitted (graceful degradation).
"""

from enum import Enum
from typing import Callable, Optional

from src.core.logging import get_logger

logger = get_logger(__name__)


class Sound(str, Enum):
    CARD_DONE = "card_done"
    EMAIL_SENT = "email_sent"
    DEMO_SET = "demo_set"
    DEAL_CLOSED = "deal_closed"
    ERROR = "error"
    STREAK = "streak"


# Frequency / duration pairs for winsound.Beep (Windows)
# On non-Windows platforms these are logged but not played.
SOUND_PROFILES: dict[Sound, tuple[int, int]] = {
    Sound.CARD_DONE: (800, 100),  # Soft ding
    Sound.EMAIL_SENT: (600, 150),  # Whoosh
    Sound.DEMO_SET: (1000, 200),  # Chime
    Sound.DEAL_CLOSED: (1200, 400),  # Celebration
    Sound.ERROR: (300, 200),  # Gentle buzz
    Sound.STREAK: (900, 300),  # Level-up
}


class AudioManager:
    """Manages sound feedback with mute and per-sound toggles."""

    def __init__(self) -> None:
        self._muted: bool = False
        self._volume: float = 1.0  # 0.0 - 1.0
        self._disabled_sounds: set[Sound] = set()
        self._play_fn: Optional[Callable[[Sound], None]] = None

    def play_sound(self, sound: Sound) -> bool:
        """Play a sound effect.

        Returns True if sound was played, False if muted/disabled.
        """
        if self._muted:
            return False
        if sound in self._disabled_sounds:
            return False

        if self._play_fn:
            try:
                self._play_fn(sound)
            except Exception:
                logger.debug("Custom play function failed", exc_info=True)
                return False
            return True

        # Default: attempt winsound on Windows, log on other platforms
        return self._default_play(sound)

    def set_muted(self, muted: bool) -> None:
        """Set global mute state."""
        self._muted = muted

    def is_muted(self) -> bool:
        """Check if globally muted."""
        return self._muted

    def set_volume(self, volume: float) -> None:
        """Set master volume (0.0 - 1.0)."""
        self._volume = max(0.0, min(1.0, volume))

    def get_volume(self) -> float:
        """Get master volume."""
        return self._volume

    def disable_sound(self, sound: Sound) -> None:
        """Disable a specific sound."""
        self._disabled_sounds.add(sound)

    def enable_sound(self, sound: Sound) -> None:
        """Re-enable a specific sound."""
        self._disabled_sounds.discard(sound)

    def is_sound_enabled(self, sound: Sound) -> bool:
        """Check if a specific sound is enabled."""
        return sound not in self._disabled_sounds

    def set_play_function(self, fn: Callable[[Sound], None]) -> None:
        """Set custom play function (for testing or custom audio backends)."""
        self._play_fn = fn

    def _default_play(self, sound: Sound) -> bool:
        """Default sound playback via winsound or log."""
        freq, duration = SOUND_PROFILES.get(sound, (800, 100))
        try:
            import winsound  # type: ignore[import-not-found]

            winsound.Beep(freq, duration)  # type: ignore[attr-defined]
            return True
        except (ImportError, RuntimeError):
            # Not on Windows or no audio — log and continue
            logger.debug(
                "Sound logged (no audio backend)",
                extra={"context": {"sound": sound.value, "freq": freq, "duration": duration}},
            )
            return False
