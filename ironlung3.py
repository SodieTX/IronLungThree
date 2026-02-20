#!/usr/bin/env python3
"""IronLung 3 - ADHD-Optimized Sales Pipeline Management.

Single entry point for the application.

Usage:
    python ironlung3.py              # Launch GUI
    python ironlung3.py --nightly    # Run nightly cycle (headless)
    python ironlung3.py --orchestrator  # Run background orchestrator
    python ironlung3.py --version    # Show version

The Iron Lung breathes.
"""

import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core.config import get_config, validate_config
from src.core.logging import get_logger, setup_logging

__version__ = "0.1.0"


def main() -> int:
    """Main entry point for IronLung 3.

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    parser = argparse.ArgumentParser(
        description="IronLung 3 - ADHD-Optimized Sales Pipeline Management"
    )
    parser.add_argument("--nightly", action="store_true", help="Run nightly cycle (headless mode)")
    parser.add_argument(
        "--orchestrator",
        action="store_true",
        help="Run background orchestrator (headless mode)",
    )
    parser.add_argument("--version", action="store_true", help="Show version and exit")
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show service readiness report and exit",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.version:
        print(f"IronLung 3 v{__version__}")
        return 0

    # Initialize logging
    setup_logging()
    logger = get_logger("main")
    logger.info(f"IronLung 3 v{__version__} starting...")

    # Load and validate configuration
    config = get_config()
    issues = validate_config(config)
    if issues:
        for issue in issues:
            if issue.startswith("CRITICAL:"):
                logger.error(f"Configuration: {issue}")
            else:
                logger.warning(f"Configuration issue: {issue}")

    # Initialize service registry and log what's available
    from src.core.services import get_service_registry

    registry = get_service_registry()
    registry.log_status()

    # --status: print readiness report and exit
    if args.status:
        report = registry.readiness_report()
        print(f"\nIronLung 3 v{__version__} - Service Readiness\n")
        print(report.summary)
        if issues:
            print(f"\nConfiguration issues ({len(issues)}):")
            for issue in issues:
                print(f"  ! {issue}")
        print()
        return 0

    # Initialize database
    from src.db.database import Database

    try:
        db = Database()
        db.initialize()
        logger.info("Database initialized", extra={"context": {"path": str(config.db_path)}})
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return 1

    # Startup backup (Phase 1, Step 1.11)
    from src.db.backup import BackupManager

    try:
        backup = BackupManager()
        backup.create_backup(label="startup")
        logger.info("Startup backup created")
    except Exception as e:
        logger.warning(f"Startup backup failed (non-fatal): {e}")

    if args.nightly:
        logger.info("Running nightly cycle...")
        from src.autonomous.nightly import run_nightly_cycle

        result = run_nightly_cycle(db)
        if result.errors:
            logger.warning(
                f"Nightly cycle completed with {len(result.errors)} error(s)",
                extra={"context": {"errors": result.errors}},
            )
        else:
            logger.info("Nightly cycle completed successfully")
        db.close()
        return 0

    if args.orchestrator:
        logger.info("Starting orchestrator (headless)...")
        from src.autonomous.orchestrator import Orchestrator

        orchestrator = Orchestrator()
        _register_orchestrator_tasks(orchestrator, db)
        orchestrator.run_headless()
        db.close()
        return 0

    # Launch GUI
    logger.info("Launching GUI...")
    # Start background orchestrator alongside GUI
    from src.autonomous.orchestrator import Orchestrator
    from src.gui.app import IronLungApp

    orchestrator = Orchestrator()
    _register_orchestrator_tasks(orchestrator, db)
    orchestrator.start()

    app = IronLungApp(db)
    app.run()

    orchestrator.stop()

    db.close()
    logger.info("IronLung 3 shutdown complete")
    return 0


def _register_orchestrator_tasks(orchestrator, db) -> None:  # type: ignore[no-untyped-def]
    """Register recurring background tasks with the orchestrator.

    Tasks registered (per blueprint):
        - Reply scanning: every 30 minutes
        - Nurture sending: every 4 hours
        - Demo prep refresh: every hour
        - Calendar sync: every hour
    """
    from datetime import timedelta

    from src.core.services import get_service_registry

    registry = get_service_registry()

    # Reply scanning — polls inbox for prospect replies
    if registry.is_available("outlook"):

        def _scan_replies() -> None:
            from src.autonomous.reply_monitor import ReplyMonitor
            from src.integrations.outlook import OutlookClient

            outlook = OutlookClient()
            monitor = ReplyMonitor(db=db, outlook=outlook)
            monitor.poll_inbox()

        orchestrator.register_task("reply_scan", _scan_replies, timedelta(minutes=30))

        # Email sync (received) — sync inbox emails to activity history
        def _sync_emails() -> None:
            from src.autonomous.email_sync import EmailSync
            from src.integrations.outlook import OutlookClient

            outlook = OutlookClient()
            sync = EmailSync(db=db, outlook=outlook)
            sync.sync_received()
            sync.sync_sent()

        orchestrator.register_task("email_sync", _sync_emails, timedelta(hours=1))

    # Nurture sending — send approved nurture drafts
    def _send_nurture() -> None:
        from src.engine.nurture import NurtureEngine

        engine = NurtureEngine(db)
        engine.send_approved_emails()

    orchestrator.register_task("nurture_send", _send_nurture, timedelta(hours=4))

    # Demo prep refresh — pre-generate prep docs for upcoming demos
    def _refresh_demo_prep() -> None:
        from src.engine.demo_prep import generate_prep

        prospects = db.get_prospects(population="demo_scheduled", limit=20)
        for p in prospects:
            if p.id is not None:
                try:
                    generate_prep(db, p.id)
                except Exception:
                    pass  # Individual failure shouldn't stop batch

    orchestrator.register_task("demo_prep", _refresh_demo_prep, timedelta(hours=1))


if __name__ == "__main__":
    sys.exit(main())
