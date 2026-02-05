"""Tests for Outlook integration.

Tests use mocked MSAL and requests to avoid real API calls.
Skipped automatically when msal package is not installed.
"""

from unittest.mock import MagicMock, patch

import pytest

try:
    import msal  # noqa: F401

    HAS_MSAL = True
except ImportError:
    HAS_MSAL = False

pytestmark = pytest.mark.skipif(not HAS_MSAL, reason="msal not installed")

from src.core.config import Config, reset_config
from src.core.exceptions import OutlookError
from src.integrations.outlook import (
    GRAPH_BASE_URL,
    CalendarEvent,
    EmailMessage,
    OutlookClient,
    ReplyClassification,
)


@pytest.fixture
def outlook_config(tmp_path, monkeypatch):
    """Provide an OutlookClient with test credentials configured."""
    config = Config(
        db_path=tmp_path / "test.db",
        backup_path=tmp_path / "backups",
        log_path=tmp_path / "logs",
        outlook_client_id="test-client-id",
        outlook_client_secret="test-client-secret",
        outlook_tenant_id="test-tenant-id",
        outlook_user_email="jeff@nexys.com",
    )
    (tmp_path).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("src.integrations.outlook.get_config", lambda: config)
    return config


@pytest.fixture
def unconfigured_config(tmp_path, monkeypatch):
    """Provide an OutlookClient with NO credentials configured."""
    config = Config(
        db_path=tmp_path / "test.db",
        backup_path=tmp_path / "backups",
        log_path=tmp_path / "logs",
    )
    monkeypatch.setattr("src.integrations.outlook.get_config", lambda: config)
    return config


@pytest.fixture
def mock_msal(outlook_config):
    """Mock the MSAL ConfidentialClientApplication."""
    with patch("src.integrations.outlook.msal") as mocked:
        mock_cache = MagicMock()
        mock_cache.has_state_changed = False
        mocked.SerializableTokenCache.return_value = mock_cache

        mock_app = MagicMock()
        mock_app.token_cache = mock_cache
        mock_app.acquire_token_for_client.return_value = {
            "access_token": "fake-token-abc123",
            "expires_in": 3600,
        }
        mocked.ConfidentialClientApplication.return_value = mock_app

        yield mocked, mock_app


class TestOutlookConfig:
    """Test Outlook configuration checks."""

    def test_is_configured_with_all_credentials(self, outlook_config):
        """is_configured returns True when all creds present."""
        client = OutlookClient()
        assert client.is_configured() is True

    def test_is_configured_without_credentials(self, unconfigured_config):
        """is_configured returns False without credentials."""
        client = OutlookClient()
        assert client.is_configured() is False

    def test_is_configured_partial_credentials(self, tmp_path, monkeypatch):
        """is_configured returns False with partial creds."""
        config = Config(
            db_path=tmp_path / "test.db",
            backup_path=tmp_path / "backups",
            log_path=tmp_path / "logs",
            outlook_client_id="test-client-id",
            # Missing secret and tenant
        )
        monkeypatch.setattr("src.integrations.outlook.get_config", lambda: config)
        client = OutlookClient()
        assert client.is_configured() is False

    def test_is_configured_missing_user_email(self, tmp_path, monkeypatch):
        """is_configured returns False when user email is missing."""
        config = Config(
            db_path=tmp_path / "test.db",
            backup_path=tmp_path / "backups",
            log_path=tmp_path / "logs",
            outlook_client_id="test-client-id",
            outlook_client_secret="test-secret",
            outlook_tenant_id="test-tenant",
            # Missing user email
        )
        monkeypatch.setattr("src.integrations.outlook.get_config", lambda: config)
        client = OutlookClient()
        assert client.is_configured() is False


class TestOutlookAuth:
    """Test OAuth2 authentication flow."""

    def test_authenticate_success(self, mock_msal):
        """Authentication succeeds with valid credentials."""
        mocked, mock_app = mock_msal
        client = OutlookClient()
        result = client.authenticate()
        assert result is True
        assert client._access_token == "fake-token-abc123"
        assert client._token_expiry is not None

    def test_authenticate_failure(self, mock_msal):
        """Authentication raises OutlookError on failure."""
        mocked, mock_app = mock_msal
        mock_app.acquire_token_for_client.return_value = {
            "error": "invalid_client",
            "error_description": "Bad credentials",
        }
        client = OutlookClient()
        with pytest.raises(OutlookError, match="Authentication failed"):
            client.authenticate()

    def test_authenticate_not_configured(self, unconfigured_config):
        """Authentication raises OutlookError when not configured."""
        client = OutlookClient()
        with pytest.raises(OutlookError, match="not configured"):
            client.authenticate()

    def test_token_reuse_when_valid(self, mock_msal):
        """_ensure_authenticated does not re-auth if token is valid."""
        mocked, mock_app = mock_msal
        client = OutlookClient()
        client.authenticate()
        call_count = mock_app.acquire_token_for_client.call_count

        # Should not call MSAL again — token is still valid
        client._ensure_authenticated()
        assert mock_app.acquire_token_for_client.call_count == call_count

    def test_token_refresh_when_expired(self, mock_msal):
        """_ensure_authenticated re-auths when token expired."""
        from datetime import datetime, timezone

        mocked, mock_app = mock_msal
        client = OutlookClient()
        client.authenticate()

        # Simulate expired token
        client._token_expiry = datetime(2020, 1, 1, tzinfo=timezone.utc)
        client._ensure_authenticated()

        # Should have called authenticate again
        assert mock_app.acquire_token_for_client.call_count == 2


class TestOutlookSendEmail:
    """Test email sending."""

    def test_send_email_success(self, mock_msal):
        """Send email returns message ID on 202 response."""
        mocked, mock_app = mock_msal
        client = OutlookClient()
        client.authenticate()

        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.text = ""

        with patch("src.integrations.outlook.requests") as mock_requests:
            mock_requests.request.return_value = mock_response
            mock_requests.RequestException = Exception

            msg_id = client.send_email(
                to="prospect@example.com",
                subject="Intro",
                body="Hello there",
            )

            assert msg_id.startswith("sent-")
            call_args = mock_requests.request.call_args
            assert call_args.kwargs["method"] == "POST"
            assert "/sendMail" in call_args.kwargs["url"]

    def test_send_email_with_html(self, mock_msal):
        """Send email with HTML body sets correct content type."""
        mocked, mock_app = mock_msal
        client = OutlookClient()
        client.authenticate()

        mock_response = MagicMock()
        mock_response.status_code = 202

        with patch("src.integrations.outlook.requests") as mock_requests:
            mock_requests.request.return_value = mock_response
            mock_requests.RequestException = Exception

            client.send_email(
                to="prospect@example.com",
                subject="Intro",
                body="<p>Hello</p>",
                html=True,
            )

            payload = mock_requests.request.call_args.kwargs["json"]
            assert payload["message"]["body"]["contentType"] == "HTML"

    def test_send_email_with_cc_bcc(self, mock_msal):
        """Send email includes CC and BCC recipients."""
        mocked, mock_app = mock_msal
        client = OutlookClient()
        client.authenticate()

        mock_response = MagicMock()
        mock_response.status_code = 202

        with patch("src.integrations.outlook.requests") as mock_requests:
            mock_requests.request.return_value = mock_response
            mock_requests.RequestException = Exception

            client.send_email(
                to="prospect@example.com",
                subject="Intro",
                body="Hello",
                cc=["cc@example.com"],
                bcc=["bcc@example.com"],
            )

            payload = mock_requests.request.call_args.kwargs["json"]
            assert len(payload["message"]["ccRecipients"]) == 1
            assert (
                payload["message"]["ccRecipients"][0]["emailAddress"]["address"] == "cc@example.com"
            )
            assert len(payload["message"]["bccRecipients"]) == 1

    def test_send_email_failure_raises(self, mock_msal):
        """Send email raises OutlookError on API failure."""
        mocked, mock_app = mock_msal
        client = OutlookClient()
        client.authenticate()

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        with patch("src.integrations.outlook.requests") as mock_requests:
            mock_requests.request.return_value = mock_response
            mock_requests.RequestException = Exception

            with pytest.raises(OutlookError, match="Send failed"):
                client.send_email(
                    to="bad@example.com",
                    subject="Test",
                    body="Hello",
                )

    def test_send_email_dry_run(self, tmp_path, monkeypatch):
        """Dry run mode logs but does not send."""
        config = Config(
            db_path=tmp_path / "test.db",
            backup_path=tmp_path / "backups",
            log_path=tmp_path / "logs",
            outlook_client_id="test-client-id",
            outlook_client_secret="test-client-secret",
            outlook_tenant_id="test-tenant-id",
            outlook_user_email="jeff@nexys.com",
            dry_run=True,
        )
        monkeypatch.setattr("src.integrations.outlook.get_config", lambda: config)

        client = OutlookClient()
        # Should not need authentication for dry_run
        msg_id = client.send_email(
            to="prospect@example.com",
            subject="Intro",
            body="Hello",
        )
        assert msg_id == ""


class TestOutlookCreateDraft:
    """Test draft email creation."""

    def test_create_draft_success(self, mock_msal):
        """Create draft returns draft ID on success."""
        mocked, mock_app = mock_msal
        client = OutlookClient()
        client.authenticate()

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "draft-id-123"}

        with patch("src.integrations.outlook.requests") as mock_requests:
            mock_requests.request.return_value = mock_response

            draft_id = client.create_draft(
                to="prospect@example.com",
                subject="Follow up",
                body="Hi there",
            )

            assert draft_id == "draft-id-123"
            call_args = mock_requests.request.call_args
            assert call_args.kwargs["method"] == "POST"
            assert "/messages" in call_args.kwargs["url"]

    def test_create_draft_failure_raises(self, mock_msal):
        """Create draft raises OutlookError on API failure."""
        mocked, mock_app = mock_msal
        client = OutlookClient()
        client.authenticate()

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"

        with patch("src.integrations.outlook.requests") as mock_requests:
            mock_requests.request.return_value = mock_response

            with pytest.raises(OutlookError, match="Draft creation failed"):
                client.create_draft(
                    to="prospect@example.com",
                    subject="Test",
                    body="Hello",
                )


class TestOutlookHealthCheck:
    """Test health check."""

    def test_health_check_unconfigured(self, unconfigured_config):
        """Health check returns False when not configured."""
        client = OutlookClient()
        assert client.health_check() is False

    def test_health_check_success(self, mock_msal):
        """Health check returns True when API is reachable."""
        mocked, mock_app = mock_msal
        client = OutlookClient()

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("src.integrations.outlook.requests") as mock_requests:
            mock_requests.request.return_value = mock_response
            mock_requests.RequestException = Exception
            assert client.health_check() is True

    def test_health_check_api_failure(self, mock_msal):
        """Health check returns False when API is unreachable."""
        mocked, mock_app = mock_msal
        client = OutlookClient()

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("src.integrations.outlook.requests") as mock_requests:
            mock_requests.request.return_value = mock_response
            mock_requests.RequestException = Exception
            assert client.health_check() is False


class TestReplyClassification:
    """Test reply classification enum."""

    def test_all_classifications_exist(self):
        """All expected classifications are defined."""
        assert ReplyClassification.INTERESTED
        assert ReplyClassification.NOT_INTERESTED
        assert ReplyClassification.OOO
        assert ReplyClassification.REFERRAL
        assert ReplyClassification.UNKNOWN

    def test_classification_values_are_strings(self):
        """Classification values are lowercase strings."""
        assert ReplyClassification.INTERESTED.value == "interested"
        assert ReplyClassification.OOO.value == "ooo"


class TestOutlookGetInbox:
    """Test inbox reading."""

    def test_get_inbox_success(self, mock_msal):
        """Get inbox returns parsed email messages."""
        mocked, mock_app = mock_msal
        client = OutlookClient()
        client.authenticate()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "value": [
                {
                    "id": "msg-1",
                    "from": {"emailAddress": {"address": "sender@test.com"}},
                    "toRecipients": [{"emailAddress": {"address": "jeff@nexys.com"}}],
                    "subject": "Re: Intro",
                    "bodyPreview": "Sounds great, let's talk",
                    "body": {"content": "<p>Sounds great, let's talk</p>"},
                    "receivedDateTime": "2026-02-05T10:30:00Z",
                    "isRead": False,
                }
            ]
        }

        with patch("src.integrations.outlook.requests") as mock_requests:
            mock_requests.request.return_value = mock_response
            messages = client.get_inbox()

        assert len(messages) == 1
        assert messages[0].id == "msg-1"
        assert messages[0].from_address == "sender@test.com"
        assert messages[0].subject == "Re: Intro"
        assert messages[0].is_read is False

    def test_get_inbox_with_since_filter(self, mock_msal):
        """Get inbox includes filter param when since is given."""
        from datetime import datetime, timezone

        mocked, mock_app = mock_msal
        client = OutlookClient()
        client.authenticate()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": []}

        with patch("src.integrations.outlook.requests") as mock_requests:
            mock_requests.request.return_value = mock_response
            since = datetime(2026, 2, 1, tzinfo=timezone.utc)
            client.get_inbox(since=since)

            call_params = mock_requests.request.call_args.kwargs["params"]
            assert "$filter" in call_params
            assert "2026-02-01" in call_params["$filter"]

    def test_get_inbox_failure_raises(self, mock_msal):
        """Get inbox raises OutlookError on API failure."""
        mocked, mock_app = mock_msal
        client = OutlookClient()
        client.authenticate()

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server Error"

        with patch("src.integrations.outlook.requests") as mock_requests:
            mock_requests.request.return_value = mock_response
            with pytest.raises(OutlookError, match="Inbox read failed"):
                client.get_inbox()


class TestClassifyReply:
    """Test email reply classification heuristics."""

    def _make_msg(self, subject: str = "", body: str = "") -> EmailMessage:
        return EmailMessage(
            id="test",
            from_address="sender@test.com",
            to_addresses=["jeff@nexys.com"],
            subject=subject,
            body=body,
        )

    def test_classify_ooo(self):
        """Classify out-of-office auto-reply."""
        client = OutlookClient.__new__(OutlookClient)
        msg = self._make_msg(subject="Automatic Reply: Out of Office")
        assert client.classify_reply(msg) == ReplyClassification.OOO

    def test_classify_ooo_body(self):
        """Classify OOO from body content."""
        client = OutlookClient.__new__(OutlookClient)
        msg = self._make_msg(body="I am currently out of the office until Feb 10")
        assert client.classify_reply(msg) == ReplyClassification.OOO

    def test_classify_not_interested(self):
        """Classify explicit decline."""
        client = OutlookClient.__new__(OutlookClient)
        msg = self._make_msg(body="Not interested, please remove me from your list")
        assert client.classify_reply(msg) == ReplyClassification.NOT_INTERESTED

    def test_classify_not_interested_polite(self):
        """Classify polite decline."""
        client = OutlookClient.__new__(OutlookClient)
        msg = self._make_msg(body="No thank you, we're all set right now.")
        assert client.classify_reply(msg) == ReplyClassification.NOT_INTERESTED

    def test_classify_referral(self):
        """Classify referral to another person."""
        client = OutlookClient.__new__(OutlookClient)
        msg = self._make_msg(
            body="You should reach out to Mike Johnson, he's the right person to talk to"
        )
        assert client.classify_reply(msg) == ReplyClassification.REFERRAL

    def test_classify_interested(self):
        """Classify positive interest signal."""
        client = OutlookClient.__new__(OutlookClient)
        msg = self._make_msg(body="Sounds great, let's set up a call next week")
        assert client.classify_reply(msg) == ReplyClassification.INTERESTED

    def test_classify_interested_short(self):
        """Classify brief positive reply."""
        client = OutlookClient.__new__(OutlookClient)
        msg = self._make_msg(body="Sure, when are you available?")
        assert client.classify_reply(msg) == ReplyClassification.INTERESTED

    def test_classify_unknown(self):
        """Classify ambiguous reply as unknown."""
        client = OutlookClient.__new__(OutlookClient)
        msg = self._make_msg(body="Thanks for the email. Let me think about it.")
        assert client.classify_reply(msg) == ReplyClassification.UNKNOWN

    def test_ooo_takes_priority_over_interested(self):
        """OOO classification takes priority when both signals present."""
        client = OutlookClient.__new__(OutlookClient)
        msg = self._make_msg(
            subject="Automatic Reply", body="I'm interested but I am currently out of the office"
        )
        assert client.classify_reply(msg) == ReplyClassification.OOO


class TestOutlookCalendar:
    """Test calendar operations."""

    def test_create_event_success(self, mock_msal):
        """Create event returns event ID on success."""
        from datetime import datetime, timezone

        mocked, mock_app = mock_msal
        client = OutlookClient()
        client.authenticate()

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "event-id-123"}

        with patch("src.integrations.outlook.requests") as mock_requests:
            mock_requests.request.return_value = mock_response

            event_id = client.create_event(
                subject="Demo with Acme Corp",
                start=datetime(2026, 2, 10, 14, 0, tzinfo=timezone.utc),
                duration_minutes=30,
                attendees=["prospect@acme.com"],
            )

            assert event_id == "event-id-123"
            payload = mock_requests.request.call_args.kwargs["json"]
            assert payload["subject"] == "Demo with Acme Corp"
            assert len(payload["attendees"]) == 1

    def test_create_event_with_teams(self, mock_msal):
        """Create event with Teams meeting link."""
        from datetime import datetime, timezone

        mocked, mock_app = mock_msal
        client = OutlookClient()
        client.authenticate()

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "event-teams-123"}

        with patch("src.integrations.outlook.requests") as mock_requests:
            mock_requests.request.return_value = mock_response

            client.create_event(
                subject="Demo",
                start=datetime(2026, 2, 10, 14, 0, tzinfo=timezone.utc),
                teams_meeting=True,
            )

            payload = mock_requests.request.call_args.kwargs["json"]
            assert payload["isOnlineMeeting"] is True
            assert payload["onlineMeetingProvider"] == "teamsForBusiness"

    def test_create_event_failure_raises(self, mock_msal):
        """Create event raises OutlookError on API failure."""
        from datetime import datetime, timezone

        mocked, mock_app = mock_msal
        client = OutlookClient()
        client.authenticate()

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        with patch("src.integrations.outlook.requests") as mock_requests:
            mock_requests.request.return_value = mock_response
            with pytest.raises(OutlookError, match="Event creation failed"):
                client.create_event(
                    subject="Demo",
                    start=datetime(2026, 2, 10, 14, 0, tzinfo=timezone.utc),
                )

    def test_get_events_success(self, mock_msal):
        """Get events returns parsed calendar events."""
        from datetime import datetime, timezone

        mocked, mock_app = mock_msal
        client = OutlookClient()
        client.authenticate()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "value": [
                {
                    "id": "evt-1",
                    "subject": "Demo with Acme",
                    "start": {"dateTime": "2026-02-10T14:00:00"},
                    "end": {"dateTime": "2026-02-10T14:30:00"},
                    "location": {"displayName": "Teams"},
                    "attendees": [{"emailAddress": {"address": "p@acme.com"}}],
                    "onlineMeeting": {"joinUrl": "https://teams.link/123"},
                    "body": {"content": "Demo description"},
                }
            ]
        }

        with patch("src.integrations.outlook.requests") as mock_requests:
            mock_requests.request.return_value = mock_response
            events = client.get_events(
                start=datetime(2026, 2, 10, tzinfo=timezone.utc),
                end=datetime(2026, 2, 11, tzinfo=timezone.utc),
            )

        assert len(events) == 1
        assert events[0].id == "evt-1"
        assert events[0].subject == "Demo with Acme"
        assert events[0].teams_link == "https://teams.link/123"
        assert events[0].attendees == ["p@acme.com"]

    def test_update_event_success(self, mock_msal):
        """Update event returns True on success."""
        mocked, mock_app = mock_msal
        client = OutlookClient()
        client.authenticate()

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("src.integrations.outlook.requests") as mock_requests:
            mock_requests.request.return_value = mock_response
            result = client.update_event("evt-1", subject="Updated Demo")
            assert result is True
            assert mock_requests.request.call_args.kwargs["method"] == "PATCH"

    def test_delete_event_success(self, mock_msal):
        """Delete event returns True on success."""
        mocked, mock_app = mock_msal
        client = OutlookClient()
        client.authenticate()

        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch("src.integrations.outlook.requests") as mock_requests:
            mock_requests.request.return_value = mock_response
            result = client.delete_event("evt-1")
            assert result is True
            assert mock_requests.request.call_args.kwargs["method"] == "DELETE"

    def test_delete_event_failure_raises(self, mock_msal):
        """Delete event raises OutlookError on API failure."""
        mocked, mock_app = mock_msal
        client = OutlookClient()
        client.authenticate()

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        with patch("src.integrations.outlook.requests") as mock_requests:
            mock_requests.request.return_value = mock_response
            with pytest.raises(OutlookError, match="Event deletion failed"):
                client.delete_event("evt-nonexistent")
