"""Tests for nurture email engine.

Tests Phase 5: Nurture Engine
    - Nurture batch generation
    - Pending approval retrieval
    - Email approval workflow
    - Email rejection workflow
    - Sequence determination logic
    - Email content generation
"""

from datetime import datetime, timedelta

import pytest

from src.db.database import Database
from src.db.models import (
    Activity,
    ActivityType,
    AttemptType,
    Company,
    ContactMethod,
    ContactMethodType,
    EngagementStage,
    Population,
    Prospect,
)
from src.engine.nurture import (
    NurtureEmail,
    NurtureEngine,
    NurtureSequence,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def memory_db():
    """In-memory database for fast tests."""
    db = Database(":memory:")
    db.initialize()
    yield db
    db.close()


@pytest.fixture
def nurture_db(memory_db):
    """Database with unengaged prospects suitable for nurture emails.

    Creates:
        - Company "Acme Corp"
        - Prospect 1: UNENGAGED, has email, 2 attempts (warm touch candidate)
        - Prospect 2: UNENGAGED, has email, 6 attempts (breakup candidate)
        - Prospect 3: UNENGAGED, no email (should be skipped)
    """
    company = Company(
        name="Acme Corp",
        domain="acme.com",
        state="TX",
        size="medium",
    )
    cid = memory_db.create_company(company)

    # Prospect 1: warm touch candidate
    p1 = Prospect(
        company_id=cid,
        first_name="Alice",
        last_name="Warm",
        title="VP of Operations",
        population=Population.UNENGAGED,
        attempt_count=2,
        prospect_score=75,
    )
    p1_id = memory_db.create_prospect(p1)
    memory_db.create_contact_method(
        ContactMethod(
            prospect_id=p1_id,
            type=ContactMethodType.EMAIL,
            value="alice@acme.com",
            label="work",
        )
    )

    # Prospect 2: breakup candidate (5+ attempts)
    p2 = Prospect(
        company_id=cid,
        first_name="Bob",
        last_name="Breakup",
        title="CEO",
        population=Population.UNENGAGED,
        attempt_count=6,
        prospect_score=60,
    )
    p2_id = memory_db.create_prospect(p2)
    memory_db.create_contact_method(
        ContactMethod(
            prospect_id=p2_id,
            type=ContactMethodType.EMAIL,
            value="bob@acme.com",
            label="work",
        )
    )

    # Prospect 3: no email (should be skipped)
    p3 = Prospect(
        company_id=cid,
        first_name="Charlie",
        last_name="NoEmail",
        population=Population.UNENGAGED,
        attempt_count=1,
    )
    p3_id = memory_db.create_prospect(p3)
    memory_db.create_contact_method(
        ContactMethod(
            prospect_id=p3_id,
            type=ContactMethodType.PHONE,
            value="555-333-3333",
        )
    )

    return memory_db, cid, p1_id, p2_id, p3_id


# =============================================================================
# generate_nurture_batch
# =============================================================================


class TestGenerateNurtureBatch:
    """Test nurture batch generation."""

    def test_generates_emails_for_eligible_prospects(self, nurture_db):
        """Generates emails for prospects with email addresses."""
        db, cid, p1_id, p2_id, p3_id = nurture_db
        engine = NurtureEngine(db)
        batch = engine.generate_nurture_batch(limit=30)

        # p1 and p2 have emails, p3 does not
        prospect_ids = [e.prospect_id for e in batch]
        assert p1_id in prospect_ids
        assert p2_id in prospect_ids
        assert p3_id not in prospect_ids

    def test_generated_emails_have_content(self, nurture_db):
        """Generated emails have subject and body."""
        db, cid, p1_id, p2_id, p3_id = nurture_db
        engine = NurtureEngine(db)
        batch = engine.generate_nurture_batch(limit=30)

        for email in batch:
            assert email.subject != ""
            assert email.body != ""
            assert email.to_address != ""
            assert email.status == "pending"

    def test_respects_limit(self, nurture_db):
        """Batch respects the limit parameter."""
        db, cid, p1_id, p2_id, p3_id = nurture_db
        engine = NurtureEngine(db)
        batch = engine.generate_nurture_batch(limit=1)
        assert len(batch) <= 1

    def test_empty_database(self, memory_db):
        """Empty database produces no emails."""
        engine = NurtureEngine(memory_db)
        batch = engine.generate_nurture_batch(limit=30)
        assert len(batch) == 0

    def test_no_duplicate_pending(self, nurture_db):
        """Running batch twice does not create duplicate pending emails."""
        db, cid, p1_id, p2_id, p3_id = nurture_db
        engine = NurtureEngine(db)
        batch1 = engine.generate_nurture_batch(limit=30)
        assert len(batch1) >= 2

        batch2 = engine.generate_nurture_batch(limit=30)
        # All prospects from batch1 should now be skipped (pending in queue)
        assert len(batch2) == 0

    def test_skips_recently_emailed(self, nurture_db):
        """Skips prospects who received a recent automated email."""
        db, cid, p1_id, p2_id, p3_id = nurture_db

        # Create a recent automated email activity for p1
        activity = Activity(
            prospect_id=p1_id,
            activity_type=ActivityType.EMAIL_SENT,
            attempt_type=AttemptType.AUTOMATED,
            notes="Recent nurture email",
            created_by="system",
        )
        db.create_activity(activity)

        engine = NurtureEngine(db)
        batch = engine.generate_nurture_batch(limit=30)

        prospect_ids = [e.prospect_id for e in batch]
        # p1 should be skipped due to recent automated email
        assert p1_id not in prospect_ids
        # p2 has no recent automated email, should be included
        assert p2_id in prospect_ids


# =============================================================================
# get_pending_approval
# =============================================================================


class TestGetPendingApproval:
    """Test retrieval of queued emails."""

    def test_returns_pending_emails(self, nurture_db):
        """Returns emails with pending status."""
        db, cid, p1_id, p2_id, p3_id = nurture_db
        engine = NurtureEngine(db)
        engine.generate_nurture_batch(limit=30)

        pending = engine.get_pending_approval()
        assert len(pending) >= 2
        for email in pending:
            assert email.status == "pending"
            assert isinstance(email, NurtureEmail)

    def test_empty_queue(self, memory_db):
        """Empty queue returns empty list."""
        engine = NurtureEngine(memory_db)
        pending = engine.get_pending_approval()
        assert pending == []


# =============================================================================
# approve_email
# =============================================================================


class TestApproveEmail:
    """Test email approval workflow."""

    def test_approve_pending_email(self, nurture_db):
        """Approving a pending email changes its status."""
        db, cid, p1_id, p2_id, p3_id = nurture_db
        engine = NurtureEngine(db)
        batch = engine.generate_nurture_batch(limit=30)
        email_id = batch[0].id

        result = engine.approve_email(email_id)
        assert result is True

        # Verify the email is now approved
        pending = engine.get_pending_approval()
        approved_ids = [e.id for e in pending]
        assert email_id not in approved_ids

    def test_approve_nonexistent_email(self, memory_db):
        """Approving nonexistent email returns False."""
        engine = NurtureEngine(memory_db)
        result = engine.approve_email(999)
        assert result is False

    def test_approve_already_approved(self, nurture_db):
        """Approving already-approved email returns False."""
        db, cid, p1_id, p2_id, p3_id = nurture_db
        engine = NurtureEngine(db)
        batch = engine.generate_nurture_batch(limit=30)
        email_id = batch[0].id

        engine.approve_email(email_id)
        result = engine.approve_email(email_id)
        assert result is False


# =============================================================================
# reject_email
# =============================================================================


class TestRejectEmail:
    """Test email rejection workflow."""

    def test_reject_pending_email(self, nurture_db):
        """Rejecting a pending email changes its status."""
        db, cid, p1_id, p2_id, p3_id = nurture_db
        engine = NurtureEngine(db)
        batch = engine.generate_nurture_batch(limit=30)
        email_id = batch[0].id

        result = engine.reject_email(email_id, reason="Not appropriate")
        assert result is True

        # Email is no longer pending
        pending = engine.get_pending_approval()
        pending_ids = [e.id for e in pending]
        assert email_id not in pending_ids

    def test_reject_nonexistent(self, memory_db):
        """Rejecting nonexistent email returns False."""
        engine = NurtureEngine(memory_db)
        result = engine.reject_email(999, reason="nope")
        assert result is False

    def test_reject_without_reason(self, nurture_db):
        """Rejection works without a reason."""
        db, cid, p1_id, p2_id, p3_id = nurture_db
        engine = NurtureEngine(db)
        batch = engine.generate_nurture_batch(limit=30)
        email_id = batch[0].id

        result = engine.reject_email(email_id)
        assert result is True

    def test_reject_already_rejected(self, nurture_db):
        """Rejecting already-rejected email returns False."""
        db, cid, p1_id, p2_id, p3_id = nurture_db
        engine = NurtureEngine(db)
        batch = engine.generate_nurture_batch(limit=30)
        email_id = batch[0].id

        engine.reject_email(email_id)
        result = engine.reject_email(email_id)
        assert result is False


# =============================================================================
# _determine_sequence
# =============================================================================


class TestDetermineSequence:
    """Test sequence selection logic."""

    def test_warm_touch_for_low_attempts(self, nurture_db):
        """Prospect with few attempts gets WARM_TOUCH."""
        db, cid, p1_id, p2_id, p3_id = nurture_db
        engine = NurtureEngine(db)

        prospect = db.get_prospect(p1_id)
        sequence, step = engine._determine_sequence(prospect)
        assert sequence == NurtureSequence.WARM_TOUCH
        assert step == 1

    def test_breakup_for_high_attempts(self, nurture_db):
        """Prospect with 5+ attempts gets BREAKUP."""
        db, cid, p1_id, p2_id, p3_id = nurture_db
        engine = NurtureEngine(db)

        prospect = db.get_prospect(p2_id)
        sequence, step = engine._determine_sequence(prospect)
        assert sequence == NurtureSequence.BREAKUP
        assert step == 1

    def test_re_engagement_for_previously_engaged(self, memory_db):
        """Prospect that was previously engaged gets RE_ENGAGEMENT."""
        company = Company(name="Test Co", state="CA")
        cid = memory_db.create_company(company)
        prospect = Prospect(
            company_id=cid,
            first_name="Lapsed",
            last_name="Lead",
            population=Population.UNENGAGED,
            attempt_count=2,
        )
        pid = memory_db.create_prospect(prospect)
        memory_db.create_contact_method(
            ContactMethod(
                prospect_id=pid,
                type=ContactMethodType.EMAIL,
                value="lapsed@test.com",
            )
        )
        # Log an activity with population_before=ENGAGED to indicate prior engagement
        activity = Activity(
            prospect_id=pid,
            activity_type=ActivityType.STATUS_CHANGE,
            population_before=Population.ENGAGED,
            population_after=Population.UNENGAGED,
            notes="Went cold",
        )
        memory_db.create_activity(activity)

        engine = NurtureEngine(memory_db)
        p = memory_db.get_prospect(pid)
        sequence, step = engine._determine_sequence(p)
        assert sequence == NurtureSequence.RE_ENGAGEMENT
        assert step == 1

    def test_warm_touch_step_increments(self, nurture_db):
        """After sending step 1, next call returns step 2."""
        db, cid, p1_id, p2_id, p3_id = nurture_db
        engine = NurtureEngine(db)

        # Insert a sent warm_touch step 1 into nurture_queue
        conn = db._get_connection()
        conn.execute(
            """INSERT INTO nurture_queue
               (prospect_id, sequence, sequence_step, subject, body, status)
               VALUES (?, ?, ?, ?, ?, 'sent')""",
            (p1_id, NurtureSequence.WARM_TOUCH.value, 1, "test", "test"),
        )
        conn.commit()

        prospect = db.get_prospect(p1_id)
        sequence, step = engine._determine_sequence(prospect)
        assert sequence == NurtureSequence.WARM_TOUCH
        assert step == 2


# =============================================================================
# _generate_email
# =============================================================================


class TestGenerateEmail:
    """Test email content generation."""

    def test_email_has_prospect_info(self, nurture_db):
        """Generated email contains prospect name in body."""
        db, cid, p1_id, p2_id, p3_id = nurture_db
        engine = NurtureEngine(db)

        prospect = db.get_prospect(p1_id)
        email = engine._generate_email(prospect, NurtureSequence.WARM_TOUCH, 1)

        assert email.prospect_id == p1_id
        assert "Alice" in email.body
        assert email.to_address == "alice@acme.com"
        assert email.prospect_name == "Alice Warm"

    def test_email_has_company_name(self, nurture_db):
        """Generated email contains company name."""
        db, cid, p1_id, p2_id, p3_id = nurture_db
        engine = NurtureEngine(db)

        prospect = db.get_prospect(p1_id)
        email = engine._generate_email(prospect, NurtureSequence.WARM_TOUCH, 1)

        assert "Acme Corp" in email.subject or "Acme Corp" in email.body

    def test_breakup_template(self, nurture_db):
        """Breakup email uses the breakup template."""
        db, cid, p1_id, p2_id, p3_id = nurture_db
        engine = NurtureEngine(db)

        prospect = db.get_prospect(p2_id)
        email = engine._generate_email(prospect, NurtureSequence.BREAKUP, 1)

        assert "closing the loop" in email.subject.lower() or "inbox" in email.body.lower()
        assert email.sequence == NurtureSequence.BREAKUP
        assert email.sequence_step == 1

    def test_re_engagement_template(self, nurture_db):
        """Re-engagement email uses correct template."""
        db, cid, p1_id, p2_id, p3_id = nurture_db
        engine = NurtureEngine(db)

        prospect = db.get_prospect(p1_id)
        email = engine._generate_email(prospect, NurtureSequence.RE_ENGAGEMENT, 1)

        assert email.sequence == NurtureSequence.RE_ENGAGEMENT
        assert email.sequence_step == 1
        assert "checking in" in email.subject.lower() or "while" in email.body.lower()

    def test_warm_touch_all_steps(self, nurture_db):
        """All warm touch steps generate valid emails."""
        db, cid, p1_id, p2_id, p3_id = nurture_db
        engine = NurtureEngine(db)

        prospect = db.get_prospect(p1_id)
        for step in [1, 2, 3]:
            email = engine._generate_email(prospect, NurtureSequence.WARM_TOUCH, step)
            assert email.subject != ""
            assert email.body != ""
            assert email.sequence_step == step

    def test_email_status_is_pending(self, nurture_db):
        """Generated email has pending status."""
        db, cid, p1_id, p2_id, p3_id = nurture_db
        engine = NurtureEngine(db)

        prospect = db.get_prospect(p1_id)
        email = engine._generate_email(prospect, NurtureSequence.WARM_TOUCH, 1)
        assert email.status == "pending"


# =============================================================================
# Full workflow integration
# =============================================================================


class TestNurtureWorkflow:
    """Test end-to-end nurture workflow."""

    def test_generate_approve_send(self, nurture_db):
        """Full workflow: generate -> approve -> send."""
        db, cid, p1_id, p2_id, p3_id = nurture_db
        engine = NurtureEngine(db)

        # Generate
        batch = engine.generate_nurture_batch(limit=30)
        assert len(batch) >= 1

        # Approve first email
        email_id = batch[0].id
        engine.approve_email(email_id)

        # Fix the approved_at timestamp format for SQLite compatibility.
        # approve_email() stores isoformat (with 'T'), but SQLite's
        # PARSE_DECLTYPES expects space-separated datetime strings.
        conn = db._get_connection()
        conn.execute(
            "UPDATE nurture_queue SET approved_at = REPLACE(approved_at, 'T', ' ') WHERE id = ?",
            (email_id,),
        )
        conn.commit()

        # Send (no Outlook client = testing mode, marks as sent)
        sent = engine.send_approved_emails()
        assert sent == 1

    def test_send_with_outlook_client(self, nurture_db):
        """When Outlook client is provided, send_email is called."""
        db, cid, p1_id, p2_id, p3_id = nurture_db

        # Create a mock Outlook client
        class MockOutlook:
            def __init__(self):
                self.sent = []

            def send_email(self, to, subject, body):
                self.sent.append({"to": to, "subject": subject, "body": body})

        mock_outlook = MockOutlook()
        engine = NurtureEngine(db, outlook=mock_outlook)

        # Generate and approve
        batch = engine.generate_nurture_batch(limit=30)
        assert len(batch) >= 1
        email_id = batch[0].id
        engine.approve_email(email_id)

        # Fix timestamp format
        conn = db._get_connection()
        conn.execute(
            "UPDATE nurture_queue SET approved_at = REPLACE(approved_at, 'T', ' ') WHERE id = ?",
            (email_id,),
        )
        conn.commit()

        # Send with Outlook client
        sent = engine.send_approved_emails()
        assert sent == 1
        assert len(mock_outlook.sent) == 1
        assert mock_outlook.sent[0]["to"] == batch[0].to_address
