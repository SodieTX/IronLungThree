# Changelog

All notable changes to IronLung 3 will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.7.0] - 2026-02-21

### Added — Phase 7: The Weapons (Strategic AI)
- **AI Copilot** (`ai/copilot.py`) — Full pipeline strategy mode, record manipulation via natural language, analytical question routing
- **Contact Analyzer** (`ai/contact_analyzer.py`) — Engagement pattern analysis, stalling detection, multi-contact coordination
- **Prospect Insights** (`ai/insights.py`) — Per-prospect strategic suggestions, competitive vulnerability analysis, confidence scoring
- **Learning Engine** (`engine/learning.py`) — Qualitative note-based pattern learning from wins/losses, competitor tracking
- **Intervention Engine** (`engine/intervention.py`) — Pipeline decay detection: overdue follow-ups, stale leads, unworked cards, data quality
- **Proactive Card Interrogation** (`ai/proactive_interrogation.py`) — Anne reviews cards during brief generation: orphans, stale leads, overdue, data quality; wired into morning brief
- **Analytics Tab** (`gui/tabs/analytics.py`) — Monthly metrics display, CSV export, revenue/commission/close rate tracking
- **Data Export** (`engine/export.py`) — Prospect CSV export, monthly summary generation and export
- **Dead Lead Resurrection** (`engine/resurrection.py`) — 12+ month lost lead audit with smart rationale per loss reason
- **Partnership Promotion** (`gui/tabs/partnerships.py`) — Full tab with promote-to-prospect workflow via population transitions
- **Nexys Contract Generator** (`engine/contract_gen.py`) — Template-based contract rendering (Jinja2, no AI), editable templates, wired into Closed Won dialog with preview and clipboard copy
- **Cost Tracking** (`utils/cost_tracking.py`) — Centralized Claude API usage tracking per module, JSONL persistence, daily/monthly/total summaries, model-aware pricing
- Wired cost tracking into `ClaudeClientMixin` — all AI modules (Anne, Copilot, EmailGenerator) now automatically track token usage and estimated costs
- Contract template at `templates/contracts/nexys_standard.txt.j2` — edit to customize contract format
- 118 new tests for Phase 7 features (39 new in this PR, 79 existing)

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
- **0.7.0** — Phases 1–6 complete, Phase 7 in progress
- **1.0.0** — Phase 7 complete (The Weapons) — Full release
