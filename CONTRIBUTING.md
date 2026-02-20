# Contributing to IronLung 3

## Development Setup

### Prerequisites

- Python 3.11 or higher
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/jsoderstrom/ironlung3.git
cd ironlung3

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Verify installation
python ironlung3.py --version
```

## Development Workflow

### Before Making Changes

1. **Run the test suite** to ensure everything passes:
   ```bash
   python -m pytest tests/ -v
   ```

2. **Create a new branch** if working on a feature:
   ```bash
   git checkout -b feature/my-feature
   ```

### Code Style

This project uses automated code formatting:

- **Black** for code formatting (line length: 100)
- **isort** for import sorting (Black profile)
- **mypy** for type checking

Run all formatters before committing:

```bash
python -m black src/ tests/ ironlung3.py
python -m isort src/ tests/ ironlung3.py
python -m mypy src/ --ignore-missing-imports
```

### Testing

- Every module has a corresponding test file in `tests/`
- Tests use in-memory SQLite (`:memory:`) — never touch real data
- Tests marked with `@pytest.mark.skip("Stub not implemented")` are placeholders for future phases

Run tests:

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_db/test_models.py -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=term-missing
```

### Commit Guidelines

Follow the Build Sequence discipline:

1. **One commit per verified step** — not per session, not per feature
2. **Never commit failing tests** — main branch always works
3. **Descriptive commit messages**:
   ```
   Step 1.6: Company CRUD with timezone auto-assignment — 6 tests pass
   ```

### Git Tags

Each completed phase gets a tag:

```bash
git tag phase-1-complete
git push origin phase-1-complete
```

## Project Structure

```
ironlung3/
├── ironlung3.py          # Single entry point
├── src/
│   ├── core/             # Config, logging, exceptions
│   ├── db/               # Database, models, backup
│   ├── integrations/     # External services (Outlook, Bria, etc.)
│   ├── engine/           # Business logic (populations, cadence, scoring)
│   ├── ai/               # Anne AI (parser, disposition, copilot)
│   ├── autonomous/       # Background tasks (nightly, orchestrator)
│   ├── gui/              # Tkinter GUI (tabs, dialogs, ADHD features)
│   └── content/          # Generated content (briefs, summaries)
├── tests/                # Test suite (mirrors src/ structure)
├── docs/                 # Documentation
├── data/                 # Runtime data (backups, style examples)
└── templates/            # Email templates (Jinja2)
```

## Phase-by-Phase Development

IronLung 3 is built in phases, where each phase produces a usable tool:

1. **Phase 1: The Slab** — Database, import, basic GUI
2. **Phase 2: The Daily Grind** — Morning brief, processing loop, calendar
3. **Phase 3: The Communicator** — Outlook, Bria, email templates
4. **Phase 4: Anne** — Conversational AI, dictation bar
5. **Phase 5: The Autonomy** — Nightly cycle, orchestrator
6. **Phase 6: The Soul** — ADHD UX features
7. **Phase 7: The Weapons** — Strategic AI, analytics

See `docs/BUILD-SEQUENCE.md` for details.

## Questions?

Check the documentation in `docs/` or open an issue.
