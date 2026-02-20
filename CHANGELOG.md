# Changelog

All notable changes to IronLung 3 will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — Phase 6: The Soul (ADHD UX)
- **Dopamine Engine** (`gui/adhd/dopamine.py`) — Streak tracking with celebrations at 5/10/20/50, 7 achievements (first call, first demo, first close, power hour, queue cleared, perfect day, streak master), persistent state
- **Session Manager** (`gui/adhd/session.py`) — Time-blindness warnings at configurable intervals, energy levels (HIGH/MEDIUM/LOW by time of day), 5-deep undo stack, crash recovery with session state persistence
- **Focus Mode** (`gui/adhd/focus.py`) — Distraction-free card processing state, auto-trigger by streak, enter/exit callbacks for UI
- **Audio Feedback** (`gui/adhd/audio.py`) — 6 sound types (card done, email sent, demo set, deal closed, error, streak), per-sound mute, global mute, volume control, pluggable audio backend
- **Command Palette** (`gui/adhd/command_palette.py`) — Fuzzy search across tabs/prospects/actions/settings, recency boost, prefix/substring/fuzzy scoring, < 50ms search on 500 items
- **Glanceable Dashboard** (`gui/adhd/dashboard.py`) — Cards processed/total, calls, emails, demos, streak — all from DB activities, < 50ms refresh
- **Compassionate Messages** (`gui/adhd/compassion.py`) — Context-aware welcome messages, time-of-day encouragement, streak encouragement, break suggestions, queue-empty celebration, rescue intro — zero guilt words verified by test
- **Rescue Engine** (`ai/rescue.py`) — "Just do these 3 things" mode, priority: closing > post-demo > demo-scheduled > pre-demo > unengaged by score
- **Troubled Cards** (`engine/troubled_cards.py`) — Overdue (2+ days), stalled (14+ days no activity), suspect contact data — with deduplication
- **Intel Gaps** (`engine/intel_gaps.py`) — Missing domain, title, company size, intel nuggets — with summary counts
- **Feedback Capture** (`core/feedback.py`) — Bug/suggestion JSONL log with persistence
- **Setup Wizard** (`core/setup_wizard.py`) — First-run config (name, paths, sounds, Outlook) with persistence
- Updated `gui/tabs/troubled.py` and `gui/tabs/intel_gaps.py` to wire to service layer
- 163 new tests for Phase 6 features

### Added — Phases 1–5
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
