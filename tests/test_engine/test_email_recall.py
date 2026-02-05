"""Tests for email recall — the Oh Shit button."""

from unittest.mock import MagicMock

import pytest

from src.engine.email_recall import RecallResult, attempt_recall


@pytest.fixture
def mock_outlook():
    """Mocked OutlookClient for recall tests."""
    outlook = MagicMock()
    outlook._user_email = "jeff@nexys.com"

    # Default: delete succeeds, message readable
    delete_response = MagicMock()
    delete_response.status_code = 204

    get_response = MagicMock()
    get_response.status_code = 200
    get_response.json.return_value = {
        "subject": "Quick intro",
        "toRecipients": [
            {"emailAddress": {"address": "prospect@acme.com"}}
        ],
    }

    def graph_request(method, endpoint, **kwargs):
        if method == "DELETE":
            return delete_response
        elif method == "GET":
            return get_response
        return MagicMock(status_code=500)

    outlook._graph_request = MagicMock(side_effect=graph_request)
    outlook.send_email = MagicMock(return_value="sent-recall")

    return outlook


class TestAttemptRecall:
    """Test recall flow."""

    def test_recall_with_follow_up(self, mock_outlook):
        """Full recall: delete + send follow-up."""
        result = attempt_recall(mock_outlook, "msg-123")

        assert result.success is True
        assert result.method == "follow_up"
        assert "please disregard" in result.message.lower() or "prospect@acme.com" in result.message

        # Verify follow-up was sent
        mock_outlook.send_email.assert_called_once()
        call_kwargs = mock_outlook.send_email.call_args.kwargs
        assert call_kwargs["to"] == "prospect@acme.com"
        assert "disregard" in call_kwargs["subject"].lower()

    def test_recall_delete_only(self, mock_outlook):
        """Recall without follow-up just deletes."""
        result = attempt_recall(mock_outlook, "msg-123", send_follow_up=False)

        assert result.success is True
        assert result.method == "deleted"
        mock_outlook.send_email.assert_not_called()

    def test_recall_custom_follow_up_text(self, mock_outlook):
        """Custom follow-up text is used."""
        result = attempt_recall(
            mock_outlook, "msg-123",
            follow_up_text="Wrong attachment! Correct one attached.",
        )

        assert result.success is True
        call_kwargs = mock_outlook.send_email.call_args.kwargs
        assert "Wrong attachment" in call_kwargs["body"]

    def test_recall_no_message_id(self, mock_outlook):
        """Recall fails with no message ID."""
        result = attempt_recall(mock_outlook, "")
        assert result.success is False
        assert result.method == "failed"

    def test_recall_delete_fails(self, mock_outlook):
        """When delete fails, follow-up is still attempted."""
        fail_response = MagicMock()
        fail_response.status_code = 404

        get_response = MagicMock()
        get_response.status_code = 200
        get_response.json.return_value = {
            "subject": "Test",
            "toRecipients": [
                {"emailAddress": {"address": "p@acme.com"}}
            ],
        }

        def graph_request(method, endpoint, **kwargs):
            if method == "DELETE":
                return fail_response
            return get_response

        mock_outlook._graph_request = MagicMock(side_effect=graph_request)

        result = attempt_recall(mock_outlook, "msg-123")
        assert result.success is True  # Follow-up still sent
        assert result.method == "follow_up"

    def test_recall_everything_fails(self, mock_outlook):
        """When everything fails, returns failure result."""
        mock_outlook._graph_request = MagicMock(
            side_effect=Exception("Network error")
        )

        result = attempt_recall(mock_outlook, "msg-123", send_follow_up=False)
        assert result.success is False
        assert result.method == "failed"


class TestRecallResult:
    """Test RecallResult dataclass."""

    def test_defaults(self):
        result = RecallResult(success=True)
        assert result.method == ""
        assert result.message == ""
