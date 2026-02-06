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
    parser.add_argument("--setup", action="store_true", help="Re-run the install wizard")

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

    # First-run install wizard (or --setup to re-run)
    from src.core.setup_wizard import SetupWizard

    data_dir = config.db_path.parent
    setup = SetupWizard(data_dir=data_dir)

    if args.setup or setup.needs_setup():
        logger.info("Launching install wizard...")
        from src.gui.install_wizard import InstallWizard

        wizard = InstallWizard(data_dir=data_dir)
        result = wizard.run()
        if result is None:
            logger.info("Install wizard cancelled")
            return 0
        logger.info("Install wizard completed, reloading config...")
        from src.core.config import reset_config

        config = get_config()

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
        # TODO: Phase 5 - run nightly cycle
        # from src.autonomous.nightly import run_nightly_cycle
        # run_nightly_cycle(db)
        logger.info("Nightly cycle not yet implemented (Phase 5)")
        db.close()
        return 0

    if args.orchestrator:
        logger.info("Starting orchestrator...")
        # TODO: Phase 5 - run orchestrator
        # from src.autonomous.orchestrator import Orchestrator
        # orchestrator = Orchestrator(db)
        # orchestrator.run()
        logger.info("Orchestrator not yet implemented (Phase 5)")
        db.close()
        return 0

    # Launch GUI
    logger.info("Launching GUI...")
    # TODO: Phase 1, Step 1.14 - launch main window
    # from src.gui.app import IronLungApp
    # app = IronLungApp(db)
    # app.run()
    print("GUI not yet implemented (Phase 1, Step 1.14)")
    print(f"Database ready at: {config.db_path}")
    print(f"Logs at: {config.log_path}")

    db.close()
    logger.info("IronLung 3 shutdown complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
