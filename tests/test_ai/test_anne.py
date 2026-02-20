"""Tests for Anne - The conversational AI assistant."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from src.ai.anne import Anne, AnneResponse, ConversationContext


class TestAnneInit:
    """Test Anne initialization."""

    def test_creates_without_api_key(self, populated_db, monkeypatch):
        """Anne initializes without API key (offline mode)."""
        monkeypatch.setattr("src.ai.anne.get_config", lambda: MagicMock(claude_api_key=None))
        anne = Anne(populated_db)
        assert not anne.is_available()

    def test_is_available_with_key(self, populated_db, monkeypatch):
        """Reports available when API key is set."""
        monkeypatch.setattr("src.ai.anne.get_config", lambda: MagicMock(claude_api_key="test-key"))
        anne = Anne(populated_db)
        assert anne.is_available()


class TestPresentCard:
    """Test card presentation."""

    def test_presents_card_locally(self, populated_db, monkeypatch):
        """Falls back to local presentation without API."""
        monkeypatch.setattr("src.ai.anne.get_config", lambda: MagicMock(claude_api_key=None))
        anne = Anne(populated_db)
        prospects = populated_db.get_prospects()
        assert len(prospects) > 0

        result = anne.present_card(prospects[0].id)
        # Should contain the prospect's name (could be John or Jane)
        assert "Acme" in result

    def test_returns_pre_generated(self, populated_db, monkeypatch):
        """Returns pre-generated presentation if cached."""
        monkeypatch.setattr("src.ai.anne.get_config", lambda: MagicMock(claude_api_key=None))
        anne = Anne(populated_db)
        anne._pre_generated[1] = "Pre-generated card for prospect 1"

        result = anne.present_card(1)
        assert result == "Pre-generated card for prospect 1"
        assert 1 not in anne._pre_generated  # consumed from cache

    def test_missing_prospect(self, populated_db, monkeypatch):
        """Handles missing prospect."""
        monkeypatch.setattr("src.ai.anne.get_config", lambda: MagicMock(claude_api_key=None))
        anne = Anne(populated_db)
        result = anne.present_card(99999)
        assert "can't find" in result.lower()


class TestRespond:
    """Test Anne's response to user input."""

    @pytest.fixture
    def anne(self, populated_db, monkeypatch):
        monkeypatch.setattr("src.ai.anne.get_config", lambda: MagicMock(claude_api_key=None))
        return Anne(populated_db)

    @pytest.fixture
    def context(self):
        return ConversationContext(current_prospect_id=1)

    def test_confirm(self, anne, context):
        result = anne.respond("yes", context)
        assert "executing" in result.message.lower()

    def test_deny(self, anne, context):
        result = anne.respond("no", context)
        assert "cancelled" in result.message.lower()

    def test_skip(self, anne, context):
        result = anne.respond("skip", context)
        assert result.suggested_actions is not None
        assert result.suggested_actions[0]["action"] == "skip"

    def test_undo(self, anne, context):
        result = anne.respond("undo", context)
        assert result.suggested_actions is not None
        assert result.suggested_actions[0]["action"] == "undo"

    def test_defer(self, anne, context):
        result = anne.respond("defer", context)
        assert "deferred" in result.message.lower()

    def test_voicemail(self, anne, context):
        result = anne.respond("lv", context)
        assert "voicemail" in result.message.lower()
        assert result.suggested_actions is not None
        assert result.suggested_actions[0]["action"] == "log_activity"

    def test_no_answer(self, anne, context):
        result = anne.respond("no answer", context)
        assert result.suggested_actions is not None
        assert result.suggested_actions[0]["outcome"] == "no_answer"

    def test_send_email(self, anne, context):
        result = anne.respond("send him an email", context)
        assert "email" in result.message.lower()

    def test_dial(self, anne, context):
        result = anne.respond("dial him", context)
        assert "dialing" in result.message.lower()

    def test_park_with_month(self, anne, context):
        result = anne.respond("park him until june", context)
        assert result.requires_confirmation
        assert "park" in result.message.lower()

    def test_park_without_month(self, anne, context):
        result = anne.respond("park him", context)
        assert "when" in result.message.lower()

    def test_schedule_demo(self, anne, context):
        result = anne.respond("schedule a demo", context)
        assert result.requires_confirmation
        assert "demo" in result.message.lower()

    def test_follow_up_with_date(self, anne, context):
        result = anne.respond("follow up next tuesday", context)
        assert result.suggested_actions is not None
        assert result.suggested_actions[0]["action"] == "set_follow_up"

    def test_follow_up_without_date(self, anne, context):
        result = anne.respond("follow up", context)
        assert "when" in result.message.lower()

    def test_dnc_requires_confirmation(self, anne, context):
        result = anne.respond("hard no", context)
        assert result.requires_confirmation
        assert "permanent" in result.message.lower()

    def test_engaged_asks_for_followup(self, anne, context):
        result = anne.respond("he's interested", context)
        assert "follow-up" in result.message.lower() or "follow up" in result.message.lower()

    def test_wrong_number_flags_suspect(self, anne, context):
        result = anne.respond("wrong number", context)
        assert "suspect" in result.message.lower() or "flagging" in result.message.lower()

    def test_default_note(self, anne, context):
        result = anne.respond("random thoughts about this prospect", context)
        assert result.suggested_actions is not None
        assert result.suggested_actions[0]["action"] == "log_note"


class TestTakeNotes:
    """Test note-taking."""

    def test_local_fallback(self, populated_db, monkeypatch):
        """Falls back to local note format without API."""
        monkeypatch.setattr("src.ai.anne.get_config", lambda: MagicMock(claude_api_key=None))
        anne = Anne(populated_db)
        result = anne.take_notes(1, "Called John, he was interested")
        assert date.today().isoformat() in result
        assert "Called John" in result


class TestExtractIntel:
    """Test intel extraction."""

    def test_extracts_loan_types(self, populated_db, monkeypatch):
        """Extracts loan type intel from notes."""
        monkeypatch.setattr("src.ai.anne.get_config", lambda: MagicMock(claude_api_key=None))
        anne = Anne(populated_db)
        nuggets = anne.extract_intel(1, "They do bridge and fix and flip lending")
        categories = [n["category"] for n in nuggets]
        assert "loan_type" in categories


class TestPreGenerate:
    """Test card pre-generation."""

    def test_pre_generates_locally(self, populated_db, monkeypatch):
        """Pre-generates card presentations locally."""
        monkeypatch.setattr("src.ai.anne.get_config", lambda: MagicMock(claude_api_key=None))
        anne = Anne(populated_db)
        prospects = populated_db.get_prospects()
        ids = [p.id for p in prospects if p.id is not None]

        result = anne.pre_generate_cards(ids)
        assert len(result) > 0
        # Cached for later use
        for pid in result:
            assert pid in anne._pre_generated


class TestExecuteActions:
    """Test action execution."""

    def test_handles_unknown_action(self, populated_db, monkeypatch):
        """Unknown actions go to failed list."""
        monkeypatch.setattr("src.ai.anne.get_config", lambda: MagicMock(claude_api_key=None))
        anne = Anne(populated_db)
        result = anne.execute_actions([{"action": "teleport"}])
        assert len(result["failed"]) == 1
        assert result["failed"][0]["action"] == "teleport"
