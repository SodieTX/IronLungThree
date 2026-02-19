# IRONLUNG 3: BUILD SEQUENCE

**The Construction Order**

---

## HOW THIS DOCUMENT WORKS

This is the build sequence for IronLung 3, broken into steps where each one produces something you can run, test, and verify before touching the next.

**Parent document:** `docs/BLUEPRINT.md` is the architectural source of truth. This document tells you the order to build it in and how to prove each piece works.

**Each phase gets its own build spec.** This document is the overview — the map of the whole journey. Before construction begins on any phase, a detailed Phase Build Specification is written with exact function signatures, exact DDL statements, exact test cases. The Phase 1 Build Spec (`docs/build/PHASE-1-BUILD-SPEC.md`) is the template for how detailed those documents are.

---

## ENGINEERING STANDARDS

These apply to every step in every phase. They are not optional. They are not aspirational. They are structural requirements, and the build is not considered complete without them.

### Testing Framework

**pytest** is the test runner. Every module ships with its test file. The test suite is the immune system — it catches regressions before they become architecture problems.

```
tests/
├── conftest.py              # Shared fixtures (in-memory DB, test config, sample data)
├── test_core/
│   ├── test_exceptions.py
│   ├── test_logging.py
│   └── test_config.py
├── test_db/
│   ├── test_database.py     # Schema, CRUD, queries
│   ├── test_backup.py
│   └── test_intake.py       # Dedup, DNC protection
├── test_integrations/
│   └── test_csv_importer.py
├── test_engine/             # Phase 2+
├── test_ai/                 # Phase 4+
├── test_autonomous/         # Phase 5+
└── test_gui/                # Smoke tests only — GUI testing is manual
```

**Rules:**

- Every non-GUI module has a corresponding test file.
- Every test file runs independently (`pytest tests/test_db/test_database.py` works alone).
- `conftest.py` provides shared fixtures: in-memory database, test config with temp directories, sample prospect/company data factories.
- Tests use in-memory SQLite (`:memory:`) — never touch the real database.
- The full suite runs in under 10 seconds. If it gets slower, something is wrong.
- **Before starting any new step, run the full test suite.** If anything is red, fix it first. Never build on a broken foundation.

**What we test vs. what we don't:**

| Test | Don't Test |
|---|---|
| Database CRUD operations | tkinter widget rendering |
| Dedup logic and DNC protection | Visual layout and styling |
| Population transitions | Keyboard shortcut bindings |
| Cadence calculations | Color values |
| CSV parsing and mapping | Font sizes |
| Data normalization | Window dimensions |
| Backup create/restore | Dialog appearance |
| Email template rendering | Button labels |
| AI parser output | Sound effects |

GUI gets manual smoke tests. Logic gets automated tests. The line is: if it touches data, it's tested automatically. If it only touches pixels, it's tested manually.

### Version Control

**Git.** Initialize the repository before writing a single line of code.

**Rules:**

- **One commit per verified step.** Step 1.1 passes its tests → commit with message "Step 1.1: Project skeleton + exceptions — all tests pass." Not one commit per session. Not one commit per phase. One commit per verified step.
- **Never commit code with failing tests.** The main branch always works. This is the rule that protects you at 2 AM when something breaks and you need to roll back.
- **Commit messages are descriptive.** Not "wip" or "stuff." The message should tell a future reader what this step accomplished and that it was verified. Example: `"Step 1.7: Prospect CRUD — insert, get, update, population query, follow-up query — 8 tests pass"`
- **Tag each completed phase.** `git tag phase-1-complete` after the milestone test passes. This is the rollback point if Phase 2 development breaks something fundamental.
- **No branches in Phase 1-3.** Single developer, linear build. Branches add complexity with no benefit when you're the only person committing. Revisit if that changes.
- **`.gitignore` from day one:**
  ```
  __pycache__/
  *.pyc
  .env
  *.db
  data/backups/
  ~/.ironlung/
  .pytest_cache/
  ```

### Performance Targets

Every target has a specific step where it gets verified. If the target isn't met, you stop and fix it before proceeding.

| Target | Verified At | Method |
|---|---|---|
| Database creation < 1 second | Step 1.5 | Time `create_tables()` |
| Insert 500 prospects < 2 seconds | Step 1.7 | Bulk insert in test |
| Pipeline tab loads 500 records < 1 second | Step 1.14 | Seed 500 records, time `refresh()` |
| Search returns results < 200ms | Step 2.12 | Seed 500 records, time search query |
| Queue builder (20 prospects) < 500ms | Step 2.4 | Seed 20 across populations, time build |
| Full test suite < 10 seconds | Every step | `time pytest` |
| App startup to window visible < 3 seconds | Step 1.14 | Time `ironlung3.py` launch |
| Morning brief generation < 2 seconds | Step 2.7 | Seed 200 records, time generation |
| CSV import (500 records) preview < 5 seconds | Step 1.13 | Parse + dedup analysis timed |

If a target fails: profile, fix, re-verify, commit. Do not move forward with a slow foundation — it gets slower with every layer on top.

### Error Recovery Verification

The happy path is not enough. Each step that handles external input or system resources has specific failure tests.

| Failure Scenario | Verified At | Expected Behavior |
|---|---|---|
| Database file locked by another process | Step 1.5 | Clear error message, no crash |
| Database file on read-only filesystem | Step 1.5 | Error dialog at startup, clean exit |
| CSV file with wrong encoding (not UTF-8) | Step 1.12 | Auto-detect latin-1, then cp1252, then error message |
| CSV with missing columns | Step 1.12 | Mapping UI shows unmapped columns, disables Analyze |
| CSV with zero data rows | Step 1.12 | "File contains no data rows" message |
| CSV with 50,000 rows | Step 1.12 | Processes without memory error (stream, don't load all) |
| XLSX without openpyxl installed | Step 1.12 | "Install openpyxl" message, CSV still works |
| Import with ALL records matching DNC | Step 1.13 | Preview shows all blocked, Import button disabled |
| Backup directory doesn't exist | Step 1.11 | Creates it. If can't create, logs warning, continues |
| Backup to full disk | Step 1.11 | Logs error, shows warning in status bar, app continues |
| Cloud sync directory missing (OneDrive not installed) | Step 1.11 | Silently skips cloud sync, logs info |
| Restore from corrupted backup file | Step 1.11 | Error message, original DB untouched |
| Bulk operation with mixed valid/DNC IDs | Step 1.14 | DNC skipped, valid processed, count reported |
| Network timeout during Outlook auth | Step 3.1 | Retry with backoff, then graceful fallback |
| Bria not installed | Step 3.3 | Phone numbers copy to clipboard instead |
| Claude API rate limit | Step 4.3 | Queue request, retry after delay, show "thinking..." |
| Claude API down entirely | Step 4.10 | Manual mode activates, all local features work |
| Nightly cycle interrupted mid-run | Step 5.8 | Picks up where it left off on next run |

Each failure scenario becomes an automated test where possible, a manual smoke test where not.

### Phase Handoff Process

Every phase ends the same way:

1. **Full test suite passes.** Zero failures, zero skips.
2. **Performance targets met.** All targets for this phase verified.
3. **Error scenarios tested.** Each failure scenario for this phase confirmed.
4. **Handoff document written.** One page:
   - What's working and how to use it
   - Known limitations (things that don't work yet — by design, because they're in a later phase)
   - How to run the test suite
   - What to test manually (the things automated tests don't cover)
5. **Jeff runs through it.** Uses the actual tool with his actual data.
6. **Jeff signs off or files issues.** Issues go in a `PHASE_N_ISSUES.md` file. All issues resolved before the next phase begins.
7. **Git tag.** `git tag phase-N-complete`
8. **Next phase build spec written.** Not before. The Phase 2 spec is informed by what was learned building Phase 1. This is intentional — you don't spec Phase 2 before you've built Phase 1, because Phase 1 always teaches you something.

---

## PHASE 1: THE SLAB + DATA IN

**Goal:** Database with contacts in it. Import works. Backup works. Basic GUI shows data.

**Detailed spec:** `docs/build/PHASE-1-BUILD-SPEC.md`

**Prerequisites:** Python 3.11+, pip, git. Nothing else.

### Step 1.1 — Project skeleton + exceptions

Create directory structure, `ironlung3.py` entry point (prints "IronLung 3 starting..." and exits), `requirements.txt` (openpyxl + pytest), `conftest.py` with placeholder fixtures, `core/exceptions.py` with full hierarchy.

Initialize git repo. First commit.

**Tests:** Import every exception class. Instantiate each. Verify inheritance chain.
**Commit:** "Step 1.1: Project skeleton + exceptions — tests pass"

### Step 1.2 — Logging

`core/logging.py`. Structured JSON logger with rotating file handler. Console output at INFO, file at DEBUG. Context fields via `extra={"context": {...}}`.

**Tests:** Log at every level. Verify JSON format in file. Verify rotation config. Verify log directory creation.
**Commit:** "Step 1.2: Structured JSON logging — tests pass"

### Step 1.3 — Configuration

`core/config.py`. Environment variable loading with defaults. `.env` file parser (no third-party library — simple `KEY=VALUE` line parser). Path setup (`~/.ironlung/`). `validate_config()` checks paths exist/are writable.

**Tests:** Load with no `.env` (defaults work). Load with `.env` (overrides work). Validate writable path. Validate non-writable path raises ConfigurationError.
**Error test:** `.env` file with malformed lines (no `=`, blank lines, comments) — parser handles gracefully.
**Commit:** "Step 1.3: Configuration with env loading — tests pass"

### Step 1.4 — Data models + enumerations

`db/models.py`. All enums (Population, EngagementStage, ActivityType, ActivityOutcome, LostReason, ContactMethodType, AttemptType, ResearchStatus, IntelCategory). All dataclasses (Company, Prospect, ContactMethod, Activity, ImportSource, ResearchTask, IntelNugget). `normalize_company_name()`. `STATE_TO_TIMEZONE` lookup. `timezone_from_state()`. `assess_completeness()`.

**Tests:**
- Enum values are strings (for SQLite storage).
- Every dataclass instantiates with defaults.
- `normalize_company_name("ABC Lending, LLC")` → `"abc lending"`
- `normalize_company_name("First National Holdings, Inc.")` → `"first national holdings"`
- `normalize_company_name("XYZ Mortgage Corp.")` → `"xyz mortgage"` (industry terms preserved)
- `timezone_from_state("TX")` → `"central"`
- `timezone_from_state(None)` → `"central"` (default)
- `timezone_from_state("")` → `"central"` (default)
- `assess_completeness` with email + phone → `"unengaged"`
- `assess_completeness` with email only → `"broken"`
- `assess_completeness` with phone only → `"broken"`
- `assess_completeness` with neither → `"broken"`

**Commit:** "Step 1.4: Data models, enums, normalization, timezone lookup — tests pass"

### Step 1.5 — Database schema creation

`db/database.py` — connection management, `initialize()` creates all tables and indexes from blueprint DDL. WAL mode. Foreign keys ON.

**Tests:**
- Create database, verify all 9 tables exist.
- Verify WAL mode enabled.
- Verify foreign keys enabled.
- Verify all indexes exist.
- Verify schema_version = 1.
- **Error test:** Database on read-only path raises DatabaseError.
- **Error test:** Database file locked by another connection — clear error.
- **Performance test:** `create_tables()` completes in < 1 second.

**Commit:** "Step 1.5: Database schema creation — 7 tests pass, <1s creation"

### Step 1.6 — Company CRUD

Add to `database.py`: `create_company()`, `get_company()`, `get_company_by_normalized_name()`, `update_company()`, `search_companies()`. Auto-normalize name on insert. Auto-assign timezone from state.

**Tests:**
- Insert company with state=TX, verify timezone=central.
- Insert company without state, verify timezone=central (default).
- Find by normalized name (case insensitive, suffix stripped).
- Search by partial name (LIKE query).
- Update company, verify updated_at changes.
- **Duplicate test:** Two companies with same normalized name found by `get_company_by_normalized_name`.

**Commit:** "Step 1.6: Company CRUD with timezone auto-assignment — tests pass"

### Step 1.7 — Prospect CRUD

`create_prospect()`, `get_prospect()`, `get_prospect_full()`, `update_prospect()`, `get_prospects()` with all filter parameters (population, company_id, state, score range, search query, sort, limit/offset).

**Tests:**
- Insert prospect linked to company, get it back.
- Filter by population returns correct subset.
- Filter by state returns correct subset.
- Score range filter works.
- Search query matches first_name, last_name, company name.
- Sort by score DESC (default), sort by name ASC.
- Pagination: limit=10, offset=10 returns second page.
- `get_prospect_full` returns prospect + company + empty lists for methods/activities.
- **Performance test:** Insert 500 prospects. `get_prospects(limit=100)` < 200ms. `get_prospects(search_query="smith")` < 200ms.

**Commit:** "Step 1.7: Prospect CRUD with filtering/pagination — tests pass, 500-record queries <200ms"

### Step 1.8 — Contact methods CRUD

`create_contact_method()`, `get_contact_methods()`, `update_contact_method()`. Methods to find prospects by email and phone for dedup.

**Tests:**
- Add email and phone to prospect, get them back.
- `get_contact_methods` returns primary first.
- Find prospect by exact email match (case insensitive).
- Find prospect by phone (digits-only normalization).
- **DNC test:** `is_dnc(email="dnc@test.com")` returns True when that email belongs to a DNC prospect.

**Commit:** "Step 1.8: Contact methods CRUD with dedup queries — tests pass"

### Step 1.9 — Activity logging

`create_activity()`, `get_activities()` (most recent first).

**Tests:**
- Log a call, status change, email. Get back in reverse chronological order.
- Activity with population_before and population_after stored correctly.
- `get_prospect_full` now includes activities.

**Commit:** "Step 1.9: Activity logging — tests pass"

### Step 1.10 — Remaining tables + bulk operations

CRUD for `data_freshness`, `import_sources`, `research_queue`, `intel_nuggets`. Bulk operations: `bulk_update_population()`, `bulk_set_follow_up()`, `bulk_park()`.

**Tests:**
- Round-trip insert/read for each remaining table.
- `bulk_update_population`: updates 5 prospects, logs activity for each.
- `bulk_park`: sets population=parked + parked_month.
- **DNC test:** Bulk operation with mixed valid/DNC IDs — DNC records skipped, valid processed, correct count returned.
- `get_population_counts()` returns correct numbers.

**Run full test suite.** All steps 1.1–1.10 still pass.

**Commit:** "Step 1.10: Remaining tables + bulk operations + DNC bulk protection — full suite passes"

### Step 1.11 — Backup system

`db/backup.py`. Create timestamped backup using SQLite backup API. Cloud sync copy. Retention cleanup. Restore with safety backup of current DB first.

**Tests:**
- Create backup, verify file exists and is valid SQLite.
- Backup filename format matches `ironlung3_YYYYMMDD_HHMMSS_label.db`.
- List backups returns newest first.
- Cleanup removes files older than retention, keeps newer ones.
- Restore works: insert data → backup → delete data → restore → data is back.
- Restore creates pre-restore safety backup.
- **Error test:** Restore from non-existent file raises DatabaseError.
- **Error test:** Restore from corrupt file raises DatabaseError, original DB untouched.
- **Error test:** Cloud sync dir missing — returns False, logs info, doesn't crash.

**Commit:** "Step 1.11: Backup system with restore and error handling — tests pass"

### Step 1.12 — CSV importer (parser only)

`integrations/csv_importer.py`. Read CSV/XLSX. Column mapping. Presets for PhoneBurner and AAPL formats. Auto-detect. Output: `list[ImportRecord]` (not yet written to DB).

**Tests:**
- Parse test CSV with PhoneBurner columns.
- Parse test XLSX.
- Auto-detect PhoneBurner preset from headers.
- Full name split: "John Smith" → first="John", last="Smith".
- Full name split: "Mary Jane Watson" → first="Mary", last="Jane Watson".
- Phone normalization: "(713) 555-1234" → digits only.
- Email normalization: "JOHN@ABC.COM" → lowercase.
- Empty rows skipped.
- Whitespace stripped from all fields.
- **Error test:** Non-existent file raises ImportError_.
- **Error test:** File with wrong encoding falls back to latin-1.
- **Error test:** CSV with zero data rows returns empty list with message.
- **Error test:** XLSX without openpyxl gives clear install message.
- **Performance test:** Parse 500-row CSV in < 2 seconds.

**Commit:** "Step 1.12: CSV/XLSX parser with presets and error handling — tests pass"

### Step 1.13 — Intake funnel

`db/intake.py`. Three-pass dedup (exact email → fuzzy company+name → phone). DNC protection hard block. Completeness assessment. Preview generation. Commit with activity logging.

**Tests:**
- **DNC protection (5 tests):**
  - Import record matching DNC email → blocked.
  - Import record matching DNC phone → blocked.
  - Import record with fuzzy name match to DNC → blocked.
  - DNC check runs BEFORE dedup (record never reaches merge logic).
  - Import where ALL records match DNC → preview shows all blocked, nothing to commit.
- **Dedup pass 1 (3 tests):**
  - Same email → merge (fills blanks on existing).
  - Merge does NOT overwrite existing non-blank fields.
  - Case-insensitive email match.
- **Dedup pass 2 (3 tests):**
  - "John Smith" at "ABC Lending LLC" matches "Jon Smith" at "ABC Lending" (>85% similarity) → duplicate.
  - "John Smith" does NOT match "Jane Doe" at same company (<85%).
  - Different company, same name → not a match (new record).
- **Dedup pass 3 (2 tests):**
  - Same phone, different person → needs review.
  - Phone match to DNC → blocked (not needs_review).
- **Completeness (2 tests):**
  - Record with name + email + phone → unengaged.
  - Record missing phone → broken + research_queue entry created.
- **Integration (3 tests):**
  - Preview does NOT modify database.
  - Commit creates prospects, contact methods, activities, import source record.
  - Import source record has correct counts.
- **Performance test:** Analyze 500 records against 500-record database in < 5 seconds.

**Run full test suite.** All steps 1.1–1.13 still pass.

**Commit:** "Step 1.13: Intake funnel with 3-pass dedup + DNC protection — 18 tests pass"

### Step 1.14 — GUI shell + Pipeline tab

`gui/theme.py` — all visual constants.
`gui/cards.py` — prospect card widget (glance view).
`gui/tabs/pipeline.py` — table with filter, search, sort, multi-select, bulk actions, CSV export.
`gui/app.py` — main window, tab bar, status bar.
`ironlung3.py` — full launch sequence (config → logging → database → backup check → GUI).

**Manual smoke tests (not automated):**
- App launches without error.
- Pipeline tab shows all prospects.
- Filter by population: shows only that population.
- Search by name: real-time filtering.
- Sort by score: click column header toggles direction.
- Multi-select: checkboxes work, shift+click range select works.
- Bulk move: select 5, move to Parked-June, confirm dialog, records update.
- Bulk move with DNC in selection: DNC skipped, message shown.
- CSV export: exports visible records, file opens in Excel correctly.
- Status bar: shows total count and backup time.
- Window close: creates backup, exits cleanly.

**Performance checks:**
- Seed 500 records. Pipeline tab loads in < 1 second.
- App startup to window visible < 3 seconds.

**Commit:** "Step 1.14: GUI shell + Pipeline tab — manual smoke tests pass, performance targets met"

### Step 1.15 — Import tab

`gui/tabs/import_tab.py` — file browser (not drag-and-drop — tkinter drag-and-drop requires unreliable third-party libraries), column mapping UI, preset detection, sample data preview, dedup preview with DNC blocks in red, confirm/cancel, import history.

**Manual smoke tests:**
- Click Browse, select CSV, columns appear in mapping dropdowns.
- PhoneBurner CSV auto-detects preset.
- Unknown CSV format: mapping dropdowns default to "(unmapped)".
- Sample data preview shows first 5 rows.
- Click Analyze: preview appears with correct counts.
- DNC blocks shown in red with expandable detail.
- Click Import: records appear in Pipeline tab.
- Import history shows the completed import with counts.
- **Error test:** Select a corrupt file — error message, no crash.
- **Error test:** Select an empty CSV — "no data rows" message.

**Run full test suite.** All automated tests still pass.

**Commit:** "Step 1.15: Import tab with column mapping and DNC preview — smoke tests pass"

### Step 1.16 — Settings tab (minimal)

`gui/tabs/settings.py` — manual backup button, backup list, restore button, config display (read-only).

**Manual smoke tests:**
- Click "Backup Now" — backup created, appears in list.
- Click restore on a backup — confirm dialog, restore completes, data matches.

**Commit:** "Step 1.16: Settings tab with backup/restore — smoke tests pass"

### Phase 1 Milestone Test

Against **Jeff's real data**, not test fixtures:

1. Launch app. Window appears in < 3 seconds.
2. Import Jeff's PhoneBurner CSV (300+ records). Preview shows correct counts.
3. Any DNC records in existing DB are protected — blocked in preview.
4. Import completes. Records visible in Pipeline tab.
5. Filter by "broken" — shows records missing phone or email.
6. Filter by "unengaged" — shows complete records.
7. Search for a known name — appears in < 200ms.
8. Multi-select 10 records, park in March. Confirm dialog. Records move.
9. Export filtered view as CSV. Open in Excel. Columns correct.
10. Close app. Reopen. Data persists. Backup was created on close.
11. Full automated test suite passes.

**Handoff document written.** Jeff runs through items 1-10 manually. Issues filed or signed off.

**Git tag:** `git tag phase-1-complete`

---

## PHASE 2: THE DAILY GRIND

**Goal:** Jeff sits down, reads the brief, hits go, and processes cards with correct cadence logic.

**Detailed build spec:** Written after Phase 1 handoff, informed by anything learned during Phase 1 construction.

### Step 2.1 — Population manager

`engine/populations.py`. All valid transitions from blueprint. Transition logging (activity record). Invalid transition rejection. DNC → anything throws.

**Tests:** Walk prospect through full lifecycle (both axes): imported → unengaged → engaged → demo_scheduled → warming_tray → closed_won. Confirm each population transition and stage transition logged independently. Confirm DNC → anything raises error.

### Step 2.2 — Scoring algorithm

`engine/scoring.py`. 0-100 composite with manual weights. Company fit, contact quality, engagement signals, timing, source quality. Data confidence score.

**Tests:** Score a fully-filled prospect vs. sparse one. Verify differentiated. Verify 0-100 bounds.

### Step 2.3 — Cadence engine

`engine/cadence.py`. Unengaged: configurable intervals by attempt number, next-contact-date calculation. Engaged: date stored directly, orphan detection (engaged with no follow-up date).

**Tests:** Simulate 5 unengaged attempts, verify wait intervals. Set engaged follow-up, verify exact date. Create engaged prospect with no follow-up, verify orphan flag. **Attempt counting:** verify personal vs. automated attempts tracked separately.

### Step 2.4 — Queue builder

Assembles today's work queue: engaged first (closing → post-demo → demo-scheduled → pre-demo), then unengaged by score, timezone-ordered within each group (Eastern first in morning).

**Tests:** Seed 20 prospects across populations and timezones. Verify queue order matches blueprint.
**Performance test:** Queue build < 500ms.

### Step 2.5 — Prospect card (glance + call mode + deep dive)

`gui/cards.py` expanded. Glance: name, title, company, phone (copies to clipboard in Phase 2), why-up-today, last interaction, scores, custom fields. Call mode: large name/company, last 3 interactions, intel nuggets. Deep dive: full history, all contact methods, company context, all notes.

**Manual test:** Render cards in all three modes for a seeded prospect.

### Step 2.6 — Today tab + processing loop (keyboard only)

`gui/tabs/today.py`. Queue loads. Cards display one at a time. Manual disposition: dropdown for population change, date picker for follow-up, text field for notes. "Next" advances queue. Skip, defer.

**Tests:** Process 5 cards — change status, add notes, set follow-ups. Verify activities logged, populations updated, dates set.

### Step 2.7 — Morning brief generation

`content/morning_brief.py`. Counts by population, today's engaged follow-ups (sorted by stage), overdue items, unengaged queue count, overnight changes.

**Tests:** Generate brief against seeded data, verify numbers match.
**Performance test:** Generation < 2 seconds on 200 records.

### Step 2.8 — Morning brief dialog + queue transition

`gui/dialogs/morning_brief.py`. Brief shows on launch. "Ready? Let's go." closes dialog, Today tab underneath, first card presented immediately. "Today's Brief" button to re-read.

**Manual test:** Launch app → read brief → click start → first card appears.

### Step 2.9 — Calendar tab

`gui/tabs/calendar.py`. Day view (hour-by-hour), week view (7 columns). Follow-ups in time slots respecting timezone. Monthly bucket visualization.

**Manual test:** Seed follow-ups across days. Verify correct placement.

### Step 2.10 — Broken tab

`gui/tabs/broken.py`. Three sections: needs confirmation (confirm/reject), in progress, manual research needed (pre-built links: company website, Google search, NMLS). Tab header count.

**Manual test:** Seed broken records. Verify research links work. Confirm one, verify it graduates to unengaged.

### Step 2.11 — End-of-day summary

`content/eod_summary.py`. Today's activity stats, pipeline movement, tomorrow preview.

**Tests:** Process cards, generate EOD, verify numbers.

### Step 2.12 — Quick lookup

Search bar: fuzzy match on prospect name and company. Sub-second results.

**Performance test:** 500 records, search for partial name < 200ms.

### Step 2.13 — Keyboard shortcuts + company context panel

All shortcuts from blueprint wired. Company context panel on cards ("2 other contacts at ABC Lending").

**Manual test:** Each shortcut triggers its action. Seed 3 contacts at one company, confirm panel shows.

### Phase 2 Milestone Test

1. Launch app. Morning brief appears with correct counts.
2. Click "Let's go." First card appears — highest priority engaged follow-up.
3. Process 10 cards: change statuses, add notes, set follow-ups.
4. Cadence math is correct: unengaged card shows "Attempt #3 — next contact in 9 business days."
5. Engaged card with no follow-up: shows orphan warning.
6. Calendar shows follow-ups in correct day/time slots.
7. Broken tab shows research links. Confirm a record — graduates to unengaged.
8. Quick lookup: phone rings, search name, full context on screen in < 1 second.
9. EOD summary: numbers match what was done.
10. Full test suite passes.

**Handoff → Jeff runs through it → sign off or issues → tag `phase-2-complete`**
**Phase 3 build spec written.**

---

## PHASE 3: THE COMMUNICATOR

**Goal:** Emails send. Phone dials. Demos get scheduled. Data exports.

**Build spec:** Written after Phase 2 handoff.

### Step 3.1 — Outlook auth + send

OAuth2 flow, token refresh, send email (plain text + HTML).
**Test:** Send a real email.
**Error test:** Auth failure → clear error message, app continues without Outlook.

### Step 3.2 — Outlook read + calendar

Inbox polling. Calendar CRUD. Teams link generation.
**Test:** Read inbox. Create event with Teams link.

### Step 3.3 — Bria dialer

`tel:` URI launch. Offline fallback (copy to clipboard).
**Test:** Click phone → Bria dials. Disconnect internet → copies to clipboard.
**Error test:** Bria not installed → copies to clipboard with info message.

### Step 3.4 — Email templates

Jinja2 templates: intro, follow-up, demo confirmation, nurture (3-part), breakup, demo invite. Auto-populated.
**Tests:** Render each template with test data. Verify prospect data injected correctly.

### Step 3.5 — Demo invite + Demos tab

Invite creator: duration, Teams link, template with prospect data. Preview. Send. Upcoming demos. Post-demo tracking.
**Test:** Create invite, send, verify calendar event + email.

### Step 3.6 — AI email generator

Claude API + prospect context + Jeff's instruction → draft.
**Test:** Generate intro email. Verify it's not generic robot-speak.
**Error test:** API timeout → retry with backoff → fallback message.

### Step 3.7 — One-off email from cards + inline history

Send email action on cards. Email history displayed on deep dive.
**Test:** Send from card, verify appears in card history.

### Step 3.8 — Demo prep generator

Auto-generated from prospect data + notes.
**Test:** Generate prep for prospect with history. Verify relevant details.

### Step 3.9 — Call Mode view

Card rearranges for phone: large name/company, last 3 interactions, intel nuggets.
**Test:** Enter call mode on card with history. Verify cheat sheet.

### Step 3.10 — Data export + Closed Won flow

CSV from Pipeline (current filter). Monthly summary report. Closed Won: deal value, close date, notes, commission calc.
**Tests:** Export CSV. Generate monthly summary. Record closed won deal. Verify commission math.

### Step 3.11 — Email recall

Pull back a sent email.
**Test:** Send, immediately recall.

### Phase 3 Milestone Test

Jeff sends a real email from a card. Dials through Bria. Creates a demo invite that appears in Outlook. Sees email history on cards. Has a cheat sheet during calls. Exports data. Records a closed deal.

**Handoff → sign off → tag `phase-3-complete` → Phase 4 spec written.**

---

## PHASE 4: ANNE

**Goal:** Conversational processing. Jeff talks, Anne handles everything.

**Build spec:** Written after Phase 3 handoff.

### Step 4.1 — Dictation bar (persistent input)

Text input bottom of every tab. Submit on Enter. Response area above.

### Step 4.2 — Voice parser

Structured action extraction: sales vocab, relative dates, population transitions, intel extraction, navigation, actions.
**Tests:** 20+ test phrases with expected structured output.

### Step 4.3 — Anne core (card presentation)

Claude API with system prompt, pipeline context. Card presentation with name, company, context, history, recommendation.
**Tests:** Present 5 cards. Verify context and suggestion quality.
**Error test:** API timeout → pre-generated presentation shown. API down → manual mode.

### Step 4.4 — Anne conversation + disagreement

Discuss prospects, answer questions, push back on bad decisions.
**Test:** Tell Anne to park a high-signal prospect. Verify she challenges.

### Step 4.5 — Obsessive note-taking + intel extraction

Every disposition → detailed notes + intel nuggets (pain points, competitors, loan types, timelines).
**Tests:** Dictate call outcome with details. Verify notes and nuggets created.

### Step 4.6 — Disposition engine

WON / OUT / ALIVE. ALIVE always requires follow-up date. Orphan enforcement.
**Test:** Leave engaged prospect without follow-up. Verify Anne flags it.

### Step 4.7 — Style learner

Curated email examples loaded into prompt context.
**Test:** Draft email with style learner. Compare to examples.

### Step 4.8 — Card story generator

Narrative from notes. "You first called John in November..."
**Test:** Generate for prospect with 3+ months of history.

### Step 4.9 — Pre-generation for latency

Batch-prepare next 5-10 card presentations during idle time and overnight.
**Performance test:** Measure with/without pre-generation. Target < 2 second card-to-card.

### Step 4.10 — Offline fallback + skip/defer/undo

API down → manual mode with dropdown selectors. Skip, defer, undo last 5 actions.
**Tests:** Disconnect → manual mode activates. Skip/defer/undo work. Reconnect → Anne wakes.

### Phase 4 Milestone Test

Jeff processes his entire daily queue by conversation with Anne. Anne presents with opinions, they discuss, Jeff decides, Anne executes with obsessive notes. Intel nuggets appear on next card visit. Style learner produces Jeff's voice. Offline mode works.

**Handoff → sign off → tag `phase-4-complete` → Phase 5 spec written.**

---

## PHASE 5: THE AUTONOMY

**Goal:** The system works while Jeff sleeps.

**Build spec:** Written after Phase 4 handoff.

### Step 5.1 — Autonomous research

Company website scraping, email pattern detection, Google Custom Search (free tier), NMLS lookup. 90% confidence rule.
**Tests:** Run against 10 broken records. Verify findings categorized (auto-fill vs. suggest).
**Honest expectation:** 20-30% fix rate. Test verifies the system correctly categorizes confidence, not that it magically finds everything.

### Step 5.2 — Groundskeeper

Flag stale data per blueprint intervals. Rolling prioritization by age × score.
**Tests:** Seed records with old verification dates. Verify flagging order.

### Step 5.3 — Nurture engine wired to Outlook

Warm Touch, Re-engagement, Breakup sequences. Daily send caps. Flagged as automated attempts.
**Tests:** Trigger nurture sequence. Verify correct email count, spacing, and automated flag.

### Step 5.4 — Reply monitor

Poll inbox every 30 min. Classify replies. Match to prospect. Flag interested replies for Jeff's review (no auto-promotion).
**Tests:** Send test reply. Verify classified, matched, and flagged for review (not auto-promoted).

### Step 5.5 — Email sync + activity capture

Sent/received emails stored in activity history for inline display.
**Test:** Email sent from Outlook appears on prospect card.

### Step 5.6 — Monthly bucket auto-activation

First business day of month: parked prospects for that month → Unengaged.
**Test:** Park prospect in target month. Trigger activation. Verify population change.

### Step 5.7 — Auto-replenish from ActiveCampaign

Low unengaged threshold triggers pull from AC.
**Test:** Set threshold, trigger, verify import.

### Step 5.8 — Nightly cycle (full 11 steps)

All steps wired end-to-end: backup → AC pull → dedup → assess → research → groundskeeper → re-score → bucket check → nurture → pre-generate brief + cards → extract intel.
**Test:** Run full cycle. Verify each step completed. Morning brief ready.
**Error test:** Cycle interrupted mid-run — picks up on next run, no data corruption.

### Step 5.9 — Orchestrator + Windows Task Scheduler

Starts on GUI launch AND headless via Task Scheduler. Registered tasks at blueprint intervals.
**Test:** Launch app → orchestrator running. Close app → Task Scheduler runs nightly at 2 AM.
**Error test:** Orchestrator crash → restarts on next scheduled run. Graceful shutdown on app close.

### Phase 5 Milestone Test

Jeff goes to bed. System backs up, researches broken records, flags stale data, sends nurture emails, monitors replies, scores prospects, activates monthly buckets, writes tomorrow's brief. Morning brief waiting when Jeff wakes up.

**Handoff → sign off → tag `phase-5-complete` → Phase 6 spec written.**

---

## PHASE 6: THE SOUL

**Goal:** ADHD-aware UX. The system understands Jeff's brain.

**Build spec:** Written after Phase 5 handoff. Each step below will be expanded into the same granularity as Phase 1-5 steps — specific tests, specific error handling, specific performance targets. The brief descriptions here are placeholders for that future spec.

### Step 6.1 — Dopamine engine
`gui/adhd/dopamine.py`. Streak tracking. Celebrations at 5, 10, 20 cards. Achievements: First Call, First Demo, First Close, Power Hour, Queue Cleared, Perfect Day.

### Step 6.2 — Session manager
`gui/adhd/session.py`. Time tracking with warnings (time blindness). Energy level: HIGH before 2 PM, MEDIUM 2-4 PM, LOW after 4 PM. Auto low-energy mode (reduced cognitive load).

### Step 6.3 — Focus mode
`gui/adhd/focus.py`. Current card fills screen. Queue hidden. Only: card, dictation bar, action buttons.

### Step 6.4 — Audio feedback
`gui/adhd/audio.py`. Sound for every action. Different tones for different outcomes. Mutable.

### Step 6.5 — Command palette
`gui/adhd/command_palette.py`. Ctrl+K. Fuzzy search across tabs, prospects, actions.

### Step 6.6 — Glanceable dashboard
`gui/adhd/dashboard.py`. One-second read of today's progress.

### Step 6.7 — Compassionate messages
`gui/adhd/compassion.py`. No guilt trips. "Welcome back. Here are the 3 most important things."

### Step 6.8 — Rescue engine
`ai/rescue.py`. Zero-capacity mode: "Just do these 3 things." Simplified interface.

### Step 6.9 — Troubled Cards + Intel Gaps tabs
Built from existing data: overdue, stale, conflicting. Cards missing useful but non-critical info.

### Step 6.10 — Bug/suggestion capture + setup wizard
In-app capture. First-run setup wizard.

### Phase 6 Milestone Test

Low-energy mode activates at 3 PM. Streaks celebrated. No guilt trips. Rescue mode available when Jeff is having a bad day. Command palette finds anything. Focus mode eliminates distractions.

**Handoff → sign off → tag `phase-6-complete` → Phase 7 spec written.**

---

## PHASE 7: THE WEAPONS

**Goal:** Anne becomes strategic. The system makes Jeff dangerous.

**Build spec:** Written after Phase 6 handoff. Same expansion treatment as earlier phases.

### Step 7.1 — AI copilot
`ai/copilot.py`. "What's our pipeline looking like?" "What's the story with ABC Lending?" Full strategic conversation.

### Step 7.2 — Record manipulation via conversation
Anne can update records, move populations, schedule follow-ups — all through conversation.

### Step 7.3 — Contact analyzer
`ai/contact_analyzer.py`. Engagement pattern analysis across companies.

### Step 7.4 — Prospect insights
`ai/insights.py`. Per-prospect strategic suggestions: best approach, likely objections.

### Step 7.5 — Learning engine
`engine/learning.py`. Qualitative patterns from notes on won/lost deals. "Three of your last four losses mentioned pricing."

### Step 7.6 — Intervention engine
`engine/intervention.py`. Pipeline decay detection: overdue follow-ups, stale leads, unworked cards.

### Step 7.7 — Proactive card interrogation
Anne reviews cards during brief generation: orphans, stale engaged leads, high-score/low-confidence.

### Step 7.8 — Analytics tab
Revenue, commission, close rate, cycle time, top sources. Numbers and CSV export.

### Step 7.9 — Endgame features
Dead lead resurrection audit (12+ months). Partnership promotion workflow. Nexys contract generator integration. Cost tracking refinement.

### Phase 7 Milestone Test

Anne references qualitative patterns from past deals. Interrogates cards proactively. Generates strategic insights. Analytics show real revenue and commission. The system is a weapon.

**Handoff → sign off → tag `phase-7-complete`**

**IronLung 3 is operational.**

---

## THE COMPLETE PICTURE

```
Phase 1: THE SLAB          16 steps, ~30 automated tests, ~15 manual smoke tests
Phase 2: THE DAILY GRIND   13 steps, ~20 automated tests, ~10 manual smoke tests
Phase 3: THE COMMUNICATOR  11 steps, ~15 automated tests, ~10 manual smoke tests
Phase 4: ANNE              10 steps, ~20 automated tests, ~8 manual smoke tests
Phase 5: THE AUTONOMY       9 steps, ~15 automated tests, ~5 manual smoke tests
Phase 6: THE SOUL          10 steps, spec written later
Phase 7: THE WEAPONS        9 steps, spec written later
                           ─────────
                           78 steps total
```

Each step: build, test, commit. Each phase: milestone test, handoff, sign-off, tag, write next spec. Never skip. Never combine. Never rush.

---

**Version:** 2.2
**Date:** February 4, 2026
**Parent Document:** docs/BLUEPRINT.md
**Status:** World-class construction sequence. Testing framework, version control, performance targets, error recovery, and formal handoffs built into every step.

**v2.1 changes:** Normalize test expectation updated (Holdings preserved). Lifecycle test clarified (two axes). Parent document reference updated to v3.1.

**v2.2 changes:** Voice bar → dictation bar. Reply monitor step updated (flag, don't auto-promote). Parent document reference updated to v3.2.
