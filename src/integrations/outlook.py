"""Microsoft Outlook integration via Graph API.

Provides:
    - OAuth2 authentication with token refresh
    - Send email (plain text and HTML)
    - Create drafts
    - Read inbox (polling)
    - Reply classification
    - Calendar operations with Teams meeting links

Uses MSAL ConfidentialClientApplication with client credentials flow.
Requires application permissions granted in Azure AD:
    Mail.Send, Mail.ReadWrite, Calendars.ReadWrite

Usage:
    from src.integrations.outlook import OutlookClient

    client = OutlookClient()
    if client.is_configured():
        client.authenticate()
        client.send_email(to="test@example.com", subject="Hello", body="...")
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import msal
import requests

from src.core.config import get_config
from src.core.exceptions import OutlookError
from src.core.logging import get_logger
from src.integrations.base import IntegrationBase

logger = get_logger(__name__)

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPES = ["https://graph.microsoft.com/.default"]


class ReplyClassification(str, Enum):
    """Classification of email reply."""

    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    OOO = "ooo"
    REFERRAL = "referral"
    UNKNOWN = "unknown"


@dataclass
class EmailMessage:
    """Email message from Outlook.

    Attributes:
        id: Message ID
        from_address: Sender email
        to_addresses: Recipient emails
        subject: Email subject
        body: Email body (plain text)
        body_html: Email body (HTML)
        received_at: When received
        is_read: Read status
    """

    id: str
    from_address: str
    to_addresses: list[str]
    subject: str
    body: str
    body_html: Optional[str] = None
    received_at: Optional[datetime] = None
    is_read: bool = False


@dataclass
class CalendarEvent:
    """Calendar event from Outlook.

    Attributes:
        id: Event ID
        subject: Event subject
        start: Start datetime
        end: End datetime
        location: Location
        attendees: List of attendee emails
        teams_link: Teams meeting link (if any)
        body: Event body/description
    """

    id: str
    subject: str
    start: datetime
    end: datetime
    location: Optional[str] = None
    attendees: Optional[list[str]] = None
    teams_link: Optional[str] = None
    body: Optional[str] = None


class OutlookClient(IntegrationBase):
    """Microsoft Graph API client for Outlook.

    Handles:
        - OAuth2 authentication with MSAL
        - Token caching and refresh
        - Email send/receive
        - Calendar operations
    """

    def __init__(self) -> None:
        """Initialize Outlook client."""
        self._config = get_config()
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self._msal_app: Optional[msal.ConfidentialClientApplication] = None

    @property
    def _user_email(self) -> str:
        """Get the configured user email for Graph API calls."""
        if not self._config.outlook_user_email:
            raise OutlookError("OUTLOOK_USER_EMAIL not configured")
        return self._config.outlook_user_email

    @property
    def _token_cache_path(self) -> Path:
        """Path to MSAL token cache file."""
        return self._config.db_path.parent / "outlook_token_cache.json"

    def health_check(self) -> bool:
        """Check if Outlook API is reachable.

        Attempts to read the user's profile via Graph API.

        Returns:
            True if API is reachable and authenticated
        """
        if not self.is_configured():
            return False

        try:
            self._ensure_authenticated()
            response = self._graph_request("GET", f"/users/{self._user_email}")
            return response.status_code == 200
        except (OutlookError, requests.RequestException):
            return False

    def is_configured(self) -> bool:
        """Check if Outlook credentials are configured."""
        return all(
            [
                self._config.outlook_client_id,
                self._config.outlook_client_secret,
                self._config.outlook_tenant_id,
                self._config.outlook_user_email,
            ]
        )

    def authenticate(self) -> bool:
        """Authenticate with Microsoft Graph.

        Uses OAuth2 client credentials flow via MSAL.
        Tokens are cached to disk and refreshed automatically.

        Returns:
            True if authentication successful

        Raises:
            OutlookError: If authentication fails
        """
        if not self.is_configured():
            raise OutlookError("Outlook credentials not configured")

        try:
            app = self._get_msal_app()
            result = app.acquire_token_for_client(scopes=GRAPH_SCOPES)

            if "access_token" in result:
                self._access_token = result["access_token"]
                expires_in = result.get("expires_in", 3600)
                self._token_expiry = datetime.now(timezone.utc) + timedelta(
                    seconds=expires_in
                )
                self._save_token_cache()
                logger.info(
                    "Outlook authentication successful",
                    extra={"context": {"user": self._user_email}},
                )
                return True
            else:
                error = result.get("error_description", result.get("error", "Unknown"))
                raise OutlookError(f"Authentication failed: {error}")

        except OutlookError:
            raise
        except Exception as e:
            raise OutlookError(f"Authentication error: {e}") from e

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html: bool = False,
        cc: Optional[list[str]] = None,
        bcc: Optional[list[str]] = None,
    ) -> str:
        """Send an email via Graph API.

        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body
            html: True if body is HTML
            cc: CC recipients
            bcc: BCC recipients

        Returns:
            Message ID (empty string for dry_run)

        Raises:
            OutlookError: If send fails
        """
        if self._config.dry_run:
            logger.info(
                f"DRY RUN: Would send email to {to}: {subject}",
                extra={"context": {"to": to, "subject": subject}},
            )
            return ""

        self._ensure_authenticated()

        message_payload: dict[str, Any] = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML" if html else "Text",
                    "content": body,
                },
                "toRecipients": [
                    {"emailAddress": {"address": to}},
                ],
            },
            "saveToSentItems": True,
        }

        if cc:
            message_payload["message"]["ccRecipients"] = [
                {"emailAddress": {"address": addr}} for addr in cc
            ]

        if bcc:
            message_payload["message"]["bccRecipients"] = [
                {"emailAddress": {"address": addr}} for addr in bcc
            ]

        try:
            response = self.with_retry(
                lambda: self._graph_request(
                    "POST",
                    f"/users/{self._user_email}/sendMail",
                    json_data=message_payload,
                ),
                max_retries=2,
                exceptions=(requests.RequestException, OutlookError),
            )

            if response.status_code == 202:
                logger.info(
                    f"Email sent to {to}",
                    extra={"context": {"to": to, "subject": subject}},
                )
                return f"sent-{datetime.now(timezone.utc).isoformat()}"
            else:
                raise OutlookError(
                    f"Send failed ({response.status_code}): {response.text}"
                )

        except OutlookError:
            raise
        except Exception as e:
            raise OutlookError(f"Failed to send email: {e}") from e

    def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
        html: bool = False,
    ) -> str:
        """Create a draft email in the user's mailbox.

        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body
            html: True if body is HTML

        Returns:
            Draft message ID

        Raises:
            OutlookError: If draft creation fails
        """
        self._ensure_authenticated()

        draft_payload: dict[str, Any] = {
            "subject": subject,
            "body": {
                "contentType": "HTML" if html else "Text",
                "content": body,
            },
            "toRecipients": [
                {"emailAddress": {"address": to}},
            ],
        }

        try:
            response = self._graph_request(
                "POST",
                f"/users/{self._user_email}/messages",
                json_data=draft_payload,
            )

            if response.status_code == 201:
                data = response.json()
                draft_id = data.get("id", "")
                logger.info(
                    f"Draft created for {to}",
                    extra={"context": {"to": to, "subject": subject}},
                )
                return draft_id
            else:
                raise OutlookError(
                    f"Draft creation failed ({response.status_code}): {response.text}"
                )

        except OutlookError:
            raise
        except Exception as e:
            raise OutlookError(f"Failed to create draft: {e}") from e

    def get_inbox(
        self,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> list[EmailMessage]:
        """Get inbox messages.

        Args:
            since: Only messages received after this time
            limit: Maximum messages to return

        Returns:
            List of email messages
        """
        raise NotImplementedError("Phase 3, Step 3.2")

    def classify_reply(self, message: EmailMessage) -> ReplyClassification:
        """Classify an email reply.

        Uses simple heuristics to classify:
            - Keywords for interest
            - OOO auto-reply patterns
            - Referral patterns

        Returns:
            Reply classification
        """
        raise NotImplementedError("Phase 3, Step 3.2")

    def create_event(
        self,
        subject: str,
        start: datetime,
        duration_minutes: int = 30,
        attendees: Optional[list[str]] = None,
        teams_meeting: bool = False,
        body: Optional[str] = None,
    ) -> str:
        """Create a calendar event.

        Args:
            subject: Event subject
            start: Start datetime
            duration_minutes: Duration in minutes
            attendees: Attendee email addresses
            teams_meeting: Generate Teams meeting link
            body: Event description

        Returns:
            Event ID
        """
        raise NotImplementedError("Phase 3, Step 3.2")

    def get_events(
        self,
        start: datetime,
        end: datetime,
    ) -> list[CalendarEvent]:
        """Get calendar events in date range."""
        raise NotImplementedError("Phase 3, Step 3.2")

    def update_event(self, event_id: str, **kwargs: Any) -> bool:
        """Update an event."""
        raise NotImplementedError("Phase 3, Step 3.2")

    def delete_event(self, event_id: str) -> bool:
        """Delete an event."""
        raise NotImplementedError("Phase 3, Step 3.2")

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _get_msal_app(self) -> msal.ConfidentialClientApplication:
        """Get or create the MSAL application instance."""
        if self._msal_app is None:
            cache = msal.SerializableTokenCache()
            if self._token_cache_path.exists():
                cache.deserialize(self._token_cache_path.read_text())

            self._msal_app = msal.ConfidentialClientApplication(
                client_id=self._config.outlook_client_id,
                client_credential=self._config.outlook_client_secret,
                authority=(
                    f"https://login.microsoftonline.com/"
                    f"{self._config.outlook_tenant_id}"
                ),
                token_cache=cache,
            )
        return self._msal_app

    def _save_token_cache(self) -> None:
        """Persist MSAL token cache to disk."""
        app = self._get_msal_app()
        if app.token_cache.has_state_changed:
            try:
                self._token_cache_path.parent.mkdir(parents=True, exist_ok=True)
                self._token_cache_path.write_text(app.token_cache.serialize())
            except OSError as e:
                logger.warning(f"Failed to save token cache: {e}")

    def _ensure_authenticated(self) -> None:
        """Ensure we have a valid access token, refreshing if needed.

        Raises:
            OutlookError: If authentication fails
        """
        now = datetime.now(timezone.utc)

        if self._access_token and self._token_expiry:
            if now < self._token_expiry - timedelta(minutes=5):
                return

        self.authenticate()

    def _graph_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, str]] = None,
    ) -> requests.Response:
        """Make an authenticated request to Microsoft Graph API.

        Args:
            method: HTTP method (GET, POST, PATCH, DELETE)
            endpoint: API endpoint (e.g., /users/{id}/sendMail)
            json_data: JSON request body
            params: Query parameters

        Returns:
            Response object

        Raises:
            OutlookError: If not authenticated
        """
        if not self._access_token:
            raise OutlookError("Not authenticated — call authenticate() first")

        url = f"{GRAPH_BASE_URL}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=json_data,
            params=params,
            timeout=30,
        )

        # Handle 401 — token may have expired, re-auth and retry once
        if response.status_code == 401:
            logger.warning("Token expired, re-authenticating")
            self._access_token = None
            self._token_expiry = None
            self.authenticate()
            headers["Authorization"] = f"Bearer {self._access_token}"
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=json_data,
                params=params,
                timeout=30,
            )

        return response
