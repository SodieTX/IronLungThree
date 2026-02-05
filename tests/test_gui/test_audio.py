"""Tests for audio feedback — sound playback, mute, per-sound toggles."""

import pytest

from src.gui.adhd.audio import AudioManager, Sound


@pytest.fixture
def audio() -> AudioManager:
    return AudioManager()


class TestPlaySound:
    def test_play_with_custom_fn(self, audio: AudioManager) -> None:
        played: list[Sound] = []
        audio.set_play_function(lambda s: played.append(s))
        assert audio.play_sound(Sound.CARD_DONE) is True
        assert played == [Sound.CARD_DONE]

    def test_play_muted_returns_false(self, audio: AudioManager) -> None:
        played: list[Sound] = []
        audio.set_play_function(lambda s: played.append(s))
        audio.set_muted(True)
        assert audio.play_sound(Sound.CARD_DONE) is False
        assert len(played) == 0

    def test_play_disabled_sound_returns_false(self, audio: AudioManager) -> None:
        played: list[Sound] = []
        audio.set_play_function(lambda s: played.append(s))
        audio.disable_sound(Sound.ERROR)
        assert audio.play_sound(Sound.ERROR) is False
        assert len(played) == 0

    def test_play_enabled_after_reenable(self, audio: AudioManager) -> None:
        played: list[Sound] = []
        audio.set_play_function(lambda s: played.append(s))
        audio.disable_sound(Sound.CARD_DONE)
        audio.enable_sound(Sound.CARD_DONE)
        assert audio.play_sound(Sound.CARD_DONE) is True

    def test_default_play_on_linux(self, audio: AudioManager) -> None:
        # On Linux, winsound is not available — should return False gracefully
        result = audio.play_sound(Sound.CARD_DONE)
        assert result is False  # No winsound on Linux

    def test_custom_fn_exception_handled(self, audio: AudioManager) -> None:
        def bad_fn(s: Sound) -> None:
            raise RuntimeError("audio crash")

        audio.set_play_function(bad_fn)
        assert audio.play_sound(Sound.CARD_DONE) is False


class TestMuteState:
    def test_not_muted_initially(self, audio: AudioManager) -> None:
        assert audio.is_muted() is False

    def test_set_muted(self, audio: AudioManager) -> None:
        audio.set_muted(True)
        assert audio.is_muted() is True

    def test_unmute(self, audio: AudioManager) -> None:
        audio.set_muted(True)
        audio.set_muted(False)
        assert audio.is_muted() is False


class TestVolume:
    def test_default_volume(self, audio: AudioManager) -> None:
        assert audio.get_volume() == 1.0

    def test_set_volume(self, audio: AudioManager) -> None:
        audio.set_volume(0.5)
        assert audio.get_volume() == 0.5

    def test_volume_clamped_high(self, audio: AudioManager) -> None:
        audio.set_volume(2.0)
        assert audio.get_volume() == 1.0

    def test_volume_clamped_low(self, audio: AudioManager) -> None:
        audio.set_volume(-0.5)
        assert audio.get_volume() == 0.0


class TestPerSoundToggle:
    def test_all_enabled_initially(self, audio: AudioManager) -> None:
        for sound in Sound:
            assert audio.is_sound_enabled(sound) is True

    def test_disable_specific_sound(self, audio: AudioManager) -> None:
        audio.disable_sound(Sound.ERROR)
        assert audio.is_sound_enabled(Sound.ERROR) is False
        assert audio.is_sound_enabled(Sound.CARD_DONE) is True
