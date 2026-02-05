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
            logger.warning(f"Configuration issue: {issue}")

    # Initialize database
    from src.db.database import Database

    try:
        db = Database()
        db.initialize()
        logger.info("Database initialized", extra={"context": {"path": str(config.db_path)}})
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return 1

    # Check for backup (Phase 1, Step 1.11 - will be wired when backup is implemented)
    # from src.db.backup import BackupManager
    # backup = BackupManager()
    # backup.create_backup(label="startup")

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
