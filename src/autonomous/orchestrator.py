"""Orchestrator - Background task coordination.

Coordinates recurring tasks:
    - Reply scanning (30 min)
    - Nurture sending (4 hours)
    - Demo prep (hourly)
    - Calendar sync (hourly)

CRITICAL: Starts with GUI AND runs headless via Task Scheduler.
"""

import threading
import time
from datetime import datetime, timedelta
from typing import Callable, Optional

from src.core.logging import get_logger

logger = get_logger(__name__)

# How often the orchestrator checks for tasks ready to run (seconds)
_CHECK_INTERVAL_SECONDS = 30


class Orchestrator:
    """Background task coordinator."""

    def __init__(self) -> None:
        self._running: bool = False
        self._tasks: dict[str, dict] = {}
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start orchestrator in a background daemon thread.

        Called on GUI launch. The daemon thread runs the task loop, checking
        registered tasks and executing them when their interval has elapsed.
        """
        if self._running:
            logger.warning("Orchestrator already running")
            return

        self._running = True
        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._run_loop,
            name="ironlung-orchestrator",
            daemon=True,
        )
        self._thread.start()

        logger.info(
            "Orchestrator started (background)",
            extra={"context": {"tasks": list(self._tasks.keys())}},
        )

    def stop(self) -> None:
        """Stop orchestrator gracefully.

        Signals the background thread to stop and waits for it to finish
        (with a 10-second timeout).
        """
        if not self._running:
            return

        logger.info("Orchestrator stopping...")
        self._running = False
        self._stop_event.set()

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=10)
            if self._thread.is_alive():
                logger.warning("Orchestrator thread did not stop within timeout")

        self._thread = None
        logger.info("Orchestrator stopped")

    def register_task(
        self,
        name: str,
        func: Callable,
        interval: timedelta,
    ) -> None:
        """Register a recurring task.

        Args:
            name: Unique task name (e.g. 'reply_scan', 'nurture_send')
            func: Callable to execute. Should take no arguments.
            interval: How often to run the task.
        """
        self._tasks[name] = {
            "func": func,
            "interval": interval,
            "last_run": None,
        }
        logger.info(
            "Task registered",
            extra={"context": {"name": name, "interval_seconds": interval.total_seconds()}},
        )

    def run_headless(self) -> None:
        """Run without GUI for Task Scheduler mode.

        Same as start() but blocks the main thread. This is used when IronLung
        is launched by Windows Task Scheduler in headless mode.
        """
        if self._running:
            logger.warning("Orchestrator already running")
            return

        self._running = True
        self._stop_event.clear()

        logger.info(
            "Orchestrator started (headless)",
            extra={"context": {"tasks": list(self._tasks.keys())}},
        )

        # Run the loop directly on the main thread (blocks until stopped)
        try:
            self._run_loop()
        except KeyboardInterrupt:
            logger.info("Orchestrator interrupted by keyboard")
        finally:
            self._running = False
            logger.info("Orchestrator headless mode stopped")

    def is_running(self) -> bool:
        """Check if orchestrator is running."""
        return self._running

    def _run_loop(self) -> None:
        """Main task execution loop.

        Continuously checks registered tasks and runs them when their interval
        has elapsed. Catches and logs exceptions from individual tasks so that
        one failure never crashes the orchestrator.
        """
        logger.debug("Orchestrator loop started")

        while self._running:
            now = datetime.utcnow()

            for name, task_info in self._tasks.items():
                last_run = task_info["last_run"]
                interval = task_info["interval"]

                # Determine if the task is due to run
                if last_run is None or (now - last_run) >= interval:
                    logger.info(
                        f"Running task: {name}",
                        extra={"context": {"task": name}},
                    )
                    try:
                        task_info["func"]()
                        task_info["last_run"] = datetime.utcnow()
                        logger.info(
                            f"Task completed: {name}",
                            extra={"context": {"task": name}},
                        )
                    except Exception as exc:
                        # Never crash the orchestrator due to a task failure
                        task_info["last_run"] = datetime.utcnow()
                        logger.error(
                            f"Task failed: {name}",
                            extra={"context": {"task": name, "error": str(exc)}},
                            exc_info=True,
                        )

            # Sleep in small increments so we can respond to stop signals quickly
            if self._stop_event.wait(timeout=_CHECK_INTERVAL_SECONDS):
                # Stop event was set
                break

        logger.debug("Orchestrator loop ended")
