# IronLung 3 Architecture Overview

## System Purpose

IronLung 3 is an ADHD-optimized sales pipeline management system. It acts as a "cognitive prosthetic" for Jeff, managing follow-ups, communications, and prospect data while accommodating the realities of ADHD.

**Core Philosophy:** The system breathes while Jeff sleeps. It maintains context, handles the boring parts, and presents work in a way that works with ADHD, not against it.

## The Seven Layers

IronLung 3 is built in seven architectural layers, each with clear responsibilities and dependencies.

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 7: Soul                                               │
│ ADHD UX, dopamine engine, compassionate messages            │
├─────────────────────────────────────────────────────────────┤
│ Layer 6: Heartbeat                                          │
│ Autonomous operations, nightly cycle, reply monitoring      │
├─────────────────────────────────────────────────────────────┤
│ Layer 5: Brain                                              │
│ Anne (AI assistant), parsing, disposition, copilot          │
├─────────────────────────────────────────────────────────────┤
│ Layer 4: Face                                               │
│ GUI (tkinter), tabs, cards, dictation bar                   │
├─────────────────────────────────────────────────────────────┤
│ Layer 3: Engine                                             │
│ Business logic, populations, cadence, scoring, research     │
├─────────────────────────────────────────────────────────────┤
│ Layer 2: Pipes                                              │
│ External integrations (Outlook, Bria, CSV, ActiveCampaign)  │
├─────────────────────────────────────────────────────────────┤
│ Layer 1: Slab                                               │
│ Core infrastructure (logging, config, exceptions, database) │
└─────────────────────────────────────────────────────────────┘
```

### Layer Dependencies

- Each layer depends only on layers below it
- Never upward dependencies
- Layer 1 (Slab) has no internal dependencies

## Key Design Decisions

### SQLite for Storage
Single-file database. Simple. Backups are just file copies. No server to manage.

### tkinter for GUI
Ships with Python. No Node.js, no Electron, no web stack. One GUI.

### Polling over Webhooks
No public endpoints needed. No server. Works anywhere.

### Notes as Memory
Notes field is sacred. Contains qualitative context that scoring cannot capture.

### Dual Cadence System
- **System-paced:** Unengaged prospects follow automatic escalating intervals
- **Prospect-paced:** Engaged prospects follow explicit follow-up dates

## Data Flow

### Import Flow
```
File (CSV/XLSX) → Parser → Intake Funnel → Database
                              ↓
                      Dedup + DNC Check
```

### Daily Processing Flow
```
Morning Brief → Card Queue → Process Card → Disposition
                    ↓              ↓
                Anne presents   Actions recorded
                    ↓              ↓
                 Response     Activities logged
```

### Nightly Cycle
```
2 AM → Backup → Pull AC → Dedup → Assess → Research → Score → Bucket → Nurture → Brief
```

## Population System

Prospects move through discrete populations:

```
        ┌─────────┐
        │ BROKEN  │ (missing contact data)
        └────┬────┘
             ↓
        ┌─────────┐
  ┌────→│UNENGAGED│←───┐
  │     └────┬────┘    │
  │          ↓         │
  │     ┌─────────┐    │
  │     │ ENGAGED │────┤
  │     └────┬────┘    │
  │          ↓         │
  │  ┌───────┴───────┐ │
  │  ↓               ↓ │
┌────────┐      ┌──────────┐
│CUSTOMER│      │   LOST   │
└────────┘      └──────────┘

Special populations:
- DNC: Do Not Contact (permanent, sacrosanct)
- DEAD: Company/person gone
- PARKED: Future follow-up by month
```

## DNC Protection

**DNC is absolute and permanent.**

- Records can only enter DNC, never leave
- DNC records are never merged or updated
- DNCViolationError is never swallowed
- All DNC checks happen before any operation

## Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| GUI | tkinter |
| Database | SQLite |
| AI | Claude API (Anthropic) |
| Email | Microsoft Graph API |
| Softphone | Bria (URI scheme) |
| Templates | Jinja2 |
| Testing | pytest |

## File Organization

```
IronLungThree/
├── ironlung3.py          # Entry point
├── src/
│   ├── core/             # Layer 1: Infrastructure
│   ├── db/               # Layer 1: Database
│   ├── integrations/     # Layer 2: External services
│   ├── engine/           # Layer 3: Business logic
│   ├── gui/              # Layer 4: User interface
│   ├── ai/               # Layer 5: AI features
│   ├── autonomous/       # Layer 6: Background processes
│   └── content/          # Content generation
├── tests/                # Mirrors src/ structure
├── docs/
│   ├── layers/           # Layer specifications
│   ├── build/            # Phase specifications
│   ├── adr/              # Architecture decisions
│   └── patterns/         # Engineering patterns
└── data/                 # Runtime data (gitignored)
```

## Build Philosophy

IronLung 3 is built in phases, each producing a usable tool:

1. **Phase 1:** Data foundation (import, backup, basic CRUD)
2. **Phase 2:** Daily workflow (cards, queues, morning brief)
3. **Phase 3:** Communications (Outlook, Bria, email)
4. **Phase 4:** Anne (AI assistant, dictation, parsing)
5. **Phase 5:** Autonomous (nightly cycle, monitoring)
6. **Phase 6:** ADHD UX (dopamine, focus mode, compassion)
7. **Phase 7:** Advanced features (learning, analytics)

**"Good enough to deploy" after each phase.**

## See Also

- `docs/layers/` - Detailed layer specifications
- `docs/build/` - Phase build specifications
- `docs/adr/` - Architecture decision records
- `COMPACT-GUIDE.md` - Quick reference
