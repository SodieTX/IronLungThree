"""Windows Task Scheduler integration.

Installs tasks for:
    - Nightly Cycle: 2:00 AM daily
    - Orchestrator Boot: System startup
"""

import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

from src.core.logging import get_logger

logger = get_logger(__name__)

# Task definitions
_TASKS: dict[str, dict[str, Optional[str]]] = {
    "IronLung3_Nightly": {
        "description": "IronLung 3 nightly maintenance cycle",
        "command": f'"{sys.executable}" ironlung3.py --nightly',
        "schedule": "DAILY",
        "start_time": "02:00",
    },
    "IronLung3_Orchestrator": {
        "description": "IronLung 3 background orchestrator",
        "command": f'"{sys.executable}" ironlung3.py --orchestrator',
        "schedule": "ONSTART",
        "start_time": None,
    },
}


@dataclass
class TaskStatus:
    """Status of a scheduled task."""

    name: str
    enabled: bool
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    last_result: Optional[int] = None


def _is_windows() -> bool:
    """Check if running on Windows."""
    return os.name == "nt"


def install_tasks() -> bool:
    """Install Windows Task Scheduler tasks.

    Creates two scheduled tasks:
        - IronLung3_Nightly: runs at 2:00 AM daily
        - IronLung3_Orchestrator: runs on system startup

    On non-Windows platforms, logs a warning and returns False.

    Returns:
        True if tasks were installed successfully, False otherwise.
    """
    if not _is_windows():
        logger.warning(
            "Task Scheduler integration is only available on Windows. "
            "Skipping task installation on this platform."
        )
        return False

    success = True

    for task_name, task_config in _TASKS.items():
        try:
            # Build schtasks.exe command
            command = task_config["command"] or ""
            cmd: list[str] = [
                "schtasks.exe",
                "/Create",
                "/TN",
                task_name,
                "/TR",
                command,
                "/F",  # Force overwrite if exists
            ]

            if task_config["schedule"] == "DAILY" and task_config["start_time"] is not None:
                cmd.extend(["/SC", "DAILY", "/ST", task_config["start_time"]])
            elif task_config["schedule"] == "ONSTART":
                cmd.extend(["/SC", "ONSTART"])

            # Add description
            cmd.extend(["/RU", "SYSTEM"])

            logger.info(
                f"Installing scheduled task: {task_name}",
                extra={"context": {"task": task_name, "schedule": task_config["schedule"]}},
            )

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                logger.error(
                    f"Failed to install task {task_name}: {result.stderr}",
                    extra={"context": {"task": task_name, "returncode": result.returncode}},
                )
                success = False
            else:
                logger.info(
                    f"Task installed: {task_name}",
                    extra={"context": {"task": task_name}},
                )

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            logger.error(
                f"Error installing task {task_name}: {e}",
                extra={"context": {"task": task_name, "error": str(e)}},
            )
            success = False

    return success


def uninstall_tasks() -> bool:
    """Remove scheduled tasks from Windows Task Scheduler.

    On non-Windows platforms, logs a warning and returns False.

    Returns:
        True if tasks were removed successfully, False otherwise.
    """
    if not _is_windows():
        logger.warning(
            "Task Scheduler integration is only available on Windows. "
            "Skipping task removal on this platform."
        )
        return False

    success = True

    for task_name in _TASKS:
        try:
            cmd = [
                "schtasks.exe",
                "/Delete",
                "/TN",
                task_name,
                "/F",  # Force delete without confirmation
            ]

            logger.info(
                f"Removing scheduled task: {task_name}",
                extra={"context": {"task": task_name}},
            )

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                logger.warning(
                    f"Failed to remove task {task_name}: {result.stderr}",
                    extra={"context": {"task": task_name, "returncode": result.returncode}},
                )
                success = False
            else:
                logger.info(
                    f"Task removed: {task_name}",
                    extra={"context": {"task": task_name}},
                )

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            logger.error(
                f"Error removing task {task_name}: {e}",
                extra={"context": {"task": task_name, "error": str(e)}},
            )
            success = False

    return success


def check_tasks() -> dict[str, TaskStatus]:
    """Check status of scheduled tasks in Windows Task Scheduler.

    On non-Windows platforms, returns an empty dict.

    Returns:
        Dict mapping task name to TaskStatus.
    """
    if not _is_windows():
        logger.warning(
            "Task Scheduler integration is only available on Windows. "
            "Returning empty status on this platform."
        )
        return {}

    statuses: dict[str, TaskStatus] = {}

    for task_name in _TASKS:
        try:
            cmd = [
                "schtasks.exe",
                "/Query",
                "/TN",
                task_name,
                "/FO",
                "LIST",
                "/V",
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                # Task may not exist
                statuses[task_name] = TaskStatus(
                    name=task_name,
                    enabled=False,
                )
                continue

            # Parse schtasks output
            output = result.stdout
            enabled = True
            last_run = None
            next_run = None
            last_result = None

            for line in output.splitlines():
                line = line.strip()
                if line.startswith("Status:"):
                    status_val = line.split(":", 1)[1].strip()
                    enabled = status_val.lower() not in ("disabled",)
                elif line.startswith("Last Run Time:"):
                    last_run = line.split(":", 1)[1].strip()
                    if last_run == "N/A":
                        last_run = None
                elif line.startswith("Next Run Time:"):
                    next_run = line.split(":", 1)[1].strip()
                    if next_run == "N/A":
                        next_run = None
                elif line.startswith("Last Result:"):
                    try:
                        last_result = int(line.split(":", 1)[1].strip())
                    except ValueError:
                        last_result = None

            statuses[task_name] = TaskStatus(
                name=task_name,
                enabled=enabled,
                last_run=last_run,
                next_run=next_run,
                last_result=last_result,
            )

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            logger.error(
                f"Error checking task {task_name}: {e}",
                extra={"context": {"task": task_name, "error": str(e)}},
            )
            statuses[task_name] = TaskStatus(
                name=task_name,
                enabled=False,
            )

    return statuses
