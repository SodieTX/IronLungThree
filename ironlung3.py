#!/usr/bin/env python3
"""IronLung 3 - ADHD-Optimized Sales Pipeline Management.

Single entry point for the application.

Usage:
    python ironlung3.py              # Launch GUI
    python ironlung3.py --nightly    # Run nightly cycle (headless)
    python ironlung3.py --orchestrator  # Run background orchestrator

The Iron Lung breathes.
"""

import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))


def main() -> int:
    """Main entry point for IronLung 3.
    
    Returns:
        Exit code (0 = success, non-zero = error)
    """
    parser = argparse.ArgumentParser(
        description="IronLung 3 - ADHD-Optimized Sales Pipeline Management"
    )
    parser.add_argument(
        "--nightly",
        action="store_true",
        help="Run nightly cycle (headless mode)"
    )
    parser.add_argument(
        "--orchestrator",
        action="store_true",
        help="Run background orchestrator (headless mode)"
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version and exit"
    )
    
    args = parser.parse_args()
    
    if args.version:
        print("IronLung 3 v0.1.0")
        return 0
    
    print("IronLung 3 starting...")
    
    # Phase 1: Basic startup
    # TODO: Initialize logging
    # TODO: Load configuration
    # TODO: Connect to database
    # TODO: Check/create backup
    
    if args.nightly:
        print("Running nightly cycle...")
        # TODO: Phase 5 - run nightly cycle
        print("Nightly cycle not yet implemented (Phase 5)")
        return 0
    
    if args.orchestrator:
        print("Starting orchestrator...")
        # TODO: Phase 5 - run orchestrator
        print("Orchestrator not yet implemented (Phase 5)")
        return 0
    
    # Launch GUI
    print("Launching GUI...")
    # TODO: Phase 1 - launch main window
    print("GUI not yet implemented (Phase 1, Step 1.14)")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
