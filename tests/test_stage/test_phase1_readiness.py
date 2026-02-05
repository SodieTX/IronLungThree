"""Phase 1 readiness gate tests."""

from pathlib import Path

import pytest

from src.db.database import Database

pytestmark = pytest.mark.phase1_ready


REQUIRED_DOCS = [
    "README.md",
    "COMPACT-GUIDE.md",
    "docs/BLUEPRINT.md",
    "docs/BUILD-SEQUENCE.md",
    "docs/PHASE1-CHECKLIST.md",
    "docs/build/PHASE-1-BUILD-SPEC.md",
    "IRONLUNG3-BLUEPRINT-v3.md",
    "IRONLUNG3-PHASE1-BUILD-SPEC.md",
]


def test_required_docs_exist() -> None:
    """All key docs referenced for phase readiness should exist."""
    missing = [path for path in REQUIRED_DOCS if not Path(path).exists()]
    assert not missing, f"Missing required docs: {missing}"


def test_pyproject_declares_python_311_plus() -> None:
    """Project metadata should match documented Python support."""
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.11"' in pyproject


def test_pytest_registers_phase1_ready_marker() -> None:
    """Marker registration keeps strict marker mode green."""
    pytest_ini = Path("pytest.ini").read_text(encoding="utf-8")
    assert "phase1_ready" in pytest_ini


def test_database_initializes_in_memory() -> None:
    """Minimum phase capability: schema initializes in memory."""
    db = Database(":memory:")
    db.initialize()
    tables = (
        db._get_connection().execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    )
    db.close()

    assert len(tables) > 0
