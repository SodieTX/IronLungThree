"""Nurture email sequences for unengaged prospects.

Draft-and-queue model: emails are generated and queued for Jeff's
batch approval, NOT auto-sent.

Sequences:
    - Warm Touch: 3 emails, 7 days apart
    - Re-engagement: 2 emails, 14 days apart
    - Breakup: 1 final email

Usage:
    from src.engine.nurture import NurtureEngine

    engine = NurtureEngine(db)
    batch = engine.generate_nurture_batch(limit=30)
    # Jeff reviews and approves...
    sent = engine.send_approved_emails()
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import ActivityType, AttemptType, Prospect

logger = get_logger(__name__)


class NurtureSequence(str, Enum):
    """Type of nurture sequence."""

    WARM_TOUCH = "warm_touch"
    RE_ENGAGEMENT = "re_engagement"
    BREAKUP = "breakup"


@dataclass
class NurtureEmail:
    """A queued nurture email.

    Attributes:
        id: Queue ID
        prospect_id: Target prospect
        prospect_name: Prospect name
        company_name: Company name
        sequence: Sequence type
        sequence_step: Step in sequence (1, 2, 3)
        subject: Email subject
        body: Email body
        to_address: Recipient email
        status: pending, approved, sent, rejected
        queued_at: When queued
        approved_at: When approved
        sent_at: When sent
    """

    id: Optional[int] = None
    prospect_id: int = 0
    prospect_name: str = ""
    company_name: str = ""
    sequence: NurtureSequence = NurtureSequence.WARM_TOUCH
    sequence_step: int = 1
    subject: str = ""
    body: str = ""
    to_address: str = ""
    status: str = "pending"
    queued_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None


class NurtureEngine:
    """Nurture email generation and sending.

    Draft-and-queue model for compliance and quality control.
    """

    # Sequence configuration: (max_steps, days_between)
    SEQUENCE_CONFIG = {
        NurtureSequence.WARM_TOUCH: {"max_steps": 3, "days_between": 7},
        NurtureSequence.RE_ENGAGEMENT: {"max_steps": 2, "days_between": 14},
        NurtureSequence.BREAKUP: {"max_steps": 1, "days_between": 0},
    }

    # Simple email templates keyed by (sequence, step)
    TEMPLATES = {
        (NurtureSequence.WARM_TOUCH, 1): {
            "subject": "Quick question about {company_name}",
            "body": (
                "Hi {first_name},\n\n"
                "I work with companies like {company_name} to streamline their "
                "lending operations. I'd love to learn more about how things are "
                "going on your end.\n\n"
                "Do you have 15 minutes this week for a quick call?\n\n"
                "Best,\nJeff"
            ),
        },
        (NurtureSequence.WARM_TOUCH, 2): {
            "subject": "Following up - {company_name}",
            "body": (
                "Hi {first_name},\n\n"
                "I wanted to follow up on my previous note. I've been helping "
                "similar companies in {state} improve their loan processing "
                "workflows, and I think there could be a fit.\n\n"
                "Would it make sense to connect briefly?\n\n"
                "Best,\nJeff"
            ),
        },
        (NurtureSequence.WARM_TOUCH, 3): {
            "subject": "One more thought for {company_name}",
            "body": (
                "Hi {first_name},\n\n"
                "I know you're busy, so I'll keep this short. I've helped companies "
                "like yours save significant time on their lending operations.\n\n"
                "If the timing isn't right, no worries at all - just let me know "
                "and I'll check back another time.\n\n"
                "Best,\nJeff"
            ),
        },
        (NurtureSequence.RE_ENGAGEMENT, 1): {
            "subject": "Checking in - {first_name}",
            "body": (
                "Hi {first_name},\n\n"
                "It's been a while since we last connected. I wanted to check in "
                "and see how things are going at {company_name}.\n\n"
                "Has anything changed on your end that might make it worth "
                "revisiting a conversation?\n\n"
                "Best,\nJeff"
            ),
        },
        (NurtureSequence.RE_ENGAGEMENT, 2): {
            "subject": "Still thinking of {company_name}",
            "body": (
                "Hi {first_name},\n\n"
                "Just a final follow-up. I've been keeping {company_name} in mind "
                "and would love to reconnect when the timing is right.\n\n"
                "Feel free to reach out anytime. I'm here when you're ready.\n\n"
                "Best,\nJeff"
            ),
        },
        (NurtureSequence.BREAKUP, 1): {
            "subject": "Closing the loop - {first_name}",
            "body": (
                "Hi {first_name},\n\n"
                "I've reached out a few times and haven't been able to connect, "
                "so I don't want to keep filling your inbox.\n\n"
                "If things change down the road and you'd like to explore how we "
                "can help {company_name}, my door is always open.\n\n"
                "Wishing you all the best,\nJeff"
            ),
        },
    }

    # Minimum days since last automated email before sending another
    NURTURE_COOLDOWN_DAYS = 7

    def __init__(self, db: Database, daily_send_cap: int = 50, outlook=None):
        """Initialize nurture engine.

        Args:
            db: Database instance
            daily_send_cap: Maximum emails to send per day
            outlook: Optional Outlook client for actual sending.
                     If None, emails are marked sent without delivery (testing).
        """
        self.db = db
        self.daily_send_cap = daily_send_cap
        self.outlook = outlook
        self._ensure_nurture_table()

    def _ensure_nurture_table(self) -> None:
        """Create the nurture_queue table if it doesn't exist."""
        self.db.executescript_sql("""
            CREATE TABLE IF NOT EXISTS nurture_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prospect_id INTEGER NOT NULL,
                prospect_name TEXT,
                company_name TEXT,
                sequence TEXT NOT NULL,
                sequence_step INTEGER NOT NULL DEFAULT 1,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                to_address TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                queued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                approved_at TIMESTAMP,
                sent_at TIMESTAMP,
                rejected_reason TEXT,
                FOREIGN KEY (prospect_id) REFERENCES prospects(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_nurture_prospect
                ON nurture_queue(prospect_id);
            CREATE INDEX IF NOT EXISTS idx_nurture_status
                ON nurture_queue(status);
            """)

    def generate_nurture_batch(self, limit: int = 30) -> list[NurtureEmail]:
        """Generate nurture emails for batch approval.

        Identifies prospects due for nurture and generates emails.
        Does NOT send - queues for approval.

        Args:
            limit: Maximum emails to generate

        Returns:
            List of generated NurtureEmail objects
        """
        prospects = self._get_prospects_for_nurture(limit)
        generated: list[NurtureEmail] = []

        for prospect in prospects:
            try:
                sequence, step = self._determine_sequence(prospect)
                email = self._generate_email(prospect, sequence, step)

                # Insert into nurture_queue
                cursor = self.db.execute_sql(
                    """INSERT INTO nurture_queue
                       (prospect_id, prospect_name, company_name, sequence,
                        sequence_step, subject, body, to_address, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
                    (
                        email.prospect_id,
                        email.prospect_name,
                        email.company_name,
                        email.sequence.value,
                        email.sequence_step,
                        email.subject,
                        email.body,
                        email.to_address,
                    ),
                )
                email.id = cursor.lastrowid
                email.queued_at = datetime.now()
                generated.append(email)

                logger.info(
                    "Nurture email queued",
                    extra={
                        "context": {
                            "prospect_id": prospect.id,
                            "sequence": sequence.value,
                            "step": step,
                        }
                    },
                )
            except Exception as exc:
                logger.warning(
                    "Failed to generate nurture email",
                    extra={
                        "context": {
                            "prospect_id": prospect.id,
                            "error": str(exc),
                        }
                    },
                )
                continue

        logger.info(
            "Nurture batch generated",
            extra={"context": {"count": len(generated)}},
        )
        return generated

    def get_pending_approval(self) -> list[NurtureEmail]:
        """Get emails pending Jeff's approval.

        Returns:
            Emails awaiting approval
        """
        rows = self.db.fetchall_sql("""SELECT * FROM nurture_queue
               WHERE status = 'pending'
               ORDER BY queued_at ASC""")
        return [self._row_to_nurture_email(row) for row in rows]

    def approve_email(self, email_id: int) -> bool:
        """Approve an email for sending.

        Args:
            email_id: Queue ID

        Returns:
            True if approved
        """
        now = datetime.now().isoformat()
        cursor = self.db.execute_sql(
            """UPDATE nurture_queue
               SET status = 'approved', approved_at = ?
               WHERE id = ? AND status = 'pending'""",
            (now, email_id),
        )
        if cursor.rowcount > 0:
            logger.info(
                "Nurture email approved",
                extra={"context": {"email_id": email_id}},
            )
            return True
        return False

    def reject_email(self, email_id: int, reason: Optional[str] = None) -> bool:
        """Reject an email (won't be sent).

        Args:
            email_id: Queue ID
            reason: Why rejected

        Returns:
            True if rejected
        """
        cursor = self.db.execute_sql(
            """UPDATE nurture_queue
               SET status = 'rejected', rejected_reason = ?
               WHERE id = ? AND status = 'pending'""",
            (reason, email_id),
        )
        if cursor.rowcount > 0:
            logger.info(
                "Nurture email rejected",
                extra={"context": {"email_id": email_id, "reason": reason}},
            )
            return True
        return False

    def send_approved_emails(self) -> int:
        """Send all approved emails.

        Respects daily send cap.
        Logs as automated attempt on each prospect.

        Returns:
            Number of emails sent
        """
        # Count emails already sent today
        today_str = datetime.now().strftime("%Y-%m-%d")
        row = self.db.fetchone_sql(
            """SELECT COUNT(*) as cnt FROM nurture_queue
               WHERE status = 'sent' AND date(sent_at) = ?""",
            (today_str,),
        )
        already_sent_today = row["cnt"] if row else 0
        remaining_cap = max(0, self.daily_send_cap - already_sent_today)

        if remaining_cap == 0:
            logger.info("Daily send cap reached, no emails sent")
            return 0

        # Fetch approved emails up to remaining cap
        rows = self.db.fetchall_sql(
            """SELECT * FROM nurture_queue
               WHERE status = 'approved'
               ORDER BY approved_at ASC
               LIMIT ?""",
            (remaining_cap,),
        )

        sent_count = 0
        for row in rows:
            email = self._row_to_nurture_email(row)

            # If an Outlook client is provided, attempt real send
            if self.outlook is not None:
                try:
                    self.outlook.send_email(
                        to=email.to_address,
                        subject=email.subject,
                        body=email.body,
                    )
                except Exception as exc:
                    logger.warning(
                        "Outlook send failed",
                        extra={
                            "context": {
                                "email_id": email.id,
                                "error": str(exc),
                            }
                        },
                    )
                    continue

            # Mark as sent
            now = datetime.now().isoformat()
            self.db.execute_sql(
                """UPDATE nurture_queue
                   SET status = 'sent', sent_at = ?
                   WHERE id = ?""",
                (now, email.id),
                commit=False,
            )

            # Log as automated attempt activity
            from src.db.models import Activity, ActivityType, AttemptType

            activity = Activity(
                prospect_id=email.prospect_id,
                activity_type=ActivityType.EMAIL_SENT,
                attempt_type=AttemptType.AUTOMATED,
                email_subject=email.subject,
                email_body=email.body,
                notes=f"Nurture {email.sequence.value} step {email.sequence_step}",
                created_by="system",
            )
            self.db.create_activity(activity)

            sent_count += 1
            logger.info(
                "Nurture email sent",
                extra={
                    "context": {
                        "email_id": email.id,
                        "prospect_id": email.prospect_id,
                    }
                },
            )

        self.db.execute_sql("SELECT 1", commit=True)  # flush pending writes

        logger.info(
            "Approved emails sent",
            extra={"context": {"sent": sent_count}},
        )
        return sent_count

    def _get_prospects_for_nurture(self, limit: int) -> list[Prospect]:
        """Find prospects due for nurture emails.

        Targets UNENGAGED prospects who haven't received a recent automated
        email (based on NURTURE_COOLDOWN_DAYS).
        """
        from src.db.models import Population

        prospects = self.db.get_prospects(population=Population.UNENGAGED, limit=limit * 3)

        eligible: list[Prospect] = []
        cutoff = datetime.now().timestamp() - (self.NURTURE_COOLDOWN_DAYS * 86400)

        for prospect in prospects:
            if len(eligible) >= limit:
                break

            if prospect.id is None:
                continue

            # Check that prospect has at least one email address
            contact_methods = self.db.get_contact_methods(prospect.id)
            has_email = any(
                (m.type.value if hasattr(m.type, "value") else m.type) == "email"
                for m in contact_methods
            )
            if not has_email:
                continue

            # Check for recent automated email activity
            activities = self.db.get_activities(prospect.id, limit=50)
            last_automated_email = None
            for act in activities:
                if (
                    act.activity_type == ActivityType.EMAIL_SENT
                    and act.attempt_type == AttemptType.AUTOMATED
                ):
                    last_automated_email = act.created_at
                    break  # Activities are most-recent-first

            if last_automated_email is not None:
                # Parse the timestamp if it's a string
                if isinstance(last_automated_email, str):
                    try:
                        last_ts = datetime.fromisoformat(last_automated_email).timestamp()
                    except (ValueError, TypeError):
                        last_ts = 0
                else:
                    last_ts = last_automated_email.timestamp()

                if last_ts > cutoff:
                    continue  # Too recent, skip

            # Also check that there's no pending/approved email in the queue
            row = self.db.fetchone_sql(
                """SELECT COUNT(*) as cnt FROM nurture_queue
                   WHERE prospect_id = ? AND status IN ('pending', 'approved')""",
                (prospect.id,),
            )
            if row and row["cnt"] > 0:
                continue

            eligible.append(prospect)

        return eligible

    def _determine_sequence(self, prospect: Prospect) -> tuple[NurtureSequence, int]:
        """Determine which sequence and step for prospect.

        Logic:
        - BREAKUP: 5+ attempts and no response -> 1 final email
        - RE_ENGAGEMENT: was engaged but went quiet (has ENGAGED history
          in activities)
        - WARM_TOUCH: default for unengaged with 2+ attempts and no
          email sent
        """
        assert prospect.id is not None
        activities = self.db.get_activities(prospect.id, limit=100)

        # Check for prior engagement (was ever ENGAGED)
        was_engaged = any(
            act.population_before is not None and act.population_before.value == "engaged"
            for act in activities
        )

        # Count previous automated nurture emails sent
        nurture_emails_sent = sum(
            1
            for act in activities
            if act.activity_type == ActivityType.EMAIL_SENT
            and act.attempt_type == AttemptType.AUTOMATED
        )

        attempt_count = prospect.attempt_count or 0

        # BREAKUP: many attempts, no response
        if attempt_count >= 5:
            # Only send breakup if we haven't already sent one
            row = self.db.fetchone_sql(
                """SELECT COUNT(*) as cnt FROM nurture_queue
                   WHERE prospect_id = ? AND sequence = ?
                   AND status IN ('sent', 'pending', 'approved')""",
                (prospect.id, NurtureSequence.BREAKUP.value),
            )
            if not row or row["cnt"] == 0:
                return NurtureSequence.BREAKUP, 1

        # RE_ENGAGEMENT: was engaged but now unengaged
        if was_engaged:
            config = self.SEQUENCE_CONFIG[NurtureSequence.RE_ENGAGEMENT]
            # Figure out which step we're on
            row = self.db.fetchone_sql(
                """SELECT MAX(sequence_step) as max_step FROM nurture_queue
                   WHERE prospect_id = ? AND sequence = ?
                   AND status = 'sent'""",
                (prospect.id, NurtureSequence.RE_ENGAGEMENT.value),
            )
            last_step = row["max_step"] if row and row["max_step"] else 0
            next_step = last_step + 1
            if next_step <= config["max_steps"]:
                return NurtureSequence.RE_ENGAGEMENT, next_step

        # WARM_TOUCH: default sequence
        config = self.SEQUENCE_CONFIG[NurtureSequence.WARM_TOUCH]
        row = self.db.fetchone_sql(
            """SELECT MAX(sequence_step) as max_step FROM nurture_queue
               WHERE prospect_id = ? AND sequence = ?
               AND status = 'sent'""",
            (prospect.id, NurtureSequence.WARM_TOUCH.value),
        )
        last_step = row["max_step"] if row and row["max_step"] else 0
        next_step = last_step + 1
        if next_step <= config["max_steps"]:
            return NurtureSequence.WARM_TOUCH, next_step

        # If we've exhausted warm touch, try breakup
        row = self.db.fetchone_sql(
            """SELECT COUNT(*) as cnt FROM nurture_queue
               WHERE prospect_id = ? AND sequence = ?
               AND status IN ('sent', 'pending', 'approved')""",
            (prospect.id, NurtureSequence.BREAKUP.value),
        )
        if not row or row["cnt"] == 0:
            return NurtureSequence.BREAKUP, 1

        # Fallback: warm touch step 1 (restart)
        return NurtureSequence.WARM_TOUCH, 1

    def _generate_email(
        self,
        prospect: Prospect,
        sequence: NurtureSequence,
        step: int,
    ) -> NurtureEmail:
        """Generate email content for prospect using templates."""
        assert prospect.id is not None
        # Get company and contact info
        company = self.db.get_company(prospect.company_id) if prospect.company_id else None
        company_name = company.name if company else "your company"
        state = company.state if company and company.state else "your area"

        # Get primary email address
        contact_methods = self.db.get_contact_methods(prospect.id)
        to_address = ""
        for m in contact_methods:
            method_type = m.type.value if hasattr(m.type, "value") else m.type
            if method_type == "email":
                to_address = m.value
                if m.is_primary:
                    break  # Use primary if available

        # Look up template
        template = self.TEMPLATES.get((sequence, step))
        if template is None:
            # Fallback template
            template = {
                "subject": f"Following up - {prospect.first_name}",
                "body": (
                    f"Hi {prospect.first_name},\n\n"
                    f"I wanted to reach out and see if there's an opportunity "
                    f"to connect about {company_name}.\n\n"
                    f"Best,\nJeff"
                ),
            }

        # Format template with prospect data
        format_vars = {
            "first_name": prospect.first_name or "there",
            "last_name": prospect.last_name or "",
            "company_name": company_name,
            "state": state,
            "title": prospect.title or "",
        }

        subject = template["subject"].format(**format_vars)
        body = template["body"].format(**format_vars)

        return NurtureEmail(
            prospect_id=prospect.id,
            prospect_name=prospect.full_name,
            company_name=company_name,
            sequence=sequence,
            sequence_step=step,
            subject=subject,
            body=body,
            to_address=to_address,
            status="pending",
        )

    @staticmethod
    def _row_to_nurture_email(row) -> NurtureEmail:
        """Convert a database row to a NurtureEmail dataclass."""
        return NurtureEmail(
            id=row["id"],
            prospect_id=row["prospect_id"],
            prospect_name=row["prospect_name"] or "",
            company_name=row["company_name"] or "",
            sequence=NurtureSequence(row["sequence"]),
            sequence_step=row["sequence_step"],
            subject=row["subject"],
            body=row["body"],
            to_address=row["to_address"] or "",
            status=row["status"],
            queued_at=row["queued_at"],
            approved_at=row["approved_at"],
            sent_at=row["sent_at"],
        )
