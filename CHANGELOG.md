# Changelog

All notable changes to IronLung 3 will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Complete project scaffolding with all 60+ source files
- Full documentation suite (Blueprint, Build Sequence, Schema Spec, ADRs)
- Layer documentation (LAYER-1 through LAYER-7)
- Pattern documentation (CONFIG, ERROR-HANDLING, LOGGING, TESTING)
- Core module implementations:
  - `src/core/exceptions.py` — Full exception hierarchy
  - `src/core/config.py` — Configuration with .env file support
  - `src/core/logging.py` — JSON + console structured logging
  - `src/db/models.py` — All enums, dataclasses, utility functions
  - `src/db/database.py` — Schema DDL with all 10 tables
- Test suite with 50 passing tests, 50 stub placeholders
- Email templates (8 Jinja2 templates for Phase 3)
- CI workflow for GitHub Actions
- Development tooling (black, isort, mypy, pytest)

### Infrastructure
- `pyproject.toml` with modern Python project configuration
- `requirements.txt` and `requirements-dev.txt`
- `.gitignore` with comprehensive exclusions
- `pytest.ini` configuration
- `py.typed` marker for PEP 561 compliance

## [0.1.0] - 2026-02-05

### Added
- Initial project structure
- Blueprint v3.2 — Architectural specification
- Build Sequence v2.2 — 78-step construction plan
- Schema Spec v3.3 — Complete database DDL

---

## Version History

- **0.1.0** — Project scaffolding complete, ready for Phase 1 coding
- Future versions will follow the phase completion milestones:
  - **0.2.0** — Phase 1 complete (The Slab)
  - **0.3.0** — Phase 2 complete (The Daily Grind)
  - **0.4.0** — Phase 3 complete (The Communicator)
  - **0.5.0** — Phase 4 complete (Anne)
  - **0.6.0** — Phase 5 complete (The Autonomy)
  - **0.7.0** — Phase 6 complete (The Soul)
  - **1.0.0** — Phase 7 complete (The Weapons) — Full release
