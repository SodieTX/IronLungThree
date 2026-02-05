"""Tests for AI email generation.

Tests prompt building and response parsing without calling the real API.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.core.config import Config
from src.db.models import Company, Prospect
from src.engine.email_gen import EmailGenerator, GeneratedEmail


@pytest.fixture
def prospect():
    return Prospect(
        id=1,
        company_id=1,
        first_name="John",
        last_name="Doe",
        title="VP of Operations",
    )


@pytest.fixture
def company():
    return Company(
        id=1,
        name="Acme Lending",
        name_normalized="acme lending",
        state="TX",
        size="medium",
        timezone="central",
    )


@pytest.fixture
def gen(tmp_path, monkeypatch):
    """EmailGenerator with mocked config (no API key)."""
    config = Config(
        db_path=tmp_path / "test.db",
        backup_path=tmp_path / "backups",
        log_path=tmp_path / "logs",
    )
    monkeypatch.setattr("src.engine.email_gen.get_config", lambda: config)
    return EmailGenerator()


@pytest.fixture
def gen_with_key(tmp_path, monkeypatch):
    """EmailGenerator with a fake API key configured."""
    config = Config(
        db_path=tmp_path / "test.db",
        backup_path=tmp_path / "backups",
        log_path=tmp_path / "logs",
        claude_api_key="sk-ant-fake-key",
    )
    monkeypatch.setattr("src.engine.email_gen.get_config", lambda: config)
    return EmailGenerator()


class TestEmailGeneratorConfig:
    """Test configuration checks."""

    def test_is_available_without_key(self, gen):
        """is_available returns False without API key."""
        assert gen.is_available() is False

    def test_is_available_with_key(self, gen_with_key):
        """is_available returns True with API key."""
        assert gen_with_key.is_available() is True


class TestBuildPrompt:
    """Test prompt construction."""

    def test_prompt_includes_prospect_info(self, gen, prospect, company):
        """Prompt includes prospect name, title, company."""
        prompt = gen._build_prompt(prospect, company, "Write an intro email", None)
        assert "John Doe" in prompt
        assert "VP of Operations" in prompt
        assert "Acme Lending" in prompt

    def test_prompt_includes_instruction(self, gen, prospect, company):
        """Prompt includes Jeff's instruction."""
        prompt = gen._build_prompt(prospect, company, "mention fix-and-flip", None)
        assert "mention fix-and-flip" in prompt

    def test_prompt_includes_context(self, gen, prospect, company):
        """Prompt includes additional context."""
        prompt = gen._build_prompt(
            prospect,
            company,
            "follow up",
            context="They asked about API integrations in last demo",
        )
        assert "API integrations" in prompt

    def test_prompt_includes_location(self, gen, prospect, company):
        """Prompt includes company state."""
        prompt = gen._build_prompt(prospect, company, "intro", None)
        assert "TX" in prompt

    def test_prompt_includes_format_instructions(self, gen, prospect, company):
        """Prompt tells Claude to use SUBJECT/BODY format."""
        prompt = gen._build_prompt(prospect, company, "intro", None)
        assert "SUBJECT:" in prompt
        assert "BODY:" in prompt

    def test_prompt_without_context(self, gen, prospect, company):
        """Prompt works without additional context."""
        prompt = gen._build_prompt(prospect, company, "intro", None)
        assert "Additional context" not in prompt


class TestStyleGuidance:
    """Test style example integration."""

    def test_no_style_examples(self, gen):
        """No style guidance when no examples provided."""
        assert gen._get_style_guidance() == ""

    def test_style_examples_included(self, tmp_path, monkeypatch):
        """Style examples are included in guidance."""
        config = Config(
            db_path=tmp_path / "test.db",
            backup_path=tmp_path / "backups",
            log_path=tmp_path / "logs",
        )
        monkeypatch.setattr("src.engine.email_gen.get_config", lambda: config)
        gen = EmailGenerator(
            style_examples=["Hi Bob, quick note...", "Hey Sarah, circling back..."]
        )
        guidance = gen._get_style_guidance()
        assert "Hi Bob" in guidance
        assert "Hey Sarah" in guidance

    def test_style_guidance_limits_to_3(self, tmp_path, monkeypatch):
        """Style guidance uses at most 3 examples."""
        config = Config(
            db_path=tmp_path / "test.db",
            backup_path=tmp_path / "backups",
            log_path=tmp_path / "logs",
        )
        monkeypatch.setattr("src.engine.email_gen.get_config", lambda: config)
        gen = EmailGenerator(style_examples=[f"Example {i}" for i in range(10)])
        guidance = gen._get_style_guidance()
        assert "Example 0" in guidance
        assert "Example 2" in guidance
        assert "Example 3" not in guidance


class TestParseResponse:
    """Test Claude response parsing."""

    def test_parse_standard_response(self, gen):
        """Parse standard SUBJECT/BODY format."""
        text = "SUBJECT: Quick intro\nBODY:\nHi John,\n\nJust reaching out."
        result = gen._parse_response(text, 100)
        assert result.subject == "Quick intro"
        assert result.body == "Hi John,\n\nJust reaching out."
        assert result.tokens_used == 100

    def test_parse_response_no_format(self, gen):
        """Response without SUBJECT/BODY uses full text as body."""
        text = "Hi John,\n\nJust reaching out."
        result = gen._parse_response(text, 50)
        assert result.subject == ""
        assert result.body == "Hi John,\n\nJust reaching out."

    def test_parse_response_multiline_body(self, gen):
        """Parse response with multiline body."""
        text = (
            "SUBJECT: Follow up\n"
            "BODY:\n"
            "Hi John,\n\n"
            "I wanted to follow up.\n\n"
            "Best,\nJeff"
        )
        result = gen._parse_response(text, 200)
        assert result.subject == "Follow up"
        assert "follow up" in result.body
        assert "Jeff" in result.body


class TestGeneratedEmailDataclass:
    """Test the GeneratedEmail dataclass."""

    def test_defaults(self):
        """Defaults are sensible."""
        email = GeneratedEmail(subject="Test", body="Hello")
        assert email.body_html is None
        assert email.tokens_used == 0

    def test_all_fields(self):
        """All fields can be set."""
        email = GeneratedEmail(
            subject="Test",
            body="Hello",
            body_html="<p>Hello</p>",
            tokens_used=150,
        )
        assert email.subject == "Test"
        assert email.body_html == "<p>Hello</p>"
        assert email.tokens_used == 150
