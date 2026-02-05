# IRONLUNG 3: COMPACT GUIDE

**Quick Reference for Development**

This is your navigation hub. For full details, see Blueprint and Build Sequence files in this repo.

---

## What This Is

IronLung 3 is an ADHD-optimized sales pipeline management system. Jeff (the user) processes prospects in conversation with Anne (the AI assistant). The system breathes autonomously while Jeff sleeps.

**Core insight:** The ADHD brain goes dead clicking buttons in silence. It comes alive with a body double in the room. Anne IS that body double.

---

## The Six Things (Everything Serves These)

1. **The Rolodex** - SQLite database, local, holds everybody
2. **The Sorting** - Clear status for every contact
3. **The Grind Partner** - One card at a time, Anne-led conversation
4. **The Email Writer** - Drafts and sends through Outlook
5. **The Dialer** - Click-to-call through Bria softphone
6. **The Calendar Brain** - Right cadence, never too fast or slow

---

## The Seven Layers (Build Bottom-Up)

```
┌─────────────────────────────────────────────┐
│ LAYER 7: THE SOUL                          │
│ ADHD UX → Dopamine, Focus, Compassion      │
├─────────────────────────────────────────────┤
│ LAYER 6: THE HEARTBEAT                     │
│ Autonomous Ops → Nightly Cycle, Nurture    │
├─────────────────────────────────────────────┤
│ LAYER 5: THE BRAIN (ANNE)                  │
│ Conversational AI → Card presentation      │
├─────────────────────────────────────────────┤
│ LAYER 4: THE FACE                          │
│ GUI → Tabs, Dictation Bar, Cards          │
├─────────────────────────────────────────────┤
│ LAYER 3: THE ENGINE                        │
│ Business Logic → Populations, Cadences     │
├─────────────────────────────────────────────┤
│ LAYER 2: THE PIPES                         │
│ Integrations → Outlook, Bria, CSV Import   │
├─────────────────────────────────────────────┤
│ LAYER 1: THE SLAB                          │
│ Database, Models, Config, Logging          │
└─────────────────────────────────────────────┘
```

---

## Database Core (Layer 1)

**9 tables, SQLite, local file at `~/.ironlung/ironlung3.db`**

### Key Tables
- **companies** - Name, domain, loan types, size, state, timezone, notes
- **prospects** - Contact info, population, stage, follow-up date, score, custom fields
- **contact_methods** - Multiple emails/phones per prospect, verification status
- **activities** - Complete audit trail of every interaction
- **intel_nuggets** - Extracted facts for during-call cheat sheets
- **prospect_tags** - User-defined labels (filterable, bulk-applicable)
- **research_queue** - Broken prospects queued for autonomous research
- **import_sources** - Import batch tracking
- **schema_version** - For migrations

**See Blueprint Lines 219-241 for full DDL**

---

## Prospect Lifecycle

```
IMPORTED → ASSESSED → BROKEN (missing data)
                   ↓
              UNENGAGED (system-paced)
                   ↓
              ENGAGED (prospect-paced)
                   ↓
            DEMO SCHEDULED
                   ↓
            WARMING TRAY (post-demo)
                   ↓
              CLOSED WON

Side tracks from any state:
→ PARKED (date-specific, auto-reactivates)
→ DNC (permanent, absolute, sacrosanct)
→ LOST (may revisit after 12+ months)
```

**See Blueprint Lines 63-116 for full flow diagram**

---

## The Two Cadences (Most Important Logic)

### Unengaged: System-Paced
Prospect doesn't control timing. Jeff decides cadence.

| Attempt | Channel | Wait Before Next |
|---------|---------|------------------|
| 1       | Call    | 3-5 business days |
| 2       | Call    | 5-7 business days |
| 3       | Email   | 7-10 business days |
| 4       | Combo   | 10-14 business days |
| 5+      | Evaluate: park or mark dead |

### Engaged: Prospect-Paced
Prospect says "call me Wednesday" → follow-up IS Wednesday. That date is sacred.
- No orphans allowed (engaged must have follow-up date)
- Anne flags any engaged prospect without a date

**See Blueprint Lines 119-167 for full rules**

---

## DNC Protection (Hard Rule)

**DNC = Do Not Contact. Permanent. Absolute. No resurrection. Ever.**

- Import matching DNC email/phone/name → silently blocked
- Bulk operations skip DNC records (counted separately)
- DNC → anything transition = system error
- 24-hour grace period for reversals (after that, permanent)

**See Blueprint Lines 268-272 for full rules**

---

## Build Phases (78 Steps Total)

**Each phase = working tool you can use**

### Phase 1: THE SLAB + DATA IN (16 steps)
Database + Import + Backup + Basic GUI
**Milestone:** Import Jeff's CSV, view in Pipeline tab

### Phase 2: THE DAILY GRIND (13 steps)
Morning brief → Queue → Processing loop (keyboard)
**Milestone:** Process cards with correct cadence logic

### Phase 3: THE COMMUNICATOR (11 steps)
Outlook sends, Bria dials, Demo scheduling
**Milestone:** Send real email, dial real call

### Phase 4: ANNE (10 steps)
Conversational processing with AI
**Milestone:** Jeff talks, Anne executes

### Phase 5: THE AUTONOMY (9 steps)
Nightly cycle, research, nurture, monitoring
**Milestone:** System works while Jeff sleeps

### Phase 6: THE SOUL (10 steps)
ADHD-aware UX, dopamine, focus mode
**Milestone:** System understands Jeff's brain

### Phase 7: THE WEAPONS (9 steps)
Strategic AI, analytics, learning engine
**Milestone:** Anne becomes dangerous

**See Build Sequence for exact steps + tests**

---

## File Structure

```
ironlung3/
├── ironlung3.py              # Single entry point
├── src/
│   ├── core/                 # Config, logging, exceptions
│   ├── db/                   # Database, models, backup, intake
│   ├── integrations/         # Outlook, Bria, CSV, email import
│   ├── engine/               # Populations, cadence, scoring, nurture
│   ├── ai/                   # Anne, parser, copilot, insights
│   ├── autonomous/           # Nightly cycle, orchestrator, monitors
│   ├── gui/                  # App, tabs, cards, dictation bar
│   │   ├── tabs/            # Today, Pipeline, Calendar, Demos, etc.
│   │   ├── dialogs/         # Morning brief, import preview
│   │   └── adhd/            # Dopamine, focus, session management
│   └── content/             # Brief generation, summaries
├── templates/emails/         # Jinja2 email templates
├── data/
│   ├── backups/             # Timestamped DB backups
│   └── style_examples/      # Jeff's email voice samples
├── config/
│   ├── .env                 # API keys (gitignored)
│   └── settings.py          # Feature flags, cadence config
└── tests/                   # pytest suite (see Build Sequence)
```

**See Blueprint Lines 1032-1143 for detailed tree**

---

## Anne: The Conversational Interface

**Anne is the product. Everything else is plumbing.**

Anne's job:
- Present each card with context, history, and recommendation
- Discuss prospects (15-30 seconds per card)
- Challenge bad decisions ("Are you sure? He's showing buying signals.")
- Draft emails in Jeff's voice
- Take obsessive notes (notes ARE the memory)
- Extract intel nuggets for cheat sheets
- Execute after confirmation

**Anne never executes without Jeff's confirmation.**

**See Blueprint Lines 709-784 for Anne's full capabilities**

---

## Key Performance Targets

| Target | Threshold |
|--------|-----------|
| Database creation | < 1 second |
| Insert 500 prospects | < 2 seconds |
| Pipeline tab load (500 records) | < 1 second |
| Search results | < 200ms |
| Morning brief generation | < 2 seconds |
| Queue builder | < 500ms |
| Full test suite | < 10 seconds |
| App startup | < 3 seconds |

**See Build Sequence Lines 91-107 for verification methods**

---

## Engineering Standards

### Testing
- **pytest** for all non-GUI code
- In-memory SQLite for tests
- One test file per module
- GUI = manual smoke tests only

### Version Control
- One commit per verified step
- Never commit failing tests
- Tag each completed phase: `git tag phase-N-complete`
- No branches until Phase 4+

### Phase Handoff
1. Full test suite passes (zero failures)
2. Performance targets met
3. Error scenarios tested
4. Handoff doc written
5. Jeff tests with real data
6. Sign off or file issues
7. Git tag
8. Next phase spec written

**See Build Sequence Lines 17-152 for full standards**

---

## Where to Find Details

### Architecture Decisions
→ **Blueprint** sections: "WHAT THIS DOCUMENT IS" through "THE DESTINATION"

### Implementation Specs
→ **Blueprint** sections: Layer 1 through Layer 7 (lines 219-878)

### Build Order & Tests
→ **Build Sequence** - 78 steps with exact test cases

### Database Schema
→ **Blueprint** Lines 223-241 (full DDL with indexes)

### Prospect Lifecycle Rules
→ **Blueprint** Lines 359-388 (all valid transitions)

### Cadence Math
→ **Blueprint** Lines 389-396 (both systems)

### Error Handling
→ **Build Sequence** Lines 109-134 (failure scenarios)

### Tab Structure
→ **Blueprint** Lines 509-526 (what each tab does)

---

## Critical Design Decisions

### What's Honest (Not Aspirational)
- Autonomous research fixes 20-30% of broken records (not 50-60%)
- Confidence scoring = simple rules (not percentages)
- Learning engine = qualitative (reads notes, not statistics)
- Polling not webhooks (desktop apps can't receive push)
- Scoring weights = manual (auto-tuning needs 12+ months data)

### What's Gone (Never Build)
- Trello integration
- LinkedIn automation
- SMTP email verification (providers block it)
- Paid enrichment APIs
- Statistical ML (notes-based instead)
- Multiple entry points
- Dual implementations of anything

**See Blueprint Lines 1146-1180 for full list**

---

## Tech Stack

- **Language:** Python 3.11+
- **GUI:** tkinter (Windows desktop, proven)
- **Database:** SQLite (local, zero infrastructure)
- **AI:** Claude API (Anne + all conversational features)
- **Email:** Microsoft Graph API (OAuth2)
- **Phone:** Bria softphone (tel: URI)
- **Templates:** Jinja2
- **Testing:** pytest
- **Logging:** Structured JSON

---

## Quick Start (After Phase 1)

1. `python ironlung3.py` - Launches GUI
2. Import tab → Select CSV → Map columns → Analyze → Import
3. Pipeline tab → View all prospects
4. Settings tab → Backup now

## Quick Start (After Phase 2)

1. Launch → Morning brief appears
2. "Let's go" → Queue starts
3. Process cards → Change status, add notes, set follow-ups
4. Calendar tab → See follow-ups

## Quick Start (After Phase 4)

1. Launch → Read brief
2. "Let's go" → Anne presents first card
3. Discuss → Decide → Anne executes
4. Next card

---

## When Something Goes Wrong

### Build Issues
→ Check Build Sequence error scenarios (lines 109-134)
→ Run full test suite: `pytest`
→ Check last commit message for what was verified

### Runtime Issues
→ Check logs in `~/.ironlung/logs/`
→ All errors use custom exception hierarchy (Blueprint line 291-293)
→ DNC violations = their own exception class

### Performance Issues
→ Check performance targets (Build Sequence lines 91-107)
→ Profile with specific step's timing method
→ Never move forward with slow foundation

---

## The Prime Directive

**If a feature doesn't serve one of the Six Things, it doesn't belong.**

---

**Version:** 1.0  
**Date:** February 5, 2026  
**Parent Documents:** Blueprint v3.2, Build Sequence v2.2  
**Purpose:** Navigation hub for daily development work
