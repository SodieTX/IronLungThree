"""Microsoft Outlook integration via Graph API.

Provides:
    - OAuth2 authentication with token refresh
    - Send email (plain text and HTML)
    - Create drafts
    - Read inbox (polling)
    - Reply classification
    - Calendar operations with Teams meeting links

Usage:
    from src.integrations.outlook import OutlookClient

    client = OutlookClient()
    if client.is_configured():
        client.send_email(to="test@example.com", subject="Hello", body="...")
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum

from src.integrations.base import IntegrationBase
from src.core.config import get_config
from src.core.logging import get_logger

logger = get_logger(__name__)


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

    def __init__(self):
        """Initialize Outlook client."""
        self._config = get_config()
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

    def health_check(self) -> bool:
        """Check if Outlook API is reachable."""
        raise NotImplementedError("Phase 3, Step 3.1")

    def is_configured(self) -> bool:
        """Check if Outlook credentials are configured."""
        return all(
            [
                self._config.outlook_client_id,
                self._config.outlook_client_secret,
                self._config.outlook_tenant_id,
            ]
        )

    def authenticate(self) -> bool:
        """Authenticate with Microsoft Graph.

        Uses OAuth2 with client credentials flow.

        Returns:
            True if authentication successful
        """
        raise NotImplementedError("Phase 3, Step 3.1")

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html: bool = False,
        cc: Optional[list[str]] = None,
        bcc: Optional[list[str]] = None,
    ) -> str:
        """Send an email.

        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body
            html: True if body is HTML
            cc: CC recipients
            bcc: BCC recipients

        Returns:
            Message ID
        """
        raise NotImplementedError("Phase 3, Step 3.1")

    def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
        html: bool = False,
    ) -> str:
        """Create a draft email.

        Returns:
            Draft ID
        """
        raise NotImplementedError("Phase 3, Step 3.1")

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

    def update_event(self, event_id: str, **kwargs) -> bool:
        """Update an event."""
        raise NotImplementedError("Phase 3, Step 3.2")

    def delete_event(self, event_id: str) -> bool:
        """Delete an event."""
        raise NotImplementedError("Phase 3, Step 3.2")
