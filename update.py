#!/usr/bin/env python3
"""IronLung 3 — Self-updater.

Double-click this script (or run `python update.py`) to pull the latest
code from GitHub onto your desktop.  Safe to run at any time — your
database and credentials (~/.ironlung/) are never touched.

What it does:
  1. Fixes the git remote if it was overwritten by a sandbox proxy.
  2. Switches to the main branch.
  3. Pulls the latest code from GitHub.
  4. Installs any new pip dependencies.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
GITHUB_URL = "https://github.com/SodieTX/IronLungThree.git"


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    """Run a command and return the result."""
    return subprocess.run(
        cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=120, **kwargs
    )


def main() -> int:
    print("=" * 48)
    print("  IronLung 3 — Pulling Latest Code")
    print("=" * 48)
    print()

    # 1. Fix remote if it points at a sandbox proxy
    result = run(["git", "remote", "get-url", "origin"])
    current_url = result.stdout.strip()
    print(f"Current remote: {current_url}")

    if "127.0.0.1" in current_url or "local_proxy" in current_url:
        print("Detected sandbox proxy — fixing remote...")
        run(["git", "remote", "set-url", "origin", GITHUB_URL])
        print(f"Remote set to {GITHUB_URL}")
    elif "github.com" not in current_url:
        print("Remote doesn't point to GitHub — fixing...")
        run(["git", "remote", "set-url", "origin", GITHUB_URL])
        print(f"Remote set to {GITHUB_URL}")
    else:
        print("Remote OK.")
    print()

    # 2. Switch to main
    print("Switching to main branch...")
    checkout = run(["git", "checkout", "main"])
    if checkout.returncode != 0:
        # Maybe the branch is called 'master' locally
        checkout = run(["git", "checkout", "master"])
        if checkout.returncode != 0:
            print(f"ERROR: Could not switch to main branch.")
            print(f"  {checkout.stderr.strip()}")
            print("  You may have uncommitted changes. Try: git stash")
            return 1
    print()

    # 3. Pull latest
    print("Pulling latest from GitHub...")
    pull = run(["git", "pull", "origin", "main"])
    if pull.returncode != 0:
        print("Fast pull failed, trying fetch + reset...")
        run(["git", "fetch", "origin", "main"])
        reset = run(["git", "reset", "--hard", "origin/main"])
        if reset.returncode != 0:
            print(f"ERROR: Could not update code.")
            print(f"  {reset.stderr.strip()}")
            return 1
    print(pull.stdout.strip() if pull.stdout.strip() else "Up to date.")
    print()

    # 4. Install dependencies
    print("Checking dependencies...")
    pip = run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"])
    if pip.returncode == 0:
        print("Dependencies OK.")
    else:
        print("Note: pip had issues — you may need to run it manually:")
        print(f"  pip install -r requirements.txt")
    print()

    print("=" * 48)
    print("  Update complete! You can now run the app:")
    print("    python ironlung3.py")
    print("=" * 48)
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except KeyboardInterrupt:
        print("\nCancelled.")
        code = 1
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        code = 1

    if sys.platform == "win32":
        input("\nPress Enter to close...")
    sys.exit(code)
