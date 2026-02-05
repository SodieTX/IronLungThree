"""Nightly cycle - System maintenance while Jeff sleeps.

11-step cycle running 2:00 AM - 7:00 AM:
    1. Backup (local + cloud)
    2. Pull from ActiveCampaign
    3. Run dedup
    4. Assess new records
    5. Autonomous research on Broken
    6. Groundskeeper: flag stale data
    7. Re-score all active prospects
    8. Check monthly buckets
    9. Draft nurture sequences
    10. Pre-generate morning brief + cards
    11. Extract intel nuggets
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import Population

logger = get_logger(__name__)

# Sentinel values for tracking nightly cycle runs
_CYCLE_SENTINEL_PROSPECT_ID = 0
_CYCLE_SENTINEL_FIELD = "nightly_cycle_last_run"


@dataclass
class NightlyCycleResult:
    """Result of nightly cycle."""

    started_at: datetime
    completed_at: Optional[datetime] = None
    backups_created: int = 0
    prospects_imported: int = 0
    duplicates_merged: int = 0
    research_completed: int = 0
    stale_flagged: int = 0
    prospects_scored: int = 0
    buckets_activated: int = 0
    nurture_drafted: int = 0
    cards_prepared: int = 0
    intel_extracted: int = 0
    errors: list[str] = field(default_factory=list)


def run_nightly_cycle(db: Database) -> NightlyCycleResult:
    """Execute full 11-step nightly cycle.

    Each step is wrapped in try/except so one failure doesn't stop
    the entire cycle. Errors are collected in the result.

    Args:
        db: Database instance

    Returns:
        NightlyCycleResult with metrics from each step
    """
    result = NightlyCycleResult(started_at=datetime.now())
    logger.info("Nightly cycle starting")

    # Step 1: Backup
    logger.info("Nightly step 1/11: Backup")
    try:
        from src.db.backup import BackupManager

        backup = BackupManager()
        backup.create_backup(label="nightly")
        backup.sync_to_cloud()
        backup.cleanup_old_backups(keep_days=30)
        result.backups_created = 1
        logger.info("Nightly step 1 complete: backup created")
    except Exception as e:
        result.errors.append(f"Step 1 (Backup): {e}")
        logger.error(f"Nightly step 1 failed: {e}")

    # Step 2: Pull from ActiveCampaign
    logger.info("Nightly step 2/11: ActiveCampaign pull")
    try:
        from src.integrations.activecampaign import ActiveCampaignClient

        ac = ActiveCampaignClient()
        if ac.is_configured():
            contacts = ac.get_contacts(limit=100)
            imported = _import_ac_contacts(db, contacts)
            result.prospects_imported = imported
            logger.info(f"Nightly step 2 complete: {imported} contacts imported")
        else:
            logger.info("Nightly step 2 skipped: ActiveCampaign not configured")
    except Exception as e:
        result.errors.append(f"Step 2 (AC Pull): {e}")
        logger.error(f"Nightly step 2 failed: {e}")

    # Step 3: Dedup (handled during import, minimal pass here)
    logger.info("Nightly step 3/11: Dedup check")
    try:
        # Dedup is already handled by the intake module during import.
        # No additional pass needed unless we detect issues.
        result.duplicates_merged = 0
        logger.info("Nightly step 3 complete: dedup handled during import")
    except Exception as e:
        result.errors.append(f"Step 3 (Dedup): {e}")
        logger.error(f"Nightly step 3 failed: {e}")

    # Step 4: Assess new records
    logger.info("Nightly step 4/11: Assess new records")
    try:
        from src.db.models import ContactMethodType, assess_completeness

        # Find any records that might need reassessment
        broken = db.get_prospects(population=Population.BROKEN, limit=500)
        assessed = 0
        for prospect in broken:
            if prospect.id is None:
                continue
            contact_methods = db.get_contact_methods(prospect.id)
            new_pop = assess_completeness(prospect, contact_methods)
            if new_pop == Population.UNENGAGED and prospect.population == Population.BROKEN:
                from src.engine.populations import transition_prospect

                transition_prospect(
                    db, prospect.id, Population.UNENGAGED, "Nightly assessment: data complete"
                )
                assessed += 1
        logger.info(f"Nightly step 4 complete: {assessed} records promoted from broken")
    except Exception as e:
        result.errors.append(f"Step 4 (Assess): {e}")
        logger.error(f"Nightly step 4 failed: {e}")

    # Step 5: Autonomous research on Broken
    logger.info("Nightly step 5/11: Autonomous research")
    try:
        from src.engine.research import ResearchEngine

        engine = ResearchEngine(db)
        researched = engine.run_batch(limit=50)
        result.research_completed = researched
        logger.info(f"Nightly step 5 complete: {researched} prospects researched")
    except Exception as e:
        result.errors.append(f"Step 5 (Research): {e}")
        logger.error(f"Nightly step 5 failed: {e}")

    # Step 6: Groundskeeper - flag stale data
    logger.info("Nightly step 6/11: Groundskeeper")
    try:
        from src.engine.groundskeeper import Groundskeeper

        gk = Groundskeeper(db)
        maintenance = gk.run_maintenance()
        result.stale_flagged = maintenance.get("flagged", 0)
        logger.info(f"Nightly step 6 complete: {result.stale_flagged} stale records flagged")
    except Exception as e:
        result.errors.append(f"Step 6 (Groundskeeper): {e}")
        logger.error(f"Nightly step 6 failed: {e}")

    # Step 7: Re-score all active prospects
    logger.info("Nightly step 7/11: Re-scoring")
    try:
        from src.engine.scoring import rescore_all

        scored = rescore_all(db)
        result.prospects_scored = scored
        logger.info(f"Nightly step 7 complete: {scored} prospects re-scored")
    except Exception as e:
        result.errors.append(f"Step 7 (Rescore): {e}")
        logger.error(f"Nightly step 7 failed: {e}")

    # Step 8: Monthly bucket auto-activation
    logger.info("Nightly step 8/11: Monthly buckets")
    try:
        activated = _activate_monthly_buckets(db)
        result.buckets_activated = activated
        logger.info(f"Nightly step 8 complete: {activated} parked prospects activated")
    except Exception as e:
        result.errors.append(f"Step 8 (Buckets): {e}")
        logger.error(f"Nightly step 8 failed: {e}")

    # Step 9: Draft nurture sequences
    logger.info("Nightly step 9/11: Nurture drafting")
    try:
        from src.engine.nurture import NurtureEngine

        nurture = NurtureEngine(db)
        drafted = nurture.generate_nurture_batch(limit=25)
        result.nurture_drafted = len(drafted) if isinstance(drafted, list) else drafted
        logger.info(f"Nightly step 9 complete: {result.nurture_drafted} nurture emails drafted")
    except Exception as e:
        result.errors.append(f"Step 9 (Nurture): {e}")
        logger.error(f"Nightly step 9 failed: {e}")

    # Step 10: Pre-generate morning brief
    logger.info("Nightly step 10/11: Morning brief")
    try:
        from src.content.morning_brief import generate_morning_brief

        brief = generate_morning_brief(db)
        result.cards_prepared = 1
        logger.info(f"Nightly step 10 complete: morning brief generated")
    except Exception as e:
        result.errors.append(f"Step 10 (Brief): {e}")
        logger.error(f"Nightly step 10 failed: {e}")

    # Step 11: Extract intel nuggets from recent activities
    logger.info("Nightly step 11/11: Intel extraction")
    try:
        extracted = _extract_intel_from_activities(db)
        result.intel_extracted = extracted
        logger.info(f"Nightly step 11 complete: {extracted} intel nuggets extracted")
    except Exception as e:
        result.errors.append(f"Step 11 (Intel): {e}")
        logger.error(f"Nightly step 11 failed: {e}")

    # Record completion
    result.completed_at = datetime.now()
    _record_cycle_run(db)

    error_count = len(result.errors)
    if error_count == 0:
        logger.info("Nightly cycle completed successfully")
    else:
        logger.warning(f"Nightly cycle completed with {error_count} error(s)")

    return result


def run_condensed_cycle(db: Database) -> NightlyCycleResult:
    """Run quick catch-up after missed nightly cycle.

    Only runs critical steps: backup, bucket activation, morning brief.

    Args:
        db: Database instance

    Returns:
        NightlyCycleResult with metrics
    """
    result = NightlyCycleResult(started_at=datetime.now())
    logger.info("Condensed cycle starting")

    # Step 1: Backup
    try:
        from src.db.backup import BackupManager

        backup = BackupManager()
        backup.create_backup(label="catchup")
        result.backups_created = 1
    except Exception as e:
        result.errors.append(f"Backup: {e}")

    # Step 2: Monthly bucket activation
    try:
        activated = _activate_monthly_buckets(db)
        result.buckets_activated = activated
    except Exception as e:
        result.errors.append(f"Buckets: {e}")

    # Step 3: Morning brief
    try:
        from src.content.morning_brief import generate_morning_brief

        generate_morning_brief(db)
        result.cards_prepared = 1
    except Exception as e:
        result.errors.append(f"Brief: {e}")

    result.completed_at = datetime.now()
    _record_cycle_run(db)

    logger.info("Condensed cycle completed")
    return result


def check_last_run(db: Database) -> Optional[datetime]:
    """Check when nightly cycle last ran.

    Uses a sentinel record in data_freshness table.

    Args:
        db: Database instance

    Returns:
        Datetime of last run, or None if never run
    """
    conn = db._get_connection()
    row = conn.execute(
        "SELECT verified_date FROM data_freshness WHERE prospect_id = ? AND field_name = ? "
        "ORDER BY verified_date DESC LIMIT 1",
        (_CYCLE_SENTINEL_PROSPECT_ID, _CYCLE_SENTINEL_FIELD),
    ).fetchone()

    if row is None:
        return None

    verified = row["verified_date"]
    if isinstance(verified, str):
        try:
            return datetime.fromisoformat(verified)
        except (ValueError, TypeError):
            return None
    elif isinstance(verified, datetime):
        return verified
    elif isinstance(verified, date):
        return datetime(verified.year, verified.month, verified.day)
    return None


def _record_cycle_run(db: Database) -> None:
    """Record nightly cycle completion in data_freshness."""
    try:
        db.create_data_freshness(
            prospect_id=_CYCLE_SENTINEL_PROSPECT_ID,
            field_name=_CYCLE_SENTINEL_FIELD,
            verified_date=date.today(),
            verification_method="nightly_cycle",
        )
    except Exception as e:
        logger.warning(f"Failed to record cycle run: {e}")


def _activate_monthly_buckets(db: Database) -> int:
    """Activate parked prospects whose month has arrived.

    Checks for prospects with parked_month matching current YYYY-MM.
    Transitions them back to UNENGAGED.

    Returns:
        Number of prospects activated
    """
    from src.engine.populations import transition_prospect

    current_month = date.today().strftime("%Y-%m")
    parked = db.get_prospects(population=Population.PARKED, limit=500)
    activated = 0

    for prospect in parked:
        if prospect.id is None:
            continue
        if prospect.parked_month and prospect.parked_month <= current_month:
            try:
                transition_prospect(
                    db,
                    prospect.id,
                    Population.UNENGAGED,
                    f"Monthly bucket: parked_month {prospect.parked_month} reached",
                )
                activated += 1
            except Exception as e:
                logger.warning(f"Failed to activate parked prospect {prospect.id}: {e}")

    if activated > 0:
        logger.info(f"Activated {activated} parked prospects for {current_month}")

    return activated


def _import_ac_contacts(db: Database, contacts: list) -> int:
    """Import ActiveCampaign contacts into the database.

    Performs basic dedup by email before importing.

    Args:
        db: Database instance
        contacts: List of ACContact objects

    Returns:
        Number of new contacts imported
    """
    from src.db.models import Company, ContactMethod, ContactMethodType, Prospect

    imported = 0

    for contact in contacts:
        if not contact.email:
            continue

        # Check for existing prospect by email
        existing = db.find_prospect_by_email(contact.email)
        if existing is not None:
            continue

        # Create or find company
        company_id = None
        if contact.company:
            existing_company = db.get_company_by_normalized_name(contact.company)
            if existing_company and existing_company.id is not None:
                company_id = existing_company.id
            else:
                company = Company(name=contact.company)
                company_id = db.create_company(company)

        if company_id is None:
            company = Company(name="Unknown (AC Import)")
            company_id = db.create_company(company)

        # Create prospect
        prospect = Prospect(
            company_id=company_id,
            first_name=contact.first_name,
            last_name=contact.last_name,
            source="ActiveCampaign",
        )
        prospect_id = db.create_prospect(prospect)

        # Add email contact method
        email_method = ContactMethod(
            prospect_id=prospect_id,
            type=ContactMethodType.EMAIL,
            value=contact.email,
            is_primary=True,
            source="ActiveCampaign",
        )
        db.create_contact_method(email_method)

        # Add phone if available
        if contact.phone:
            phone_method = ContactMethod(
                prospect_id=prospect_id,
                type=ContactMethodType.PHONE,
                value=contact.phone,
                source="ActiveCampaign",
            )
            db.create_contact_method(phone_method)

        imported += 1

    return imported


def _extract_intel_from_activities(db: Database) -> int:
    """Extract intel nuggets from recent activities.

    Scans activities from the last 24 hours for notable content
    and creates intel nuggets.

    Returns:
        Number of nuggets extracted
    """
    from src.db.models import IntelCategory, IntelNugget

    conn = db._get_connection()
    yesterday = (datetime.now()).strftime("%Y-%m-%d 00:00:00")

    # Get recent activities with notes
    rows = conn.execute(
        """SELECT id, prospect_id, notes, activity_type
           FROM activities
           WHERE created_at >= ?
           AND notes IS NOT NULL
           AND LENGTH(notes) > 20
           ORDER BY created_at DESC
           LIMIT 100""",
        (yesterday,),
    ).fetchall()

    extracted = 0
    for row in rows:
        notes = row["notes"] or ""
        prospect_id = row["prospect_id"]
        activity_id = row["id"]

        # Simple keyword-based intel extraction
        nuggets_to_create: list[tuple[IntelCategory, str]] = []

        notes_lower = notes.lower()

        # Pain point detection
        pain_keywords = [
            "struggling with",
            "frustrated",
            "problem with",
            "challenge",
            "pain point",
            "issue with",
            "concerned about",
            "worried about",
        ]
        for kw in pain_keywords:
            if kw in notes_lower:
                nuggets_to_create.append(
                    (IntelCategory.PAIN_POINT, f"Mentioned: {kw} - {notes[:200]}")
                )
                break

        # Competitor detection
        comp_keywords = [
            "competitor",
            "also looking at",
            "comparing",
            "currently using",
            "switched from",
            "considering",
        ]
        for kw in comp_keywords:
            if kw in notes_lower:
                nuggets_to_create.append(
                    (IntelCategory.COMPETITOR, f"Competitor intel: {notes[:200]}")
                )
                break

        # Timeline detection
        timeline_keywords = [
            "by end of",
            "q1",
            "q2",
            "q3",
            "q4",
            "this quarter",
            "next month",
            "next quarter",
            "deadline",
            "timeline",
        ]
        for kw in timeline_keywords:
            if kw in notes_lower:
                nuggets_to_create.append(
                    (IntelCategory.DECISION_TIMELINE, f"Timeline: {notes[:200]}")
                )
                break

        for category, content in nuggets_to_create:
            # Check for duplicate nuggets
            existing = db.get_intel_nuggets(prospect_id)
            is_duplicate = any(n.category == category and n.content == content for n in existing)
            if not is_duplicate:
                nugget = IntelNugget(
                    prospect_id=prospect_id,
                    category=category,
                    content=content,
                    source_activity_id=activity_id,
                )
                try:
                    db.create_intel_nugget(nugget)
                    extracted += 1
                except Exception:
                    pass

    return extracted
