"""Orchestrator - Background task coordination.

Coordinates recurring tasks:
    - Reply scanning (30 min)
    - Nurture sending (4 hours)
    - Demo prep (hourly)
    - Calendar sync (hourly)

CRITICAL: Starts with GUI AND runs headless via Task Scheduler.
"""

from datetime import timedelta
from typing import Callable, Optional
from src.core.logging import get_logger

logger = get_logger(__name__)


class Orchestrator:
    """Background task coordinator."""

    def __init__(self) -> None:
        self._running: bool = False
        self._tasks: dict[str, dict] = {}

    def start(self) -> None:
        """Start orchestrator. Called on GUI launch."""
        raise NotImplementedError("Phase 5, Step 5.9")

    def stop(self) -> None:
        """Stop orchestrator gracefully."""
        raise NotImplementedError("Phase 5, Step 5.9")

    def register_task(
        self,
        name: str,
        func: Callable,
        interval: timedelta,
    ) -> None:
        """Register a recurring task."""
        raise NotImplementedError("Phase 5, Step 5.9")

    def run_headless(self) -> None:
        """Run without GUI for Task Scheduler."""
        raise NotImplementedError("Phase 5, Step 5.9")

    def is_running(self) -> bool:
        """Check if orchestrator is running."""
        return self._running
