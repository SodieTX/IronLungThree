"""Tests for style learner."""

import os
from pathlib import Path

import pytest

from src.ai.style_learner import STYLE_DIR, analyze_style, get_style_prompt, load_examples


class TestLoadExamples:
    """Test loading email examples."""

    def test_returns_empty_when_no_dir(self, tmp_path, monkeypatch):
        """Returns empty list when style dir doesn't exist."""
        monkeypatch.setattr("src.ai.style_learner.STYLE_DIR", tmp_path / "nonexistent")
        result = load_examples()
        assert result == []

    def test_loads_txt_files(self, tmp_path, monkeypatch):
        """Loads .txt files from style directory."""
        monkeypatch.setattr("src.ai.style_learner.STYLE_DIR", tmp_path)
        (tmp_path / "01_intro.txt").write_text("Hey John, wanted to reach out...")
        (tmp_path / "02_followup.txt").write_text("Hi Sarah, following up on...")
        (tmp_path / "not_an_email.md").write_text("This should be ignored")

        result = load_examples()
        assert len(result) == 2
        assert "Hey John" in result[0]
        assert "Hi Sarah" in result[1]

    def test_skips_empty_files(self, tmp_path, monkeypatch):
        """Skips empty text files."""
        monkeypatch.setattr("src.ai.style_learner.STYLE_DIR", tmp_path)
        (tmp_path / "01_empty.txt").write_text("")
        (tmp_path / "02_content.txt").write_text("Real content here")

        result = load_examples()
        assert len(result) == 1

    def test_sorts_alphabetically(self, tmp_path, monkeypatch):
        """Files are sorted by name."""
        monkeypatch.setattr("src.ai.style_learner.STYLE_DIR", tmp_path)
        (tmp_path / "02_second.txt").write_text("Second email")
        (tmp_path / "01_first.txt").write_text("First email")
        (tmp_path / "03_third.txt").write_text("Third email")

        result = load_examples()
        assert "First" in result[0]
        assert "Second" in result[1]
        assert "Third" in result[2]


class TestAnalyzeStyle:
    """Test style analysis."""

    def test_empty_examples(self):
        """Handles empty list gracefully."""
        result = analyze_style([])
        assert result["avg_length"] == 0
        assert result["tone"] == "professional"

    def test_detects_casual_tone(self):
        """Detects casual tone from markers."""
        examples = [
            "Hey John! Thanks for your time today. Really appreciate it.",
            "Hi Sarah, thanks for getting back to me!",
        ]
        result = analyze_style(examples)
        assert "conversational" in result["tone"]

    def test_detects_formal_tone(self):
        """Detects formal tone from markers."""
        examples = [
            "Dear Mr. Johnson, Regards, Jeff Soderstrom",
            "Sincerely yours, please find the information herewith.",
        ]
        result = analyze_style(examples)
        assert "formal" in result["tone"]

    def test_calculates_avg_length(self):
        """Calculates average word count."""
        examples = [
            "One two three four five",  # 5 words
            "One two three four five six seven eight nine ten",  # 10 words
        ]
        result = analyze_style(examples)
        assert result["avg_length"] == 7  # (5+10)//2

    def test_extracts_openers(self):
        """Extracts opening lines."""
        examples = [
            "Hey John, quick note.\nRest of email.",
            "Hi there, following up.\nMore content.",
        ]
        result = analyze_style(examples)
        assert len(result["common_openers"]) == 2


class TestGetStylePrompt:
    """Test style prompt generation."""

    def test_returns_default_when_no_examples(self, tmp_path, monkeypatch):
        """Returns minimal guidance when no examples exist."""
        monkeypatch.setattr("src.ai.style_learner.STYLE_DIR", tmp_path / "nonexistent")
        result = get_style_prompt()
        assert "professional" in result.lower()
        assert "concise" in result.lower()

    def test_includes_examples_when_present(self, tmp_path, monkeypatch):
        """Includes loaded examples in prompt."""
        monkeypatch.setattr("src.ai.style_learner.STYLE_DIR", tmp_path)
        (tmp_path / "01_email.txt").write_text("Hey John, thanks for your time!")

        result = get_style_prompt()
        assert "Hey John" in result
        assert "Example 1" in result
        assert "Style notes" in result
