"""Auto-update support for IronLung 3.

Checks for new versions via git and applies updates by pulling
from the remote repository and reinstalling dependencies.

The update flow:
    1. `check_for_update()` — git fetch + compare local vs remote version
    2. `apply_update()` — git pull + pip install -r requirements.txt
    3. User restarts the application to load the new code
"""

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.core.logging import get_logger

logger = get_logger(__name__)

# Repository root — assumes this file lives at src/core/updater.py
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# The branch we track for updates
_UPDATE_BRANCH = "main"


@dataclass
class UpdateCheckResult:
    """Result of a version check."""

    current_version: str
    remote_version: Optional[str]
    update_available: bool
    commits_behind: int
    error: Optional[str] = None
    commit_summary: str = ""


@dataclass
class UpdateApplyResult:
    """Result of applying an update."""

    success: bool
    old_version: str
    new_version: str
    message: str
    needs_restart: bool = False


def _run_git(*args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    """Run a git command in the repo root."""
    cmd = ["git", "-C", str(_REPO_ROOT)] + list(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _get_local_version() -> str:
    """Read the current version from ironlung3.py."""
    entry_point = _REPO_ROOT / "ironlung3.py"
    if not entry_point.exists():
        return "unknown"
    text = entry_point.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
    return match.group(1) if match else "unknown"


def _get_remote_version() -> Optional[str]:
    """Read the version from the remote branch's pyproject.toml."""
    result = _run_git("show", f"origin/{_UPDATE_BRANCH}:pyproject.toml")
    if result.returncode != 0:
        return None
    match = re.search(r'version\s*=\s*"([^"]+)"', result.stdout)
    return match.group(1) if match else None


def _version_tuple(version: str) -> tuple[int, ...]:
    """Convert a version string like '0.7.0' to a comparable tuple."""
    parts = []
    for part in version.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def check_for_update() -> UpdateCheckResult:
    """Check whether a newer version is available on the remote.

    Performs a `git fetch` then compares the local HEAD with the
    remote tracking branch to determine if updates exist.

    Returns:
        UpdateCheckResult with version info and update availability.
    """
    current = _get_local_version()

    # Fetch latest from remote
    fetch_result = _run_git("fetch", "origin", _UPDATE_BRANCH, timeout=30)
    if fetch_result.returncode != 0:
        error_msg = fetch_result.stderr.strip() or "git fetch failed"
        logger.warning(f"Update check failed: {error_msg}")
        return UpdateCheckResult(
            current_version=current,
            remote_version=None,
            update_available=False,
            commits_behind=0,
            error=f"Could not reach update server: {error_msg}",
        )

    # Count commits behind
    rev_list = _run_git("rev-list", "--count", f"HEAD..origin/{_UPDATE_BRANCH}")
    commits_behind = 0
    if rev_list.returncode == 0:
        try:
            commits_behind = int(rev_list.stdout.strip())
        except ValueError:
            pass

    # Get remote version
    remote = _get_remote_version()

    # Determine if update is available
    update_available = False
    if remote and current != "unknown":
        update_available = _version_tuple(remote) > _version_tuple(current)
    elif commits_behind > 0:
        update_available = True

    # Get a short summary of what changed
    commit_summary = ""
    if commits_behind > 0:
        log_result = _run_git(
            "log",
            "--oneline",
            f"HEAD..origin/{_UPDATE_BRANCH}",
            "--max-count=10",
        )
        if log_result.returncode == 0:
            commit_summary = log_result.stdout.strip()

    logger.info(
        "Update check complete",
        extra={
            "context": {
                "current": current,
                "remote": remote,
                "behind": commits_behind,
                "available": update_available,
            }
        },
    )

    return UpdateCheckResult(
        current_version=current,
        remote_version=remote,
        update_available=update_available,
        commits_behind=commits_behind,
        commit_summary=commit_summary,
    )


def apply_update() -> UpdateApplyResult:
    """Pull the latest version and update dependencies.

    This runs:
        1. git pull origin main
        2. pip install -r requirements.txt (if the file changed)

    Returns:
        UpdateApplyResult indicating success/failure and whether a restart
        is needed.
    """
    old_version = _get_local_version()

    # Check for uncommitted changes that would block the pull
    status_result = _run_git("status", "--porcelain")
    if status_result.returncode == 0 and status_result.stdout.strip():
        # Stash local changes so pull doesn't fail
        stash_result = _run_git("stash", "push", "-m", "ironlung-auto-update")
        if stash_result.returncode != 0:
            return UpdateApplyResult(
                success=False,
                old_version=old_version,
                new_version=old_version,
                message="You have uncommitted changes that could not be stashed. "
                "Please commit or discard them before updating.",
            )
        logger.info("Stashed local changes before update")

    # Pull latest
    pull_result = _run_git("pull", "origin", _UPDATE_BRANCH, timeout=60)
    if pull_result.returncode != 0:
        error_msg = pull_result.stderr.strip() or "git pull failed"
        logger.error(f"Update pull failed: {error_msg}")
        return UpdateApplyResult(
            success=False,
            old_version=old_version,
            new_version=old_version,
            message=f"Update failed: {error_msg}",
        )

    # Update dependencies
    req_file = _REPO_ROOT / "requirements.txt"
    if req_file.exists():
        pip_result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(req_file), "--quiet"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(_REPO_ROOT),
        )
        if pip_result.returncode != 0:
            logger.warning(f"Dependency update had issues: {pip_result.stderr.strip()}")

    new_version = _get_local_version()

    logger.info(
        "Update applied",
        extra={
            "context": {
                "old_version": old_version,
                "new_version": new_version,
            }
        },
    )

    return UpdateApplyResult(
        success=True,
        old_version=old_version,
        new_version=new_version,
        message=f"Updated from v{old_version} to v{new_version}. Please restart IronLung 3.",
        needs_restart=True,
    )
