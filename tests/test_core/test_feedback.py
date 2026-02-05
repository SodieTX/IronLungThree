"""Tests for in-app feedback capture."""

from pathlib import Path

import pytest

from src.core.feedback import FeedbackCapture, FeedbackEntry, FeedbackType


@pytest.fixture
def capture(tmp_path: Path) -> FeedbackCapture:
    return FeedbackCapture(data_dir=tmp_path)


class TestFeedbackCapture:
    def test_submit_bug(self, capture: FeedbackCapture) -> None:
        entry = capture.submit(FeedbackType.BUG, "Button doesn't work")
        assert entry.feedback_type == "bug"
        assert entry.description == "Button doesn't work"
        assert entry.timestamp is not None

    def test_submit_suggestion(self, capture: FeedbackCapture) -> None:
        entry = capture.submit(FeedbackType.SUGGESTION, "Add dark mode")
        assert entry.feedback_type == "suggestion"

    def test_submit_with_context(self, capture: FeedbackCapture) -> None:
        entry = capture.submit(
            FeedbackType.BUG,
            "Crash on save",
            context="Editing prospect card",
        )
        assert entry.context == "Editing prospect card"

    def test_get_all_returns_entries(self, capture: FeedbackCapture) -> None:
        capture.submit(FeedbackType.BUG, "Bug one")
        capture.submit(FeedbackType.SUGGESTION, "Suggestion one")
        entries = capture.get_all()
        assert len(entries) == 2
        assert entries[0].description == "Bug one"
        assert entries[1].description == "Suggestion one"

    def test_count(self, capture: FeedbackCapture) -> None:
        capture.submit(FeedbackType.BUG, "Bug one")
        capture.submit(FeedbackType.BUG, "Bug two")
        assert capture.count() == 2

    def test_empty_get_all(self, capture: FeedbackCapture) -> None:
        assert capture.get_all() == []

    def test_persistence_across_instances(self, tmp_path: Path) -> None:
        c1 = FeedbackCapture(data_dir=tmp_path)
        c1.submit(FeedbackType.BUG, "Persistent bug")

        c2 = FeedbackCapture(data_dir=tmp_path)
        entries = c2.get_all()
        assert len(entries) == 1
        assert entries[0].description == "Persistent bug"

    def test_handles_corrupt_file(self, tmp_path: Path) -> None:
        (tmp_path / "feedback.jsonl").write_text("not json\n", encoding="utf-8")
        capture = FeedbackCapture(data_dir=tmp_path)
        entries = capture.get_all()
        assert entries == []
