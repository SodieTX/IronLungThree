# Layer 4: The Face

**GUI - What Jeff Sees and Touches**

Version: 1.0
Date: February 5, 2026
Parent: Blueprint v3.2

---

## Overview

One GUI. One entry point. Clean tabs. Dictation Bar at the bottom of every screen.

**Tech Stack:** Python tkinter (Windows desktop, proven)

**Entry Point:** `ironlung3.py` → initialize → launch GUI

**Components:**
- Main Application (`gui/app.py`)
- Theme (`gui/theme.py`)
- Dictation Bar (`gui/dictation_bar.py`)
- Prospect Cards (`gui/cards.py`)
- Keyboard Shortcuts (`gui/shortcuts.py`)
- Tabs (11 total)
- Dialogs (6 total)
- ADHD UX (7 components)

---

## Tab Structure

| Tab | Purpose | Serves |
|-----|---------|--------|
| **Today** | Morning brief + processing loop | Sorting, Grind |
| **Broken** | Records missing phone/email | Rolodex |
| **Pipeline** | Full database view | Rolodex, Sorting |
| **Calendar** | Day/week views, follow-ups | Calendar Brain |
| **Demos** | Invite creator, tracking | Email, Calendar |
| **Partnerships** | Non-prospect contacts | Rolodex |
| **Import** | File upload, mapping, preview | Rolodex |
| **Settings** | Config, backup, recovery | — |
| **Troubled** | Problem cards (added later) | — |
| **Intel Gaps** | Missing info audit (added later) | — |
| **Analytics** | Performance numbers (added later) | — |

---

## Main Application (`gui/app.py`)

### Window Structure

```
┌─────────────────────────────────────────────────────┐
│ IronLung 3                               [_][□][X] │
├─────────────────────────────────────────────────────┤
│ [Today] [Broken] [Pipeline] [Calendar] [Demos] ... │
├─────────────────────────────────────────────────────┤
│                                                     │
│                  Tab Content Area                   │
│                                                     │
├─────────────────────────────────────────────────────┤
│ [Dictation Bar                              ] [⏎]  │
├─────────────────────────────────────────────────────┤
│ 147 prospects │ Last backup: 2 hours ago │ Online  │
└─────────────────────────────────────────────────────┘
```

### Startup Sequence

1. Load config
2. Initialize logging
3. Connect database
4. Check/create backup
5. Launch main window
6. Show morning brief dialog (overlays Today tab)

---

## Dictation Bar (`gui/dictation_bar.py`)

### Purpose

Persistent text input at bottom of every tab. Universal input - there's no separate "add note" button or "change status" dropdown.

### Behavior

- Large, clear font
- Always visible, always ready
- Submit on Enter
- Windows dictation-ready (Jeff speaks, text appears)
- Response area appears above when Anne responds

### Offline Mode

When Anne unavailable:
- Manual mode activates
- Notes log directly without AI parsing
- Dropdown selectors appear for status changes
- Date picker appears for follow-ups

---

## Prospect Card (`gui/cards.py`)

### Glance View (Default)

```
┌─────────────────────────────────────────┐
│ John Smith, CEO                    [85] │
│ ABC Lending (Bridge, Fix & Flip)        │
│ ☎ (713) 555-1234                       │
│ Follow-up → he said call Wednesday      │
│ Last: 1/30 - Left VM, try again         │
│ [TX] [hot-referral]               [72%] │
└─────────────────────────────────────────┘
```

Elements:
- Name and title
- Company with loan types
- Phone (clickable → Bria)
- Why up today
- Last interaction
- Tags, state, confidence badge

### Call Mode

Activates when Jeff clicks dial or says "call him". Rearranged for phone conversation:

```
┌─────────────────────────────────────────┐
│     JOHN SMITH                          │
│     CEO, ABC Lending                    │
├─────────────────────────────────────────┤
│ Recent:                                 │
│ • 1/30: Left VM, said try again         │
│ • 1/23: No answer                       │
│ • 1/15: Intro email sent                │
├─────────────────────────────────────────┤
│ Intel:                                  │
│ • Fix and flip in Houston               │
│ • Evaluating three vendors              │
│ • Pain point: manual borrower intake    │
├─────────────────────────────────────────┤
│ [Dictation Bar                    ] [⏎] │
└─────────────────────────────────────────┘
```

### Deep Dive

Expandable - "show me more" or "what do we have on him":

- Full activity history
- All contact methods with verification
- All email correspondence inline
- Company details
- Research findings
- All notes in full
- Custom field values

---

## Today Tab (`gui/tabs/today.py`)

### Morning Brief → Queue Transition

1. Morning brief appears as dialog overlay
2. Jeff reads in 60 seconds
3. "Ready? Let's go." or Enter
4. Dialog closes, first card presented immediately

### Processing Loop

1. Anne presents card with context
2. Jeff and Anne discuss (15-30 seconds)
3. Decision made
4. If call: switch to Call Mode
5. Post-disposition: Anne shows confirmation
6. Jeff confirms
7. Anne executes (logs, notes, updates)
8. Next card

### Queue Ordering

1. Engaged follow-ups first (closing → post-demo → demo-scheduled → pre-demo)
2. Then unengaged by score
3. Timezone-ordered within groups (East Coast first in morning)
4. Overdue items surface first with days-overdue flag

---

## Pipeline Tab (`gui/tabs/pipeline.py`)

### Features

- Full database table view
- Filter by population, state, score range, tags
- Search by name, company
- Sort by any column
- Multi-select (checkboxes, Shift+click)
- Bulk actions: Move, Park, Tag, Follow-up
- CSV export of current view

### Bulk Action Bar

Appears when records selected:
```
[5 selected] [Move to ▼] [Park in ▼] [Tag ▼] [Set Follow-up] [Export]
```

DNC records in selection are skipped with count reported.

---

## Calendar Tab (`gui/tabs/calendar.py`)

### Day View

Hour-by-hour with follow-ups and demos in time slots, respecting timezone.

### Week View

Seven columns showing shape of the week. Clusters and gaps visible.

### Monthly Buckets

Parked contacts grouped by month: "March: 8 prospects activating on the 3rd."

---

## Broken Tab (`gui/tabs/broken.py`)

### Three Sections

**Needs Confirmation:**
System found something. Confirm or reject.

**In Progress:**
System still searching. Hands-off.

**Manual Research Needed:**
System struck out. Pre-built links:
- Company website
- Google search
- NMLS lookup

### Header Count

"24 Broken → 3 ready to confirm, 8 in progress, 13 need you"

---

## Keyboard Shortcuts (`gui/shortcuts.py`)

| Key | Action |
|-----|--------|
| Enter | Confirm / submit |
| Escape | Cancel / close |
| Ctrl+Z | Undo last action |
| Tab | Skip to next card |
| Ctrl+D | Defer current card |
| Ctrl+F | Quick lookup (focus search) |
| Ctrl+M | Demo invite creator |
| Ctrl+E | Send one-off email |
| Ctrl+K | Command palette |

---

## Dialogs

### Morning Brief (`gui/dialogs/morning_brief.py`)

60-second readable memo with pipeline stats, today's work, overnight changes.

### Edit Prospect (`gui/dialogs/edit_prospect.py`)

Form for manual prospect editing.

### Import Preview (`gui/dialogs/import_preview.py`)

Shows counts, DNC blocks in red, confirm/cancel.

### Quick Action (`gui/dialogs/quick_action.py`)

Fast status change or note without full card view.

### Closed Won (`gui/dialogs/closed_won.py`)

Deal value, close date, notes capture.

### Email Recall (`gui/dialogs/email_recall.py`)

"Oh Shit" button for wrong emails.

---

## ADHD UX Components (`gui/adhd/`)

See Layer 7: The Soul for full specifications.

---

## Build Phases

- **Phase 1**: App shell, Pipeline tab, Import tab, Settings (Steps 1.14-1.16)
- **Phase 2**: Today tab, Calendar, Broken, processing loop (Steps 2.5-2.13)
- **Phase 3**: Demos tab, Call Mode, inline email (Steps 3.5-3.11)
- **Phase 4**: Dictation Bar with Anne integration (Step 4.1)
- **Phase 6**: ADHD components (Steps 6.1-6.10)

---

## Performance Targets

| Operation | Target |
|-----------|--------|
| App startup to window | < 3 seconds |
| Pipeline tab load (500 records) | < 1 second |
| Search results | < 200ms |
| Tab switch | < 100ms |

---

**See also:**
- `LAYER-5-BRAIN.md` - Anne integration
- `LAYER-7-SOUL.md` - ADHD UX details
- `../build/PHASE-1-SLAB.md` - Initial GUI build steps
