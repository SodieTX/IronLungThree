# IronLung 3

**ADHD-Optimized Sales Pipeline Management**

> The ADHD brain goes dead in a silent room clicking buttons.
> It comes alive when there's another intelligence in the room
> saying "okay, what about this one?"
> That's not a feature. That's the entire reason this software exists.

---

## What Is This?

IronLung 3 is a sales pipeline management system designed for ADHD brains. You sit down, read a 60-second morning brief, and start processing prospects in conversation with Anne (your AI assistant). She presents each card with context and an opinion. You discuss for 15-30 seconds. She executes. Next card.

The system breathes autonomously while you sleep — backing up data, researching broken records, monitoring email replies, and preparing tomorrow's brief.

## Core Concept

**The Six Things:**

1. **The Rolodex** — SQLite database, local, holds everybody
2. **The Sorting** — Clear status for every contact
3. **The Grind Partner** — One card at a time, Anne-led conversation
4. **The Email Writer** — Drafts and sends through Outlook
5. **The Dialer** — Click-to-call through Bria softphone
6. **The Calendar Brain** — Right cadence, never too fast or slow

If a feature doesn't serve one of these six things, it doesn't belong.

## Quick Start

### Prerequisites

- Python 3.11+
- Windows 10/11
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/jsoderstrom/ironlung3.git
cd ironlung3

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# For development
pip install -r requirements-dev.txt
```

### Configuration

```bash
# Copy example environment file
copy .env.example .env

# Edit .env with your settings (optional for Phase 1)
notepad .env
```

### Running

```bash
# Launch the application
python ironlung3.py
```

## Build Phases

IronLung 3 is built in 7 phases. Each phase produces a working tool.

| Phase | Name | What You Get |
|-------|------|--------------|
| 1 | The Slab | Database + Import + Pipeline view |
| 2 | The Daily Grind | Morning brief + card processing |
| 3 | The Communicator | Email sending + phone dialing |
| 4 | Anne | Conversational AI assistant |
| 5 | The Autonomy | Nightly cycle + background ops |
| 6 | The Soul | ADHD-specific UX enhancements |
| 7 | The Weapons | Strategic AI + analytics |

**Current Status:** Phases 1–6 complete. Phase 7 in progress (~80%).

## Documentation

- `Blueprint` — Full architectural specification
- `Build Sequence` — Construction order with tests
- `COMPACT-GUIDE.md` — Quick reference for development
- `docs/SCHEMA-SPEC.md` — Database schema
- `docs/layers/` — Layer-by-layer specifications
- `docs/build/` — Phase build specifications
- `docs/adr/` — Architecture decision records
- `docs/patterns/` — Engineering patterns

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test file
pytest tests/test_db/test_database.py

# Run tests matching pattern
pytest -k "test_normalize"

# Phase 1 stage gate
pytest -m phase1_ready
```

## Project Structure

```
ironlung3/
├── ironlung3.py          # Entry point
├── src/
│   ├── core/             # Config, logging, exceptions
│   ├── db/               # Database, models, backup
│   ├── integrations/     # External services
│   ├── engine/           # Business logic
│   ├── ai/               # Anne + AI features
│   ├── autonomous/       # Background operations
│   ├── gui/              # User interface
│   └── content/          # Generated content
├── tests/                # Test suite
├── templates/            # Email templates
├── config/               # Configuration
├── data/                 # Local data storage
└── docs/                 # Documentation
```

## Tech Stack

- **Language:** Python 3.11+
- **GUI:** tkinter
- **Database:** SQLite
- **AI:** Claude API (Anthropic)
- **Email:** Microsoft Graph API
- **Phone:** Bria softphone

## License

MIT License - see `LICENSE` file.

## Author

Jeff Soderstrom, Nexys LLC

---

*"The Iron Lung breathes."*
