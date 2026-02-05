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

try:
    import msal
except ImportError:
    msal = None  # type: ignore[assignment]

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
        self._msal_app: Optional[object] = None

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
                self._token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
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
                raise OutlookError(f"Send failed ({response.status_code}): {response.text}")

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
        """Get inbox messages via Graph API polling.

        Args:
            since: Only messages received after this time
            limit: Maximum messages to return

        Returns:
            List of email messages, newest first

        Raises:
            OutlookError: If inbox read fails
        """
        self._ensure_authenticated()

        params: dict[str, str] = {
            "$top": str(limit),
            "$orderby": "receivedDateTime desc",
            "$select": ("id,from,toRecipients,subject,body,bodyPreview," "receivedDateTime,isRead"),
        }

        if since:
            iso_since = since.strftime("%Y-%m-%dT%H:%M:%SZ")
            params["$filter"] = f"receivedDateTime ge {iso_since}"

        try:
            response = self._graph_request(
                "GET",
                f"/users/{self._user_email}/mailFolders/inbox/messages",
                params=params,
            )

            if response.status_code != 200:
                raise OutlookError(f"Inbox read failed ({response.status_code}): {response.text}")

            data = response.json()
            messages: list[EmailMessage] = []

            for msg in data.get("value", []):
                received_at = None
                if msg.get("receivedDateTime"):
                    received_at = datetime.fromisoformat(
                        msg["receivedDateTime"].replace("Z", "+00:00")
                    )

                from_addr = ""
                if msg.get("from", {}).get("emailAddress"):
                    from_addr = msg["from"]["emailAddress"].get("address", "")

                to_addrs = [
                    r["emailAddress"]["address"]
                    for r in msg.get("toRecipients", [])
                    if r.get("emailAddress", {}).get("address")
                ]

                messages.append(
                    EmailMessage(
                        id=msg.get("id", ""),
                        from_address=from_addr,
                        to_addresses=to_addrs,
                        subject=msg.get("subject", ""),
                        body=msg.get("bodyPreview", ""),
                        body_html=msg.get("body", {}).get("content"),
                        received_at=received_at,
                        is_read=msg.get("isRead", False),
                    )
                )

            logger.info(
                f"Retrieved {len(messages)} inbox messages",
                extra={"context": {"count": len(messages), "since": str(since)}},
            )
            return messages

        except OutlookError:
            raise
        except Exception as e:
            raise OutlookError(f"Failed to read inbox: {e}") from e

    def classify_reply(self, message: EmailMessage) -> ReplyClassification:
        """Classify an email reply using keyword heuristics.

        Classification priority:
            1. OOO (out-of-office auto-replies)
            2. Not interested (explicit decline)
            3. Referral (redirecting to someone else)
            4. Interested (positive signal)
            5. Unknown (default)

        Args:
            message: Email message to classify

        Returns:
            Reply classification
        """
        text = f"{message.subject} {message.body}".lower()

        # OOO patterns (check first — auto-replies should not be misclassified)
        ooo_patterns = [
            "out of office",
            "out of the office",
            "automatic reply",
            "auto-reply",
            "autoreply",
            "i am currently out",
            "i'm currently out",
            "will be out of the office",
            "on vacation",
            "on leave",
            "limited access to email",
        ]
        if any(pattern in text for pattern in ooo_patterns):
            return ReplyClassification.OOO

        # Not interested patterns
        not_interested_patterns = [
            "not interested",
            "no thank you",
            "no thanks",
            "please remove",
            "remove me",
            "unsubscribe",
            "stop contacting",
            "don't contact",
            "do not contact",
            "not a good fit",
            "not looking",
            "we're all set",
            "we are all set",
            "pass on this",
            "no need",
        ]
        if any(pattern in text for pattern in not_interested_patterns):
            return ReplyClassification.NOT_INTERESTED

        # Referral patterns
        referral_patterns = [
            "reach out to",
            "contact instead",
            "talk to",
            "speak with",
            "the right person",
            "better person to talk to",
            "forward this to",
            "passing this along",
            "cc'ing",
            "ccing",
            "loop in",
            "adding",
        ]
        if any(pattern in text for pattern in referral_patterns):
            return ReplyClassification.REFERRAL

        # Interested patterns
        interested_patterns = [
            "interested",
            "sounds good",
            "sounds great",
            "let's chat",
            "let's talk",
            "let's connect",
            "set up a call",
            "set up a time",
            "schedule a",
            "love to learn more",
            "tell me more",
            "more information",
            "send me more",
            "when are you available",
            "what times work",
            "happy to chat",
            "i'd like to",
            "would love to",
            "that works",
            "yes",
            "sure",
            "absolutely",
        ]
        if any(pattern in text for pattern in interested_patterns):
            return ReplyClassification.INTERESTED

        return ReplyClassification.UNKNOWN

    def create_event(
        self,
        subject: str,
        start: datetime,
        duration_minutes: int = 30,
        attendees: Optional[list[str]] = None,
        teams_meeting: bool = False,
        body: Optional[str] = None,
    ) -> str:
        """Create a calendar event via Graph API.

        Args:
            subject: Event subject
            start: Start datetime
            duration_minutes: Duration in minutes
            attendees: Attendee email addresses
            teams_meeting: Generate Teams meeting link
            body: Event description

        Returns:
            Event ID

        Raises:
            OutlookError: If event creation fails
        """
        self._ensure_authenticated()

        end = start + timedelta(minutes=duration_minutes)
        event_payload: dict[str, Any] = {
            "subject": subject,
            "start": {
                "dateTime": start.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": end.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": "UTC",
            },
        }

        if body:
            event_payload["body"] = {
                "contentType": "HTML",
                "content": body,
            }

        if attendees:
            event_payload["attendees"] = [
                {
                    "emailAddress": {"address": addr},
                    "type": "required",
                }
                for addr in attendees
            ]

        if teams_meeting:
            event_payload["isOnlineMeeting"] = True
            event_payload["onlineMeetingProvider"] = "teamsForBusiness"

        try:
            response = self._graph_request(
                "POST",
                f"/users/{self._user_email}/events",
                json_data=event_payload,
            )

            if response.status_code == 201:
                data = response.json()
                event_id = data.get("id", "")
                logger.info(
                    f"Calendar event created: {subject}",
                    extra={
                        "context": {
                            "subject": subject,
                            "start": str(start),
                            "teams": teams_meeting,
                        }
                    },
                )
                return event_id
            else:
                raise OutlookError(
                    f"Event creation failed ({response.status_code}): {response.text}"
                )

        except OutlookError:
            raise
        except Exception as e:
            raise OutlookError(f"Failed to create event: {e}") from e

    def get_events(
        self,
        start: datetime,
        end: datetime,
    ) -> list[CalendarEvent]:
        """Get calendar events in date range.

        Args:
            start: Range start (inclusive)
            end: Range end (exclusive)

        Returns:
            List of calendar events

        Raises:
            OutlookError: If calendar read fails
        """
        self._ensure_authenticated()

        params: dict[str, str] = {
            "startDateTime": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endDateTime": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "$orderby": "start/dateTime",
            "$select": ("id,subject,start,end,location,attendees," "onlineMeeting,body"),
        }

        try:
            response = self._graph_request(
                "GET",
                f"/users/{self._user_email}/calendarView",
                params=params,
            )

            if response.status_code != 200:
                raise OutlookError(
                    f"Calendar read failed ({response.status_code}): {response.text}"
                )

            data = response.json()
            events: list[CalendarEvent] = []

            for evt in data.get("value", []):
                evt_start = datetime.fromisoformat(evt["start"]["dateTime"].replace("Z", "+00:00"))
                evt_end = datetime.fromisoformat(evt["end"]["dateTime"].replace("Z", "+00:00"))

                attendee_emails = [
                    a["emailAddress"]["address"]
                    for a in evt.get("attendees", [])
                    if a.get("emailAddress", {}).get("address")
                ]

                teams_link = None
                online = evt.get("onlineMeeting")
                if online and isinstance(online, dict):
                    teams_link = online.get("joinUrl")

                events.append(
                    CalendarEvent(
                        id=evt.get("id", ""),
                        subject=evt.get("subject", ""),
                        start=evt_start,
                        end=evt_end,
                        location=evt.get("location", {}).get("displayName"),
                        attendees=attendee_emails or None,
                        teams_link=teams_link,
                        body=evt.get("body", {}).get("content"),
                    )
                )

            logger.info(
                f"Retrieved {len(events)} calendar events",
                extra={"context": {"count": len(events)}},
            )
            return events

        except OutlookError:
            raise
        except Exception as e:
            raise OutlookError(f"Failed to read calendar: {e}") from e

    def update_event(self, event_id: str, **kwargs: Any) -> bool:
        """Update a calendar event.

        Args:
            event_id: Event ID to update
            **kwargs: Fields to update (subject, start, end, body, attendees)

        Returns:
            True if update successful

        Raises:
            OutlookError: If update fails
        """
        self._ensure_authenticated()

        patch_payload: dict[str, Any] = {}
        if "subject" in kwargs:
            patch_payload["subject"] = kwargs["subject"]
        if "body" in kwargs:
            patch_payload["body"] = {
                "contentType": "HTML",
                "content": kwargs["body"],
            }
        if "start" in kwargs:
            patch_payload["start"] = {
                "dateTime": kwargs["start"].strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": "UTC",
            }
        if "end" in kwargs:
            patch_payload["end"] = {
                "dateTime": kwargs["end"].strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": "UTC",
            }

        try:
            response = self._graph_request(
                "PATCH",
                f"/users/{self._user_email}/events/{event_id}",
                json_data=patch_payload,
            )
            if response.status_code == 200:
                logger.info(f"Event updated: {event_id}")
                return True
            else:
                raise OutlookError(f"Event update failed ({response.status_code}): {response.text}")
        except OutlookError:
            raise
        except Exception as e:
            raise OutlookError(f"Failed to update event: {e}") from e

    def delete_event(self, event_id: str) -> bool:
        """Delete a calendar event.

        Args:
            event_id: Event ID to delete

        Returns:
            True if deletion successful

        Raises:
            OutlookError: If deletion fails
        """
        self._ensure_authenticated()

        try:
            response = self._graph_request(
                "DELETE",
                f"/users/{self._user_email}/events/{event_id}",
            )
            if response.status_code == 204:
                logger.info(f"Event deleted: {event_id}")
                return True
            else:
                raise OutlookError(
                    f"Event deletion failed ({response.status_code}): {response.text}"
                )
        except OutlookError:
            raise
        except Exception as e:
            raise OutlookError(f"Failed to delete event: {e}") from e

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _get_msal_app(self):
        """Get or create the MSAL application instance."""
        if msal is None:
            raise OutlookError("msal package not installed. " "Install with: pip install msal")
        if self._msal_app is None:
            cache = msal.SerializableTokenCache()
            if self._token_cache_path.exists():
                cache.deserialize(self._token_cache_path.read_text())

            self._msal_app = msal.ConfidentialClientApplication(
                client_id=self._config.outlook_client_id,
                client_credential=self._config.outlook_client_secret,
                authority=(
                    f"https://login.microsoftonline.com/" f"{self._config.outlook_tenant_id}"
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
