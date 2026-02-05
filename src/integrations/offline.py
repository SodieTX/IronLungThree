"""Offline simulation clients for credential-gated services.

When real API credentials aren't available, these clients stand in so
the full application workflow can run without crashing. Every method
logs what it *would* do and returns plausible fake data.

This lets us:
    - Build and test the full GUI flow without Outlook credentials
    - Run email generation pipelines without a Claude API key
    - Exercise the nightly cycle without ActiveCampaign access
    - Catch integration bugs early, before credentials are added

Usage:
    from src.integrations.offline import OfflineOutlookClient, OfflineEmailGenerator

    # Use these when ServiceRegistry says the real service isn't available
    if not registry.is_available("outlook"):
        outlook = OfflineOutlookClient()
    else:
        outlook = OutlookClient()
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from src.core.logging import get_logger

logger = get_logger(__name__)

# Prefix for all simulated IDs so they're obviously fake
_SIM_PREFIX = "sim"


class OfflineOutlookClient:
    """Simulated Outlook client for offline development.

    Every method logs the action and returns plausible fake data.
    No network calls are made. No credentials are needed.
    """

    def __init__(self) -> None:
        self._send_count = 0
        self._draft_count = 0
        self._event_count = 0
        logger.info("OfflineOutlookClient initialized (no real emails will be sent)")

    def health_check(self) -> bool:
        return False  # We're offline

    def is_configured(self) -> bool:
        return False  # No real credentials

    def authenticate(self) -> bool:
        logger.info("OFFLINE: Skipping Outlook authentication")
        return True

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html: bool = False,
        cc: Optional[list[str]] = None,
        bcc: Optional[list[str]] = None,
    ) -> str:
        """Simulate sending an email."""
        self._send_count += 1
        msg_id = f"{_SIM_PREFIX}-sent-{self._send_count}"
        logger.info(
            f"OFFLINE: Would send email to {to}: {subject}",
            extra={
                "context": {
                    "to": to,
                    "subject": subject,
                    "sim_id": msg_id,
                    "offline": True,
                }
            },
        )
        return msg_id

    def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
        html: bool = False,
    ) -> str:
        """Simulate creating a draft."""
        self._draft_count += 1
        draft_id = f"{_SIM_PREFIX}-draft-{self._draft_count}"
        logger.info(
            f"OFFLINE: Would create draft for {to}: {subject}",
            extra={
                "context": {
                    "to": to,
                    "subject": subject,
                    "sim_id": draft_id,
                    "offline": True,
                }
            },
        )
        return draft_id

    def get_inbox(
        self,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> list:
        """Simulate inbox read - returns empty list."""
        logger.info(
            "OFFLINE: Would read inbox (returning empty)",
            extra={"context": {"since": str(since), "offline": True}},
        )
        return []

    def classify_reply(self, message: Any) -> str:
        """Simulate reply classification."""
        return "unknown"

    def create_event(
        self,
        subject: str,
        start: datetime,
        duration_minutes: int = 30,
        attendees: Optional[list[str]] = None,
        teams_meeting: bool = False,
        body: Optional[str] = None,
    ) -> str:
        """Simulate calendar event creation."""
        self._event_count += 1
        event_id = f"{_SIM_PREFIX}-event-{self._event_count}"
        logger.info(
            f"OFFLINE: Would create event: {subject}",
            extra={
                "context": {
                    "subject": subject,
                    "start": str(start),
                    "sim_id": event_id,
                    "offline": True,
                }
            },
        )
        return event_id

    def get_events(
        self,
        start: datetime,
        end: datetime,
    ) -> list:
        """Simulate calendar read - returns empty list."""
        logger.info(
            "OFFLINE: Would read calendar (returning empty)",
            extra={"context": {"offline": True}},
        )
        return []

    def update_event(self, event_id: str, **kwargs: Any) -> bool:
        logger.info(f"OFFLINE: Would update event {event_id}")
        return True

    def delete_event(self, event_id: str) -> bool:
        logger.info(f"OFFLINE: Would delete event {event_id}")
        return True


@dataclass
class SimulatedEmail:
    """Simulated AI-generated email for offline mode."""

    subject: str
    body: str
    body_html: Optional[str] = None
    tokens_used: int = 0


class OfflineEmailGenerator:
    """Simulated Claude email generator for offline development.

    Returns template-based placeholder emails so the full
    email workflow can be tested without an API key.
    """

    def __init__(self, style_examples: Optional[list[str]] = None) -> None:
        self._gen_count = 0
        logger.info("OfflineEmailGenerator initialized (no real AI calls will be made)")

    def is_available(self) -> bool:
        return False  # No real API key

    def generate_email(
        self,
        prospect: Any,
        company: Any,
        instruction: str,
        context: Optional[str] = None,
    ) -> SimulatedEmail:
        """Generate a placeholder email."""
        self._gen_count += 1

        first = getattr(prospect, "first_name", "Prospect")
        last = getattr(prospect, "last_name", "")
        co_name = getattr(company, "name", "Company")

        subject = f"[SIMULATED] Re: {instruction[:50]}"
        body = (
            f"Hi {first},\n\n"
            f"[This is a simulated email generated in offline mode.]\n"
            f"[Instruction: {instruction}]\n"
            f"[Prospect: {first} {last} at {co_name}]\n\n"
            f"When CLAUDE_API_KEY is configured, this will be a real "
            f"AI-generated email matching your writing style.\n\n"
            f"Best regards"
        )

        logger.info(
            f"OFFLINE: Generated simulated email #{self._gen_count}",
            extra={
                "context": {
                    "instruction": instruction[:80],
                    "prospect": f"{first} {last}",
                    "offline": True,
                }
            },
        )

        return SimulatedEmail(
            subject=subject,
            body=body,
            tokens_used=0,
        )

    def refine_email(
        self,
        draft: str,
        feedback: str,
    ) -> SimulatedEmail:
        """Simulate email refinement."""
        self._gen_count += 1
        logger.info(
            f"OFFLINE: Would refine email with feedback: {feedback[:80]}",
            extra={"context": {"offline": True}},
        )
        return SimulatedEmail(
            subject="[SIMULATED] Refined draft",
            body=f"{draft}\n\n[Simulated refinement based on: {feedback}]",
            tokens_used=0,
        )


def get_outlook_client():
    """Factory: return real OutlookClient if configured, else offline stub.

    Returns:
        OutlookClient or OfflineOutlookClient
    """
    from src.core.services import get_service_registry

    registry = get_service_registry()
    if registry.is_available("outlook"):
        from src.integrations.outlook import OutlookClient

        return OutlookClient()
    else:
        status = registry.check("outlook")
        logger.info(
            f"Using OfflineOutlookClient: {status.reason}",
            extra={"context": {"service": "outlook"}},
        )
        return OfflineOutlookClient()


def get_email_generator(style_examples: Optional[list[str]] = None):
    """Factory: return real EmailGenerator if configured, else offline stub.

    Args:
        style_examples: Style examples for real generator

    Returns:
        EmailGenerator or OfflineEmailGenerator
    """
    from src.core.services import get_service_registry

    registry = get_service_registry()
    if registry.is_available("claude"):
        from src.engine.email_gen import EmailGenerator

        return EmailGenerator(style_examples=style_examples)
    else:
        status = registry.check("claude")
        logger.info(
            f"Using OfflineEmailGenerator: {status.reason}",
            extra={"context": {"service": "claude"}},
        )
        return OfflineEmailGenerator(style_examples=style_examples)
