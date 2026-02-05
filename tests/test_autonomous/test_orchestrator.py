"""Tests for orchestrator (src/autonomous/orchestrator.py).

Covers:
    - Orchestrator.is_running: default state and after start/stop
    - Orchestrator.register_task: task registration
    - Orchestrator.start / stop: lifecycle management
    - Registered tasks actually execute within the loop
"""

import threading
import time
from datetime import timedelta

import pytest

from src.autonomous.orchestrator import Orchestrator

# ===========================================================================
# is_running
# ===========================================================================


class TestIsRunning:
    """Default running state."""

    def test_default_is_false(self):
        """Orchestrator is not running by default."""
        orch = Orchestrator()
        assert orch.is_running() is False

    def test_true_after_start(self):
        """is_running returns True after start()."""
        orch = Orchestrator()
        try:
            orch.start()
            assert orch.is_running() is True
        finally:
            orch.stop()

    def test_false_after_stop(self):
        """is_running returns False after stop()."""
        orch = Orchestrator()
        orch.start()
        orch.stop()
        assert orch.is_running() is False


# ===========================================================================
# register_task
# ===========================================================================


class TestRegisterTask:
    """Task registration."""

    def test_task_appears_in_tasks(self):
        """After register_task, the task name is in _tasks."""
        orch = Orchestrator()
        orch.register_task("test_task", lambda: None, timedelta(minutes=5))

        assert "test_task" in orch._tasks

    def test_task_stores_func_and_interval(self):
        """Registered task stores function and interval."""
        func = lambda: None
        interval = timedelta(seconds=30)
        orch = Orchestrator()
        orch.register_task("my_task", func, interval)

        task_info = orch._tasks["my_task"]
        assert task_info["func"] is func
        assert task_info["interval"] == interval
        assert task_info["last_run"] is None

    def test_multiple_tasks_registered(self):
        """Multiple tasks can be registered."""
        orch = Orchestrator()
        orch.register_task("task_a", lambda: None, timedelta(minutes=1))
        orch.register_task("task_b", lambda: None, timedelta(minutes=2))
        orch.register_task("task_c", lambda: None, timedelta(hours=1))

        assert len(orch._tasks) == 3
        assert "task_a" in orch._tasks
        assert "task_b" in orch._tasks
        assert "task_c" in orch._tasks

    def test_overwrite_existing_task(self):
        """Registering with the same name overwrites the previous one."""
        orch = Orchestrator()
        orch.register_task("dup", lambda: "first", timedelta(seconds=10))
        orch.register_task("dup", lambda: "second", timedelta(seconds=20))

        assert len(orch._tasks) == 1
        assert orch._tasks["dup"]["interval"] == timedelta(seconds=20)


# ===========================================================================
# start / stop lifecycle
# ===========================================================================


class TestStartStop:
    """Start and stop the orchestrator daemon thread."""

    def test_start_creates_daemon_thread(self):
        """start() creates a daemon thread."""
        orch = Orchestrator()
        try:
            orch.start()
            assert orch._thread is not None
            assert orch._thread.is_alive()
            assert orch._thread.daemon is True
        finally:
            orch.stop()

    def test_stop_joins_thread(self):
        """stop() causes the thread to terminate."""
        orch = Orchestrator()
        orch.start()
        orch.stop()
        # Thread should no longer be alive
        assert orch._thread is None

    def test_double_start_is_safe(self):
        """Calling start() twice does not create two threads."""
        orch = Orchestrator()
        try:
            orch.start()
            first_thread = orch._thread
            orch.start()  # Should be no-op
            assert orch._thread is first_thread
        finally:
            orch.stop()

    def test_double_stop_is_safe(self):
        """Calling stop() twice does not raise."""
        orch = Orchestrator()
        orch.start()
        orch.stop()
        orch.stop()  # Should be no-op
        assert orch.is_running() is False

    def test_stop_without_start_is_safe(self):
        """Calling stop() without start() does not raise."""
        orch = Orchestrator()
        orch.stop()
        assert orch.is_running() is False


# ===========================================================================
# Task execution
# ===========================================================================


class TestTaskExecution:
    """Verify that registered tasks actually run."""

    def test_task_runs_at_least_once(self):
        """A task with a short interval runs at least once during start/stop cycle."""
        counter = {"value": 0}

        def increment():
            counter["value"] += 1

        orch = Orchestrator()
        orch.register_task("counter_task", increment, timedelta(seconds=0))

        try:
            orch.start()
            # Give the background thread time to run the loop once
            time.sleep(1.5)
        finally:
            orch.stop()

        assert counter["value"] >= 1

    def test_failing_task_does_not_crash_orchestrator(self):
        """A task that raises an exception does not crash the orchestrator."""
        call_log = []

        def good_task():
            call_log.append("good")

        def bad_task():
            call_log.append("bad")
            raise RuntimeError("Task failure!")

        orch = Orchestrator()
        orch.register_task("bad", bad_task, timedelta(seconds=0))
        orch.register_task("good", good_task, timedelta(seconds=0))

        try:
            orch.start()
            time.sleep(1.5)
        finally:
            orch.stop()

        # Both tasks should have been attempted
        assert "bad" in call_log
        assert "good" in call_log
        # Orchestrator should still have stopped cleanly
        assert orch.is_running() is False

    def test_task_last_run_updated(self):
        """After a task runs, its last_run field is updated."""
        orch = Orchestrator()
        orch.register_task("tracked", lambda: None, timedelta(seconds=0))

        assert orch._tasks["tracked"]["last_run"] is None

        try:
            orch.start()
            time.sleep(1.5)
        finally:
            orch.stop()

        assert orch._tasks["tracked"]["last_run"] is not None
