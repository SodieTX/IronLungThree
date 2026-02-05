"""Tests for background task management."""

import pytest

from src.core.tasks import TaskManager, run_in_background


class TestTaskManager:
    """Test TaskManager class."""

    @pytest.mark.skip(reason="Stub not implemented")
    def test_submit_task(self):
        """Can submit a task."""
        manager = TaskManager()
        result = []

        def task():
            result.append(1)

        manager.submit(task)
        manager.shutdown()
        assert result == [1]

    @pytest.mark.skip(reason="Stub not implemented")
    def test_shutdown_waits_for_tasks(self):
        """Shutdown waits for pending tasks."""
        pass


class TestRunInBackground:
    """Test run_in_background function."""

    @pytest.mark.skip(reason="Stub not implemented")
    def test_run_in_background_executes(self):
        """Task executes in background."""
        pass
