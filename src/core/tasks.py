"""Thread and task management for IronLung 3.

Provides utilities for running background tasks without blocking the GUI.

Usage:
    from src.core.tasks import run_in_background, TaskManager

    # Simple background execution
    run_in_background(some_long_function, callback=on_complete)

    # Managed task execution
    manager = TaskManager()
    manager.submit(task_name, function, *args, **kwargs)
"""

import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TaskResult:
    """Result of a background task.

    Attributes:
        task_name: Name of the task
        success: Whether task completed successfully
        result: Return value if successful
        error: Exception if failed
        started_at: When task started
        completed_at: When task finished
    """

    task_name: str
    success: bool
    result: Any = None
    error: Optional[Exception] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate task duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


def run_in_background(
    func: Callable[..., Any],
    args: tuple = (),
    kwargs: Optional[dict] = None,
    callback: Optional[Callable[[Any], None]] = None,
    error_callback: Optional[Callable[[Exception], None]] = None,
) -> threading.Thread:
    """Run a function in a background thread.

    Simple fire-and-forget background execution.

    Args:
        func: Function to execute
        args: Positional arguments
        kwargs: Keyword arguments
        callback: Function to call with result on success
        error_callback: Function to call with exception on failure

    Returns:
        The started thread
    """
    kwargs = kwargs or {}

    def wrapper():
        try:
            result = func(*args, **kwargs)
            if callback:
                callback(result)
        except Exception as e:
            logger.error(f"Background task failed: {e}", exc_info=True)
            if error_callback:
                error_callback(e)

    thread = threading.Thread(target=wrapper, daemon=True)
    thread.start()
    return thread


class TaskManager:
    """Manages background task execution.

    Provides a thread pool for running tasks with tracking and callbacks.

    Attributes:
        max_workers: Maximum concurrent tasks
    """

    def __init__(self, max_workers: int = 4):
        """Initialize task manager.

        Args:
            max_workers: Maximum concurrent tasks
        """
        self.max_workers = max_workers
        self._executor: Optional[ThreadPoolExecutor] = None
        self._tasks: dict[str, Future] = {}
        self._lock = threading.Lock()

    def _get_executor(self) -> ThreadPoolExecutor:
        """Get or create thread pool executor."""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
        return self._executor

    def submit(
        self,
        task_name: str,
        func: Callable[..., Any],
        *args,
        callback: Optional[Callable[[TaskResult], None]] = None,
        **kwargs,
    ) -> Future:
        """Submit a task for execution.

        Args:
            task_name: Name for tracking
            func: Function to execute
            *args: Positional arguments
            callback: Function to call with TaskResult when complete
            **kwargs: Keyword arguments

        Returns:
            Future representing the task
        """
        started_at = datetime.now()

        def wrapper():
            try:
                result = func(*args, **kwargs)
                return TaskResult(
                    task_name=task_name,
                    success=True,
                    result=result,
                    started_at=started_at,
                    completed_at=datetime.now(),
                )
            except Exception as e:
                logger.error(f"Task {task_name} failed: {e}", exc_info=True)
                return TaskResult(
                    task_name=task_name,
                    success=False,
                    error=e,
                    started_at=started_at,
                    completed_at=datetime.now(),
                )

        future = self._get_executor().submit(wrapper)

        with self._lock:
            self._tasks[task_name] = future

        if callback:
            future.add_done_callback(lambda f: callback(f.result()))

        return future

    def is_running(self, task_name: str) -> bool:
        """Check if a task is currently running.

        Args:
            task_name: Name of the task

        Returns:
            True if task is running
        """
        with self._lock:
            future = self._tasks.get(task_name)
            return future is not None and not future.done()

    def cancel(self, task_name: str) -> bool:
        """Attempt to cancel a task.

        Args:
            task_name: Name of the task

        Returns:
            True if task was cancelled
        """
        with self._lock:
            future = self._tasks.get(task_name)
            if future:
                return future.cancel()
        return False

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the task manager.

        Args:
            wait: Wait for pending tasks to complete
        """
        if self._executor:
            self._executor.shutdown(wait=wait)
            self._executor = None
        with self._lock:
            self._tasks.clear()
