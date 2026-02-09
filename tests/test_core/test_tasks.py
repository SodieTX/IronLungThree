"""Tests for background task management."""

import pytest

from src.core.tasks import TaskManager, run_in_background


class TestTaskManager:
    """Test TaskManager class."""

    def test_submit_task(self):
        """Can submit a task."""
        manager = TaskManager()
        result = []

        def task():
            result.append(1)

        future = manager.submit("test_task", task)
        future.result()  # Wait for completion
        manager.shutdown()
        assert result == [1]

    def test_shutdown_waits_for_tasks(self):
        """Shutdown waits for pending tasks."""
        manager = TaskManager()
        result = []

        def task():
            result.append(1)

        manager.submit("test_task", task)
        manager.shutdown(wait=True)
        assert result == [1]


class TestRunInBackground:
    """Test run_in_background function."""

    def test_run_in_background_executes(self):
        """Task executes in background."""
        result = []

        def task():
            result.append(1)

        thread = run_in_background(task)
        thread.join(timeout=5)
        assert result == [1]
