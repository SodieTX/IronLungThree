"""Tests for offline simulation clients."""

from datetime import datetime, timezone

import pytest

from src.integrations.offline import (
    OfflineEmailGenerator,
    OfflineOutlookClient,
    SimulatedEmail,
)


class TestOfflineOutlookClient:
    """Tests for OfflineOutlookClient."""

    def test_health_check_returns_false(self):
        client = OfflineOutlookClient()
        assert client.health_check() is False

    def test_is_configured_returns_false(self):
        client = OfflineOutlookClient()
        assert client.is_configured() is False

    def test_authenticate_returns_true(self):
        client = OfflineOutlookClient()
        assert client.authenticate() is True

    def test_send_email_returns_sim_id(self):
        client = OfflineOutlookClient()
        msg_id = client.send_email(
            to="test@example.com",
            subject="Test Subject",
            body="Test body",
        )
        assert msg_id.startswith("sim-sent-")

    def test_send_email_increments_counter(self):
        client = OfflineOutlookClient()
        id1 = client.send_email(to="a@b.com", subject="s", body="b")
        id2 = client.send_email(to="c@d.com", subject="s", body="b")
        assert id1 != id2
        assert "1" in id1
        assert "2" in id2

    def test_create_draft_returns_sim_id(self):
        client = OfflineOutlookClient()
        draft_id = client.create_draft(
            to="test@example.com",
            subject="Draft Subject",
            body="Draft body",
        )
        assert draft_id.startswith("sim-draft-")

    def test_get_inbox_returns_empty_list(self):
        client = OfflineOutlookClient()
        messages = client.get_inbox()
        assert messages == []

    def test_get_inbox_with_since(self):
        client = OfflineOutlookClient()
        messages = client.get_inbox(
            since=datetime(2026, 1, 1, tzinfo=timezone.utc)
        )
        assert messages == []

    def test_classify_reply_returns_unknown(self):
        client = OfflineOutlookClient()
        result = client.classify_reply(None)
        assert result == "unknown"

    def test_create_event_returns_sim_id(self):
        client = OfflineOutlookClient()
        event_id = client.create_event(
            subject="Meeting",
            start=datetime(2026, 2, 10, 14, 0, tzinfo=timezone.utc),
        )
        assert event_id.startswith("sim-event-")

    def test_get_events_returns_empty_list(self):
        client = OfflineOutlookClient()
        events = client.get_events(
            start=datetime(2026, 2, 10, tzinfo=timezone.utc),
            end=datetime(2026, 2, 11, tzinfo=timezone.utc),
        )
        assert events == []

    def test_update_event_returns_true(self):
        client = OfflineOutlookClient()
        assert client.update_event("fake-id") is True

    def test_delete_event_returns_true(self):
        client = OfflineOutlookClient()
        assert client.delete_event("fake-id") is True

    def test_send_email_with_optional_params(self):
        client = OfflineOutlookClient()
        msg_id = client.send_email(
            to="test@example.com",
            subject="Test",
            body="Body",
            html=True,
            cc=["cc@example.com"],
            bcc=["bcc@example.com"],
        )
        assert msg_id.startswith("sim-sent-")


class TestOfflineEmailGenerator:
    """Tests for OfflineEmailGenerator."""

    def test_is_available_returns_false(self):
        gen = OfflineEmailGenerator()
        assert gen.is_available() is False

    def test_generate_email_returns_simulated(self):
        gen = OfflineEmailGenerator()

        # Minimal prospect/company-like objects
        class FakeProspect:
            first_name = "John"
            last_name = "Doe"

        class FakeCompany:
            name = "Acme Corp"

        result = gen.generate_email(
            prospect=FakeProspect(),
            company=FakeCompany(),
            instruction="Write a short intro email",
        )
        assert isinstance(result, SimulatedEmail)
        assert "[SIMULATED]" in result.subject
        assert "John" in result.body
        assert "Acme Corp" in result.body
        assert result.tokens_used == 0

    def test_generate_email_increments_counter(self):
        gen = OfflineEmailGenerator()

        class P:
            first_name = "A"
            last_name = "B"

        class C:
            name = "X"

        gen.generate_email(P(), C(), "first")
        gen.generate_email(P(), C(), "second")
        assert gen._gen_count == 2

    def test_refine_email_returns_simulated(self):
        gen = OfflineEmailGenerator()
        result = gen.refine_email(
            draft="Original email text",
            feedback="Make it shorter",
        )
        assert isinstance(result, SimulatedEmail)
        assert "Original email text" in result.body
        assert "Make it shorter" in result.body
        assert result.tokens_used == 0

    def test_generate_email_with_context(self):
        gen = OfflineEmailGenerator()

        class P:
            first_name = "Jane"
            last_name = "Smith"

        class C:
            name = "BigCo"

        result = gen.generate_email(
            prospect=P(),
            company=C(),
            instruction="Follow up on demo",
            context="They asked about pricing",
        )
        assert "Jane" in result.body
