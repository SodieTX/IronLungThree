"""One-off email service for sending emails from prospect cards.

Coordinates:
    - Email generation (template or AI)
    - Sending via Outlook
    - Activity logging to database
    - Inline email history retrieval

Usage:
    from src.engine.email_service import EmailService

    service = EmailService(db, outlook_client)
    result = service.send_from_template(
        prospect_id=1, template_name="follow_up", sender=sender_info
    )
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import Activity, ActivityType, Company, Prospect

logger = get_logger(__name__)


@dataclass
class EmailResult:
    """Result of sending an email.

    Attributes:
        success: Whether the email was sent (or drafted)
        message_id: Outlook message ID (empty for dry_run or offline)
        subject: Email subject
        recipient: Recipient email address
        activity_id: Activity record ID in database
        draft_mode: True if email was saved as draft, not sent
    """

    success: bool
    message_id: str = ""
    subject: str = ""
    recipient: str = ""
    activity_id: Optional[int] = None
    draft_mode: bool = False


@dataclass
class EmailHistoryEntry:
    """A single email from the prospect's history.

    Attributes:
        direction: "sent" or "received"
        subject: Email subject
        preview: First ~100 chars of body
        timestamp: When the email was sent/received
        activity_id: Database activity ID
    """

    direction: str
    subject: str
    preview: str
    timestamp: Optional[datetime] = None
    activity_id: Optional[int] = None


class EmailService:
    """Orchestrates email operations for prospect cards.

    Provides a clean interface for:
        - Sending template-based emails
        - Sending AI-generated emails
        - Retrieving email history for a prospect
        - Creating drafts instead of sending
    """

    def __init__(
        self,
        db: Database,
        outlook: Optional[Any] = None,
    ) -> None:
        """Initialize email service.

        Args:
            db: Database instance
            outlook: OutlookClient instance (None for offline mode)
        """
        self._db = db
        self._outlook = outlook

    def send_from_template(
        self,
        prospect_id: int,
        template_name: str,
        sender: dict[str, str],
        draft_only: bool = False,
        **template_vars: Any,
    ) -> EmailResult:
        """Send an email using a Jinja2 template.

        Args:
            prospect_id: Target prospect ID
            template_name: Template name (e.g., "intro", "follow_up")
            sender: Sender info dict with name, title, company, phone
            draft_only: If True, create draft instead of sending
            **template_vars: Additional template variables

        Returns:
            EmailResult with send outcome
        """
        from src.engine.templates import get_template_subject, render_template

        prospect = self._db.get_prospect(prospect_id)
        if not prospect:
            logger.error(f"Prospect {prospect_id} not found")
            return EmailResult(success=False)

        company = self._db.get_company(prospect.company_id) if prospect.company_id else None
        if not company:
            company = Company(id=0, name="Unknown", name_normalized="unknown")

        recipient = self._get_prospect_email(prospect_id)
        if not recipient and self._outlook:
            logger.warning(f"No email address for prospect {prospect_id}")
            return EmailResult(success=False)

        body_html = render_template(
            template_name, prospect, company,
            sender=sender, **template_vars,
        )
        subject = get_template_subject(
            template_name, prospect, company,
            sender=sender, **template_vars,
        )

        return self._send_or_draft(
            prospect=prospect,
            recipient=recipient or "",
            subject=subject,
            body_html=body_html,
            draft_only=draft_only,
            template_name=template_name,
        )

    def send_custom(
        self,
        prospect_id: int,
        subject: str,
        body: str,
        html: bool = False,
        draft_only: bool = False,
    ) -> EmailResult:
        """Send a custom (non-template) email.

        Args:
            prospect_id: Target prospect ID
            subject: Email subject
            body: Email body
            html: Whether body is HTML
            draft_only: If True, create draft instead of sending

        Returns:
            EmailResult with send outcome
        """
        prospect = self._db.get_prospect(prospect_id)
        if not prospect:
            logger.error(f"Prospect {prospect_id} not found")
            return EmailResult(success=False)

        recipient = self._get_prospect_email(prospect_id)
        if not recipient and self._outlook:
            logger.warning(f"No email address for prospect {prospect_id}")
            return EmailResult(success=False)

        body_html = body if html else None

        return self._send_or_draft(
            prospect=prospect,
            recipient=recipient or "",
            subject=subject,
            body_html=body_html,
            body_text=body if not html else None,
            draft_only=draft_only,
        )

    def get_email_history(
        self,
        prospect_id: int,
        limit: int = 10,
    ) -> list[EmailHistoryEntry]:
        """Get email history for a prospect from activity log.

        Args:
            prospect_id: Prospect ID
            limit: Maximum entries to return

        Returns:
            List of email history entries, newest first
        """
        activities = self._db.get_activities(prospect_id)

        email_activities = [
            a for a in activities
            if a.activity_type in (ActivityType.EMAIL_SENT, ActivityType.EMAIL_RECEIVED)
        ]

        # Sort newest first
        email_activities.sort(
            key=lambda a: a.created_at or datetime.min,
            reverse=True,
        )

        entries: list[EmailHistoryEntry] = []
        for activity in email_activities[:limit]:
            direction = (
                "sent" if activity.activity_type == ActivityType.EMAIL_SENT
                else "received"
            )

            # Parse subject from notes (format: "Subject: ... | Body preview...")
            subject = ""
            preview = activity.notes or ""
            if preview.startswith("Subject:"):
                parts = preview.split("|", 1)
                subject = parts[0].replace("Subject:", "").strip()
                preview = parts[1].strip() if len(parts) > 1 else ""

            entries.append(
                EmailHistoryEntry(
                    direction=direction,
                    subject=subject,
                    preview=preview[:100],
                    timestamp=activity.created_at,
                    activity_id=activity.id,
                )
            )

        return entries

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _get_prospect_email(self, prospect_id: int) -> Optional[str]:
        """Get the primary email address for a prospect."""
        methods = self._db.get_contact_methods(prospect_id)
        from src.db.models import ContactMethodType

        for method in methods:
            if method.type == ContactMethodType.EMAIL:
                return method.value
        return None

    def _send_or_draft(
        self,
        prospect: Prospect,
        recipient: str,
        subject: str,
        body_html: Optional[str] = None,
        body_text: Optional[str] = None,
        draft_only: bool = False,
        template_name: Optional[str] = None,
    ) -> EmailResult:
        """Send or draft an email and log the activity.

        Args:
            prospect: Target prospect
            recipient: Recipient email
            subject: Email subject
            body_html: HTML body (preferred)
            body_text: Plain text body (fallback)
            draft_only: Create draft instead of sending
            template_name: Template used (for activity notes)

        Returns:
            EmailResult
        """
        message_id = ""
        body = body_html or body_text or ""
        is_html = body_html is not None

        # Send via Outlook if available
        if self._outlook and recipient:
            try:
                if draft_only:
                    message_id = self._outlook.create_draft(
                        to=recipient,
                        subject=subject,
                        body=body,
                        html=is_html,
                    )
                else:
                    message_id = self._outlook.send_email(
                        to=recipient,
                        subject=subject,
                        body=body,
                        html=is_html,
                    )
            except Exception as e:
                logger.error(f"Email send/draft failed: {e}")
                return EmailResult(
                    success=False,
                    subject=subject,
                    recipient=recipient,
                )

        # Log activity
        notes = f"Subject: {subject}"
        if template_name:
            notes += f" | Template: {template_name}"
        if draft_only:
            notes += " | Saved as draft"

        activity = Activity(
            prospect_id=prospect.id or 0,
            activity_type=ActivityType.EMAIL_SENT,
            notes=notes,
        )
        activity_id = self._db.create_activity(activity)

        logger.info(
            f"Email {'drafted' if draft_only else 'sent'}: {subject} -> {recipient}",
            extra={"context": {
                "prospect_id": prospect.id,
                "subject": subject,
                "draft": draft_only,
            }},
        )

        return EmailResult(
            success=True,
            message_id=message_id,
            subject=subject,
            recipient=recipient,
            activity_id=activity_id,
            draft_mode=draft_only,
        )
