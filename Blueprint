# IRONLUNG 3: THE BLUEPRINT (v3)

**The Anne Hathaway to Your Meryl Streep**

---

> The ADHD brain goes dead in a silent room clicking buttons.
> It comes alive when there's another intelligence in the room
> saying "okay, what about this one?"
> That's not a feature. That's the entire reason this software exists.

---

## WHAT THIS DOCUMENT IS

This is the architectural blueprint for IronLung 3. Every feature from IronLung 1 and IronLung 2 is accounted for. Impossible features have been stripped. Hard features have been simplified to honest implementations. Nothing is aspirational â†’ everything in this document can be built.

**What went wrong before:** IronLung 1 was built on Trello. When the architecture shifted to SQLite, the codebase tried to be both systems at once. The result: 55,000 lines with two GUIs, two nurture engines, two learning modules, two morning briefs, two voice systems, and three batch files. The features were right. The build order was wrong.

**What's different now:** One foundation. One of everything. Each layer is built and tested before the next one goes on top. No layer depends on anything above it. You can stop building at the end of any phase and have a working tool.

**What Trello taught us:** Trello's card format was good UX â†’ a visual card with a name, status, and key info at a glance. We keep that visual language. But Trello as a backend is gone. You can't put 300-400 contacts into a Trello board without it becoming clunky. SQLite handles 300,000 without blinking.

---

## THE CORE PRODUCT: THE CONVERSATION

Everything else in this document is plumbing. This is the product.

The system is Anne Hathaway from The Devil Wears Prada. Jeff is Anna Wintour. Anne has the entire pipeline in her head. She's done her homework on every card before Jeff even sees it. She presents prospects one at a time, with context and a preliminary read. They have a 15-30 second conversation about each one. Anne can suggest, push back, even disagree. Then whatever they decide together, Anne executes.

**This is what a card interaction looks like:**

> **Anne:** "John Smith, ABC Lending. Bridge and fix-and-flip out of Houston. This is attempt three â†’ you left voicemails Monday and the Thursday before. No callback."
>
> **Jeff:** "Yeah, this guy's a ghost. What do we have on him?"
>
> **Anne:** "His company's doing volume â†’ they closed 40 loans last quarter according to their site. He's worth pursuing. But three voicemails with no callback isn't working. Want to switch to email? Or park him and try fresh in a month?"
>
> **Jeff:** "Send him an email. Something short. Hey, I've been trying to reach you, we work with fix-and-flip shops in Texas, would love 15 minutes."
>
> **Anne:** "Got it. Here's the draft: [shows email]. Send it?"
>
> **Jeff:** "Send it."
>
> **Anne:** "Sent. Follow-up in 5 business days if no reply. Next card."

Twenty seconds. Card handled. Anne had an opinion â†’ she said three voicemails isn't working. Jeff could've overruled her. He didn't because she was right.

**Why this works for ADHD:** The brain that dies in a silent room clicking buttons comes alive when there's a body double in the room. Anne is the body double. She keeps the rhythm going: card, conversation, decision, next. Card, conversation, decision, next. The momentum carries Jeff through 30-40 prospects in 90 minutes because he's never alone with the silence.

**Anne's rules:**
- She always presents the card first â†’ name, company, context, history, her suggestion
- She never executes without Jeff's confirmation
- She's allowed to disagree ("Are you sure you want to park him? He's showing buying signals.")
- She drafts emails in Jeff's voice, not robot voice
- She dials the phone when Jeff says dial
- She handles all the filing, calendaring, and note-taking after disposition
- She is an obsessive note taker â†’ every detail from every conversation gets logged. The notes ARE the memory.

---

## THE LIFECYCLE: HOW PROSPECTS MOVE

Prospects are seedlings. The system grows them.

```
 +------------------+
 | IMPORTED |
 | (Raw Data) |
 +--------+---------+
 |
 +--------v---------+
 +-----+ ASSESSED +------+
 | +------------------+ |
 | |
 +--------v----------+ +--------------v----------------+
 | BROKEN | | UNENGAGED |
 | Missing phone | | Complete data. |
 | or email. | | Jeff is chasing. |
 | Being fixed. | | SYSTEM-PACED. |
 +--------+----------+ +---------------+---------------+
 | (fixed) |
 +------------+ +--------------+
 | |
 +------------v----v--------------------------+
 | ENGAGED |
 | They showed interest. |
 | PROSPECT-PACED. |
 | Always has a date. |
 +---------------------+----------------------+
 |
 +---------------------v----------------------+
 | DEMO SCHEDULED |
 | Date certain on calendar |
 +---------------------+----------------------+
 |
 +---------------------v----------------------+
 | WARMING TRAY |
 | Post-demo. Percolating. |
 | PROSPECT-PACED. |
 +-----------+-----------------+--------------+
 | |
 +-----------v-------+ +-------v--------------+
 | CLOSED | | LOST |
 | Won! $ | | (not DNC) |
 +-------------------+ +----------------------+

```

**Side tracks (can happen from any active population):**

- ** -> Parked:** "Call me in June." Filed in monthly bucket. Auto-activates back to Unengaged on first business day of that month.
- ** -> DNC:** "Don't ever call me." Permanent. Absolute. No resurrection. No exceptions. Out of everything forever. Sacrosanct â†’ no import can touch a DNC record.
- ** -> Lost:** Went with a competitor or decided not to buy. Different from DNC. Might be worth revisiting in 12+ months.

---

## THE TWO CADENCES

The most important logic in the system. Two completely different follow-up philosophies based on one variable: **who controls the timing.**

### Unengaged Cadence: The System Controls the Clock

The prospect never said "call me Thursday." The prospect might not even know Jeff exists. Jeff decides the cadence. The system enforces it.

The goal: Present enough to stay on radar. Spaced enough not to be a stalker.

| Attempt | Channel | Wait Before Next |
|---|---|---|
| 1 | Call | 3-5 business days |
| 2 | Call | 5-7 business days |
| 3 | Email (if no callbacks) | 7-10 business days |
| 4 | Call + email combo | 10-14 business days |
| 5+ | Evaluate: park, try different approach, or mark dead |

These intervals are configurable. The system manages the math. Jeff never has to think "when did I last call this person?"

**What counts as an attempt:** An attempt is any outbound contact that could have reached the prospect.
- Phone call (answered or not) = 1 attempt
- Voicemail = part of that same call attempt, not a separate one
- Email sent = 1 attempt
- Phone call + email same day = 2 attempts

The cadence timer resets on the LAST attempt of the day. The system tracks both the attempt NUMBER (to know which interval to apply) and the LAST ATTEMPT DATE (to calculate the next window).

System-sent nurture emails count as attempts but are flagged as automated. Anne knows the difference â†’ "This is attempt 4, but two were automated nurture emails. He's only heard your voice once."

### Engaged Cadence: The Prospect Controls the Clock

The moment someone shows interest, the rules change completely. Now Jeff asks "when should I follow up?" and the prospect gives a date. That date is sacred.

- Prospect says "call me Wednesday" -> follow-up is Wednesday. Not Tuesday. Not Thursday.
- Prospect says "I need two weeks" -> follow-up is 14 days out.
- Prospect says "after our board meeting next month" -> parked to that month.

It's never intrusive because the prospect **invited** the call.

The engaged path:
1. **Engaged / Pre-Demo:** Working toward scheduling a demo. Prospect-paced follow-ups.
2. **Demo Scheduled:** Date certain on the calendar. Demo prep auto-generated.
3. **Warming Tray (Post-Demo):** They've seen the product. Percolating. Prospect-paced â†’ "I need to talk to my partner, call me in two weeks." Different context than pre-demo: not "let me show you what we do" but "what did you think? What questions came up?"
4. **Closed Won** or **Lost.**

**No orphan engaged leads.** If an engaged prospect has no follow-up date, Anne flags it immediately: "He's engaged but you didn't set a follow-up date. That's an orphan. When should we call?"

---

## THE SIX THINGS (Jeff's Words, 1:00 AM, February 4, 2026)

1. **The Rolodex.** It holds everybody. SQLite. Local. Mine.
2. **The Sorting.** Clear status for every contact. System knows who I talk to today.
3. **The Grind Partner.** One card at a time. Deal with it. Next card.
4. **The Email Writer.** Helps write emails. Sends them. Through Outlook. Actually sent.
5. **The Dialer.** Click and I'm calling. Through Bria.
6. **The Calendar Brain.** Places follow-ups at the right cadence. Not too fast. Not too slow.

Everything below serves these six things. If a feature doesn't connect back to one of them, it doesn't belong.

---

## ARCHITECTURE: THE SEVEN LAYERS

Build from bottom to top. Each layer only depends on layers below it. Never above.

```
+---------------------------------------------------------------------+
| LAYER 7: THE SOUL |
| ADHD UX -> Dopamine, Focus, Energy, Compassion |
+---------------------------------------------------------------------+
| LAYER 6: THE HEARTBEAT |
| Autonomous Ops -> Nightly Cycle, Nurture, |
| Groundskeeper, Reply Monitoring, Scheduler |
+---------------------------------------------------------------------+
| LAYER 5: THE BRAIN (ANNE) |
| Conversational AI -> Anne presents cards, |
| suggests actions, drafts emails, disagrees, |
| takes obsessive notes, executes after confirm |
+---------------------------------------------------------------------+
| LAYER 4: THE FACE |
| GUI -> Tabs, Dictation Bar, Cards, Shortcuts |
+---------------------------------------------------------------------+
| LAYER 3: THE ENGINE |
| Business Logic -> Populations, Scoring, |
| Cadences, Research, Nurture, Learning |
+---------------------------------------------------------------------+
| LAYER 2: THE PIPES |
| Integrations -> Outlook, Bria, ActiveCampaign, |
| Google Search, CSV Import |
+---------------------------------------------------------------------+
| LAYER 1: THE SLAB |
| Database, Models, Config, Logging, Exceptions |
+---------------------------------------------------------------------+

```

---

## LAYER 1: THE SLAB

*Nothing works without this. Built first. Never changes underneath other layers.*

### 1.1 SQLite Database (`db/database.py`)

Local single-file database. No server. No network calls. Ships with Python. Path: `~/.ironlung/ironlung3.db`

Schema:
- **companies** â†’ Company name (display + normalized for dedup), domain, loan types (JSON), size, state, timezone (auto-assigned, see Timezone Assignment below), notes
- **prospects** â†’ Contact linked to company. Population, engagement stage, parked month, follow-up date, last contact, attempt count, prospect score, data confidence, source, dead reason/competitor/date, notes (TEXT â†’ static context only, e.g. "CEO, hates cold calls"; the running log of interaction notes lives in activities.notes), custom fields (JSON blob for user-defined variables). For closed-won records: deal_value, close_date, close_notes.
- **contact_methods** â†’ Multiple emails/phones per prospect. Type, value, label (work/personal/cell/main), primary flag, verified flag, verified date, confidence score, suspect flag, source (where it was found)
- **activities** â†’ Complete audit trail. Every call, email, voicemail, note, status change, skip, defer. Outcome, notes, email subject/body, follow-up set, population before/after, stage before/after (engagement stage transitions tracked independently), attempt_type (personal or automated), created by (user or system)
- **data_freshness** â†’ Per-field verification timestamps. Field name, verified date, method, confidence, previous value
- **import_sources** â†’ Every import batch tracked. Source name, filename, record counts, timestamp
- **research_queue** â†’ Broken prospects queued for autonomous research. Priority, status, attempts, last attempt date, findings (JSON)
- **intel_nuggets** â†’ Extracted facts from notes for during-call cheat sheet. Prospect ID, category (pain_point, competitor, loan_type, decision_timeline, key_fact), content, source activity ID, extracted date
- **prospect_tags** -- User-defined labels on prospects. Tag name, prospect ID, created date. Tags are a flexible organizational layer on top of populations " "hot-referral," "conference-lead," "needs-pricing-call," anything. Filterable in Pipeline tab. Visible on cards. Bulk-applicable. Tags carry no transition rules and don't affect cadence or DNC protection.
- **schema_version** â†’ For future migrations

Indexes on: population, follow_up_date, company_id, prospect_score, email (contact_methods), parked_month, tag_name (prospect_tags).

Foreign keys enforced. WAL mode for concurrent read/write.

**Custom fields on prospect cards:** The card format borrows from Trello's visual language but adds flexibility Trello never had. Users can define custom variables (key-value pairs stored as JSON) on any card. Loan types, estimated volume, tech stack, decision timeline â†’ whatever Jeff needs to track for his vertical.

**Timezone Assignment:** Automatic cascade:
1. If company state is populated -> timezone from state lookup table (TX=Central, CA=Pacific, NY=Eastern, etc.)
2. If state is blank but phone area code exists -> timezone from area code lookup
3. If neither -> default to Central (Jeff's timezone)

Timezone lives on the company record. All contacts at the same company share a timezone. Used for queue ordering (East Coast first in the morning).

### 1.2 Data Models (`db/models.py`)

Enumerations:
- **Population:** broken, unengaged, engaged, parked, dead_dnc, lost, partnership, closed_won
- **EngagementStage:** pre_demo, demo_scheduled, post_demo (warming_tray), closing
- **ActivityType:** call, voicemail, email_sent, email_received, demo, demo_scheduled, demo_completed, note, status_change, skip, defer, import, enrichment, verification, reminder, task
- **ActivityOutcome:** no_answer, left_vm, spoke_with, interested, not_interested, not_now, demo_set, demo_completed, closed_won, closed_lost, bounced, replied, ooo, referral
- **DeadReason:** dnc (do not contact â†’ permanent, absolute, no exceptions)
- **LostReason:** lost_to_competitor, not_buying, timing, budget, out_of_business
- **ContactMethodType:** email, phone
- **AttemptType:** personal, automated (distinguishes Jeff's direct outreach from system-sent nurture)

Dataclasses: Company, Prospect, ContactMethod, Activity, DataFreshness, ImportSource, ResearchTask, IntelNugget

Utility: `normalize_company_name()` â†’ strips only legal entity designators (LLC, Inc, Corp, Corporation, Ltd, LP, Co, Company) for dedup matching. Identity terms common in private lending (Holdings, Capital, Group, Partners, Financial, Services) are preserved. "ABC Capital" and "ABC Lending" are different companies.

**Key distinction:** Dead/DNC and Lost are separate populations with different rules:
- **DNC:** Permanent. Absolute. No resurrection. No exceptions. No import can reactivate. Out of everything forever.

**DNC 24-hour grace period:** Because misclicks, dictation errors, and parser misinterpretation happen, a DNC transition can be reversed within 24 hours of being set. The reversal is logged as an activity with a mandatory reason. After 24 hours, the DNC is permanent and irreversible â€” the standard rules apply. This prevents a single wrong click from permanently losing a hot prospect while preserving the sanctity of DNC as a near-absolute protection.
- **Lost:** Went with a competitor or decided not to buy. Not hostile â†’ just didn't work out this time. Eligible for resurrection review after 12+ months.

### 1.3 Backup System (`db/backup.py`)

Non-negotiable. SQLite is a single file. Laptop dies = everything gone.

- **Nightly local backup:** Copy DB to timestamped file in `/backups`. Keep 30 days.
- **Cloud sync:** Copy backup to OneDrive sync folder (simple file copy, no API).
- **Pre-import snapshot:** Before every bulk import.
- **Recovery:** Single command restores from any backup. GUI has recovery option in Settings.

### 1.4 Configuration (`core/config.py`)

Centralized config via environment variables with sensible defaults. Paths, API credentials, feature flags, cadence settings (configurable intervals for unengaged cadence), commission rate (default 6%). `validate_config()` checks all integrations on startup.

### 1.5 Logging (`core/logging.py`)

Structured JSON logging with context fields. Every significant operation logs start, success, or failure.

### 1.6 Exceptions (`core/exceptions.py`)

Custom hierarchy: `IronLungError` with subtypes: `ConfigurationError`, `ValidationError`, `DatabaseError`, `IntegrationError` (subtypes: `OutlookError`, `BriaError`, `ActiveCampaignError`), `ImportError_`, `PipelineError` (subtype: `DNCViolationError`), `GUIError`. `DNCViolationError` is its own class because DNC violations are categorically different from other pipeline errors.

### 1.7 Utilities

- **Cost tracking** (`utils/cost_tracking.py`) â†’ Track Claude API call costs, rate limits
- **Retry logic** (`utils/retry.py`) â†’ Decorators with exponential backoff, circuit breaker
- **Task management** (`core/tasks.py`) â†’ Thread management, task execution
- **Async helpers** (`utils/async_helpers.py`) â†’ Async wrappers for blocking operations

---

## LAYER 2: THE PIPES

*How IronLung talks to the outside world. Each integration is independent. None depend on each other.*

### 2.1 Outlook Client (`integrations/outlook.py`)

Microsoft Graph API. The most critical integration.

Capabilities:
- Send email (plain text and HTML)
- Create drafts
- Read inbox (poll every 30 min)
- Classify replies (interested, not_interested, ooo, referral, unknown)
- Calendar operations (create, read, update events)
- Teams meeting link generation for demo invites

Auth: OAuth2 with CLIENT_ID, CLIENT_SECRET, TENANT_ID from env vars. Token refresh handled automatically.

Note: Webhooks (real-time push notifications) are impractical for a desktop app â†’ they require a publicly accessible URL. Polling every 30 minutes is reliable and sufficient.

### 2.2 Bria Dialer (`integrations/bria.py`)

Jeff's softphone. Already installed, already configured, already connected to his line.

Integration: Bria supports `tel:` and `sip:` URI schemes, and/or command-line API. Click a phone number on a card -> Bria dials. No Twilio. No per-minute billing. No phone infrastructure to build.

Note: Bria requires internet (SIP). When offline, phone numbers display but clicking them copies to clipboard instead.

### 2.3 ActiveCampaign Client (`integrations/activecampaign.py`)

API integration for pulling new prospects from AC pipelines. Automated pull during nightly cycle.

### 2.4 Google Custom Search (`integrations/google_search.py`)

Free tier (100 queries/day). Used by autonomous research for broken prospects.

### 2.5 CSV/Excel Importer (`integrations/csv_importer.py`)

Drag-and-drop file import with column mapping UI. Supports CSV, XLSX. Presets for PhoneBurner export format, AAPL directory format, and custom scrapes. Email data comes in via CSV â†’ Jeff's established workflow.

### 2.6 Integration Base (`integrations/base.py`)

Base classes for all integrations. Standard patterns for auth, rate limiting, error handling, health checks.

### 2.7 Email CSV Importer (`integrations/email_importer.py`)

Import sent and inbox email exports (CSV) to enrich prospect cards with email history. Matches emails to prospects by email address. Creates activity records with email subject, body, date, and direction (sent/received). Available before the Microsoft Graph integration is built â€” gives Jeff email enrichment from Phase 2 using his existing workflow of exporting from Outlook to CSV. Once Graph API is live in Phase 3, this becomes a fallback/bulk-import option rather than the primary email sync path.


---

## LAYER 3: THE ENGINE

*The business logic. How prospects move through the system. How scoring works. How cadence is managed. No GUI code here â†’ this layer is pure logic.*

### 3.1 Population Manager (`engine/populations.py`)

Manages population definitions and transition rules. Every transition is logged as an activity.

**Population transitions** (where they live in the pipeline):
- Broken -> Unengaged (when fixed)
- Unengaged -> Broken (data degraded â†’ phone went bad, email bounced)
- Unengaged -> Engaged (showed interest)
- Unengaged -> Parked ("call me in June")
- Unengaged -> DNC ("don't ever call me")
- Unengaged -> Lost (they chose a competitor before engagement)
- Engaged -> Parked ("not right now, try me in Q3")
- Engaged -> DNC
- Engaged -> Lost
- Engaged -> Closed Won (can close from any engaged stage)
- Parked -> Unengaged (month arrived, auto-activation)
- Lost -> Unengaged (resurrection review, 12+ months later, Jeff's decision)
- Partnership -> Unengaged or Engaged (promotion)

**Engagement stage transitions** (within Engaged â†’ population stays "engaged", only stage changes):
- pre_demo -> demo_scheduled (demo date confirmed)
- demo_scheduled -> post_demo (demo completed, warming tray)
- post_demo -> closing (active contract negotiation)

Both axes are logged independently in the activities table: `population_before/population_after` and `stage_before/stage_after`. A prospect can move on one axis without moving on the other.

Invalid transitions:
- DNC -> anything. Ever.
- Closed Won -> anything (it's done, celebrate)

### 3.2 Cadence Engine (`engine/cadence.py`)

Two cadence systems in one module. (See "The Two Cadences" section above for full rules.)

**Unengaged cadence (system-paced):** Configurable intervals. System calculates next contact date automatically after each disposition based on attempt number and last attempt date.

**Engaged cadence (prospect-paced):** No algorithm. Jeff enters the date the prospect gave. System enforces it exactly. Anne flags orphaned engaged leads with no follow-up date.

### 3.3 Scoring Algorithm (`engine/scoring.py`)

0-100 composite score from weighted categories:
- Company fit (loan types, size, geography)
- Contact quality (title seniority, data completeness, verification status)
- Engagement signals (responses, demo interest)
- Timing signals (budget cycle, recent contact)
- Source quality (where they came from)

Weights are manually tuned based on Jeff's sales intuition. No auto-tuning â†’ not enough data yet. As the note history grows over 12+ months, the learning engine can begin adjusting.

### 3.4 Data Confidence Score

Every record gets 0-100 confidence from field freshness, verification history, and source reliability. High prospect score + low confidence = Groundskeeper priority. Displayed as a small badge on the card.

### 3.5 Intake Funnel (`db/intake.py`)

Three-pass deduplication:
1. **Exact email match** â†’ same person. Merge non-empty fields.
2. **Fuzzy company + name** â†’ normalized company name, 85% name similarity threshold.
3. **Phone match** â†’ flagged for manual review (shared main lines).

**DNC Protection (hard rule):** During dedup, before any merge, the system checks: "Is this matching record DNC?" If yes, the imported record is silently dropped. Not merged. Not updated. Not reactivated. Appears in the import preview under a red "Blocked â†’ DNC match" section. This applies to ALL match types â†’ exact email, fuzzy name+company, phone. If ANY match hits a DNC record, the row is blocked. Better to accidentally block a legitimate new contact than to accidentally resurrect a DNC. Jeff can manually override if it's truly a different person, but the system never does it automatically.

Import preview before commit: "412 new, 87 enriched, 23 need review, 6 too incomplete, 3 blocked (DNC match)."

Post-import: Assess completeness -> Broken (missing critical data) or Unengaged (ready to work). Initial score assigned. Source tagged.

### 3.6 Autonomous Research (`engine/research.py`)

Runs against Broken prospects during nightly cycle. Goal: find missing phone numbers and emails so broken records can graduate to Unengaged.

**The 90% Rule:** The system does NOT guess. It does NOT fill in blanks based on hunches.
- **Auto-fill (90%+ confidence):** Found the email on the company's Contact Us page with the person's name next to it. Phone number on the About page with the prospect's name. That goes in automatically. System logs source and timestamp.
- **Suggestion (below 90%):** "The company email pattern appears to be firstname@company.com. Want me to try that?" or "Found a phone number but it's the main line, not direct." Shows Jeff what it found, where, and its confidence level. Jeff confirms or rejects.

**Honest expectations on confidence scoring:** In practice, the system uses simple rules rather than a percentage: "found on company website with name match" = auto-fill. Everything else = suggest and let Jeff decide.

**Free sources only. No paid APIs.**
1. Company website scraping â†’ /about, /team, /contact pages
2. Email pattern detection (firstname@domain, first.last@domain, etc.)
3. Google Custom Search â†’ free tier, 100/day
4. NMLS Lookup â†’ free, for licensed lenders
5. General web search for public business listings

**Honest expectations on hit rates:** This will fix maybe 20-30% of broken records autonomously. Not 50-60%. The system's best contribution for the rest is pre-building search links (company website, Google search for the person, NMLS lookup) so Jeff can click through them quickly in the Broken tab.

### 3.7 Groundskeeper (`engine/groundskeeper.py`)

Continuous database maintenance. Flags stale data for manual review.

| Field | Flag After | Method |
|---|---|---|
| Email | 90 days | Flag for manual check (SMTP verification is unreliable) |
| Phone | 180 days | Flag for manual check |
| Title/Role | 120 days | Company website re-scrape |
| Company existence | 180 days | Domain check |

Rolling prioritization by data age prospect score.

### 3.8 Nurture Logic (`engine/nurture.py`)

Email sequences for unengaged prospects (system-paced):
- **Warm Touch:** 3 emails, 7 days apart. Light, professional, value-oriented.
- **Re-engagement:** For prospects who went quiet after initial interest.
- **Breakup:** Final email. Often triggers response.

Emails are drafted and queued for Jeff's approval, not auto-sent. Anne generates a batch (e.g., 30 nurture emails overnight), Jeff reviews them in a batch approval UI â€” approve, edit, skip, approve, approve â€” then they send through Outlook. This maintains quality control and CAN-SPAM compliance (Jeff personally approves each send). Logged to activity history. Flagged as automated attempts. Daily send caps respected.

### 3.9 Learning Engine (`engine/learning.py`)

Reads notes on won and lost deals for qualitative patterns:
- "They went with LoanPro because of price"
- "Closed because they loved the borrower portal"
- "Lost â†’ too small, couldn't justify the cost"

Over time, Anne references this: "Three of your last four losses mentioned pricing â†’ might want to lead with value on this one." This is note-driven intelligence, not statistical modeling. Works from day one with even a handful of closed deals.

### 3.10 Intervention Engine (`engine/intervention.py`)

Detects pipeline decay: overdue follow-ups, stale engaged leads, unworked cards. Flags for Anne to surface during morning brief or card presentation.

### 3.11 Email Templates (`engine/templates.py`)

Jinja2 templates with frontmatter. Types: intro, follow-up, demo confirmation, nurture sequences, breakup, demo invite. All auto-populated with prospect data.

**Demo invite template:** Pre-built. One voice command: "Schedule demo Thursday at 2." System pulls email from database, uses configurable duration (default 30 min), generates Teams meeting invite with Nexys template pre-populated with prospect name/company. Preview appears. "Send it" -> sent and logged.

### 3.12 Email Generator (`engine/email_gen.py`)

AI-powered email drafting for ad-hoc emails. Jeff dictates the gist, Anne packages it in Jeff's voice. Draft appears, Jeff approves or edits, then it sends.

### 3.13 Demo Prep (`engine/demo_prep.py`)

Auto-generated demo preparation: loan types, company size, state, pain points from notes, competitive landscape from intel nuggets. Ready before the demo.

### 3.14 Data Export (`engine/export.py`)

**Quick export:** Whatever Jeff is currently filtering in the Pipeline tab â†’ all engaged prospects, all prospects in Texas, all demos this month â†’ one click exports that view as a CSV. Same columns visible on screen.

**Monthly summary report:** Auto-generated or on-demand. Plain numbers: demos booked, deals closed, deal values, commission earned, pipeline movement, calls made, emails sent. Exportable as CSV or printable text. Jeff's manager asks "how'd January go?" â†’ report in two seconds.

---

## LAYER 4: THE FACE

*What Jeff actually sees and touches. One GUI. One entry point. Clean tabs. Dictation Bar at the bottom of every screen.*

**Tech stack:** Python tkinter. Already proven. No framework change.

**One entry point:** `ironlung3.py` -> initializes database -> launches GUI.

### 4.1 Tab Structure

| Tab | Purpose | Serves Which of the 6 Things |
|---|---|---|
| **Today** | Morning brief, then the processing loop. Primary work surface. | #2 Sorting, #3 Grind |
| **Broken** | Active workbench for records missing phone or email. Research status. Confirm/reject. | #1 Rolodex |
| **Pipeline** | Full database. Filter, search, sort, multi-select, bulk actions, export. | #1 Rolodex, #2 Sorting |
| **Calendar** | Day and week views. Follow-ups, demos, monthly buckets. Outlook-integrated. | #6 Calendar Brain |
| **Demos** | Invite creator. Upcoming demos. Prep docs. Post-demo tracking. | #4 Email, #6 Calendar |
| **Partnerships** | Non-prospect contacts. Relationship notes. Promote-to-prospect. | #1 Rolodex |
| **Import** | File upload, column mapping, dedup preview, DNC protection, import history. | #1 Rolodex |
| **Settings** | Credentials, cadence rules, templates, backup/recovery, commission rate, metrics. | â†’ |

Additional tabs (added after core is stable):
- **Troubled Cards** â†’ Active cards with problems. Overdue, stalled, conflicting data. Prioritized.
- **Intel Gaps** â†’ Cards missing non-critical but useful info. "These 15 need titles found."
- **Analytics** â†’ Simple performance numbers. Close rate, cycle time, top sources, revenue, commission. Numbers and CSV export.

### 4.2 The Dictation Bar

Persistent text input at the bottom of every tab. Large, clear font. Always visible. Always ready.

This is where the conversation with Anne happens. Jeff speaks (via Windows dictation) or types. Anne responds in the area above the dictation bar. Confirmation cards appear there too.

The dictation bar is the universal input. There is no separate "add note" button, "change status" dropdown, or "schedule follow-up" date picker. Jeff speaks into one input, Anne figures out what he meant and proposes the action.

**Offline fallback:** When internet is unavailable and Anne is offline, the dictation bar switches to manual mode â†’ Jeff types notes directly and they log to the card without AI parsing. Manual dropdown selectors appear for status changes and follow-up dates.

### 4.3 The Prospect Card

Visual format inspired by Trello cards but richer.

**Glance View (default â†’ used in processing queue):**
- Name and title: John Smith, CEO
- Company: ABC Lending (Bridge, Fix & Flip)
- Phone number: Clickable -> Bria dials
- Why they're up today: "Follow-up â†’ he said call Wednesday" or "Attempt #3 â†’ no responses"
- Last interaction: One line. "1/30: Left VM, said try again this week."
- Scores: Prospect score | Data confidence (small badges)
- Custom fields: Whatever Jeff defined (loan volume, tech stack, etc.)

**Call Mode (activates when Jeff clicks dial or says "call him"):**
Same card, rearranged for the phone conversation. Anne goes silent â†’ becomes a cheat sheet.
- Top: Name, title, company (large font â†’ Jeff's glancing while talking)
- Below: Last 3 interactions as brief lines
- Below: Intel nuggets from notes ("Fix and flip in Houston. Evaluating three vendors. Pain point: manual borrower intake. Currently using spreadsheets.")
- Bottom: Dictation Bar, ready for post-call disposition

Intel nuggets are extracted from notes whenever Jeff logs information â†’ loan types, pain points, competitors, decision timelines. When the card comes up again, those nuggets surface automatically. Pre-generated during morning brief prep so there's no latency at dial time.

**Deep Dive (expandable â†’ Jeff says "show me more" or "what do we have on him"):**
- Full activity history (every call, email, note, status change)
- All contact methods with verification status and source
- All email correspondence inline (no switching to Outlook)
- Company details: loan types, size, state, other contacts at same company
- Research findings: where each piece of data was found, when verified, confidence
- All notes in full
- Custom field values

**Company Context Panel:** "2 other contacts at ABC Lending." Prevents calling the CEO not knowing a colleague talked to the VP last week.

### 4.4 The Processing Loop

This is the core interaction. Anne-led.

1. **Anne presents** the next card with context, history, and her suggestion.
2. **Jeff and Anne converse** for 15-30 seconds. Anne may suggest, Jeff may override, Anne may push back.
3. **They decide** what to do â†’ call, email, park, defer, mark dead, send demo invite, etc.
4. If Jeff calls: card switches to **Call Mode** (cheat sheet). After the call, Jeff tells Anne what happened.
5. **Anne shows** the disposition: "Log voicemail. Follow up Monday. Sound right?"
6. **Jeff confirms.**
7. **Anne executes** â†’ logs activity, writes detailed notes, extracts intel nuggets, updates population, sets follow-up date, sends email if applicable.
8. **Anne presents** next card.

### 4.5 The Morning Brief -> Queue Transition

The morning brief appears when the app launches as a dialog over the Today tab. Jeff reads it in 60 seconds. At the bottom:

> "You've got 5 engaged follow-ups and 14 unengaged attempts today. Ready?"

Jeff says "let's go" or clicks "Start" or hits Enter. The brief closes, the Today tab is underneath, and Anne presents the first card immediately. No mode switch. No navigation. The brief was a curtain â†’ it lifts and the work is already staged behind it.

"Today's Brief" button in the Today tab header to reference it later.

### 4.6 Morning Brief Content

Anne's morning memo. Readable in 60 seconds.

> "Good morning. You've got 147 active prospects. 12 engaged â†’ 2 in closing, 3 warming, 4 with demos this week, 3 pre-demo. 89 unengaged. 22 parked. 24 broken â†’ I fixed 3 overnight, 4 more need your eyes.
>
> Today's engaged follow-ups (5): [sorted by stage, closing first]
> Overdue (2): [in red, with days overdue]
> Unengaged attempts (12): [sorted by score]
>
> Overnight: Found emails for 3 broken records (confirm in Broken tab). Sent 4 nurture emails. 1 reply from Sarah at TechLend â€” she sounds interested. Flagged for your review."

### 4.7 Queue Ordering

Engaged follow-ups first (closing -> post-demo -> demo-scheduled -> pre-demo), then unengaged attempts sorted by score.

**Within each group, timezone-ordered:** East Coast first (callable when Jeff sits down at 8 AM CT â†’ it's 9 AM there), then Central, Mountain, Pacific (not callable until 10 AM CT when it's 8 AM there). Anne doesn't announce this â†’ she just presents cards in the right order.

**Overdue rollover rule:** The queue query uses `follow_up_date <= today`, not `== today`. Missed follow-ups carry forward automatically â€” they never silently expire. If Jeff has a potato day and doesn't open the app, Wednesday's 8 callbacks show up in Thursday's queue alongside Thursday's scheduled items. Overdue items surface first within the engaged group, flagged with days overdue. The morning brief calls them out: "7 engaged follow-ups â€” 3 are overdue from yesterday." Unengaged cadence recalculates from the last actual attempt, not the scheduled date â€” no compounding debt from missed days.

### 4.8 The Calendar

A real calendar. Not a list of dates.

**Day view:** Hour-by-hour. Follow-ups, demos, callbacks in time slots respecting timezone logic.

**Week view:** Seven columns. Shape of the week. Clusters and gaps visible.

**Outlook-integrated:** Demo events appear in both IronLung and Outlook calendar. Follow-ups live in IronLung (prospecting actions, not calendar events), but demo invites sync to Outlook.

**Monthly bucket visualization:** Parked contacts grouped by month. "March: 8 prospects activating on the 3rd."

### 4.9 The Broken Prospects Tab

Three sections, top to bottom:

**Needs Confirmation (system found something):**
| Name | Company | Missing | Found | Source | Confidence | [Confirm] [Reject] |
|---|---|---|---|---|---|---|
| John Smith | ABC Lending | Email | john@abclending.com | Company website /contact | High | -â€¦"-" -â€¦"-" |

Jeff confirms with one click or by voice. Confirmed records graduate to Unengaged immediately.

**In Progress (system is still looking):**
| Name | Company | Missing | Status | Last Attempt |
|---|---|---|---|---|
| Sarah Jones | XYZ Capital | Phone | Checking website, trying Google | 2 hours ago |

Hands-off. System is working.

**Manual Research Needed (system struck out):**
| Name | Company | Missing | Research Links |
|---|---|---|---|
| Mike Chen | 123 Funding | Email, Phone | [Company Site] [Google: "Mike Chen 123 Funding"] [NMLS] |

Pre-built clickable links. Jeff does the research with minimal friction. Says "Mike Chen's email is mike@123funding.com" and Anne updates the record.

Tab header count: "24 Broken â†’ 3 ready to confirm, 8 in progress, 13 need you."

### 4.10 Bulk Operations

**Pipeline tab multi-select:** Checkboxes or Shift+click. Bulk action bar appears: "Move to -> [population]" or "Set follow-up -> [date]" or "Park in -> [month]" or "Tag -> [custom field]."

Common use: 30 new imports need sorting -> Pipeline tab -> filter "imported today" -> select all -> "Park in June." Done.

**Voice bulk commands:** "Park everyone from ABC Lending in March." Anne: "That's 3 records. Park all in March?" Jeff confirms.

Always shows confirmation count before executing. Never silently modifies multiple records.

### 4.11 Closed Won Flow

When Jeff dispositions WON, the system asks three things:
1. **Deal value** (monthly recurring or one-time â†’ just the number)
2. **Close date** (defaults to today)
3. **Notes** (optional â†’ "12-month contract, 200 users, starts March 1")

Stored on the prospect record. Shows in Analytics: total revenue, average deal size, average cycle time, commission earned (calculated from configured rate â†’ default 6%).

### 4.12 End-of-Day Summary

When queue is empty or Jeff says "wrap up":

> "You processed 34 today. 11 connected calls. 16 voicemails. 4 emails sent. 3 demos scheduled. 2 marked dead. 2 parked.
>
> Pipeline movement: 4 unengaged -> engaged. 1 -> closing. Net: +3 engaged.
>
> Tomorrow: 8 engaged follow-ups. 14 unengaged attempts queued. First call at 8:15 AM."

### 4.13 Keyboard Shortcuts

| Key | Action |
|---|---|
| Enter | Confirm / submit dictation bar |
| Escape | Cancel / close expanded card |
| Ctrl+Z | Undo last action |
| Tab | Skip to next card |
| Ctrl+D | Defer current card |
| Ctrl+F | Quick lookup (focus search) |
| Ctrl+M | Demo invite creator |
| Ctrl+E | Send one-off email |
| Ctrl+K | Command palette |

### 4.14 Quick Lookup (Inbound Calls)

Phone rings mid-processing. Jeff says "pull up John Smith" or types. SQLite full-text search is instant. Full context on screen while on the phone. After the call, disposition by voice. System returns to queue.

### 4.15 Email Recall (`gui/dialogs/email_recall.py`)

The "Oh Shit" button. Recall interface if an email goes out wrong.

### 4.16 Bug/Suggestion Capture

Button in the UI: "This broke" or "I wish it could..." Logs to a file for review next dev session.

---

## LAYER 5: THE BRAIN (ANNE)

*The conversational AI. Anne sees the whole pipeline, presents cards with opinions, takes obsessive notes, drafts emails in Jeff's voice, disagrees when warranted, and executes after confirmation.*

### 5.1 Anne Core (`ai/anne.py`)

The central conversational engine. Anne IS the processing interface.

Anne's capabilities:
- **Pipeline awareness:** Sees all prospects, all statuses, all history
- **Card presentation:** Presents each card with context, history, and a recommendation
- **Conversation:** Can discuss each prospect â†’ answer questions, offer opinions, push back
- **Obsessive note-taking:** Every detail from every conversation logged in the card's notes. The notes are the enduring memory. When a card comes up in 3 months, all context is right there.
- **Intel extraction:** Pulls key facts from notes (pain points, competitors, loan types, timelines) into intel nuggets for during-call cheat sheets
- **Email drafting:** Writes emails in Jeff's voice based on instructions
- **Calendar management:** Places follow-ups based on the conversation
- **Disagreement:** If Jeff says "park him" but the prospect is showing buying signals, Anne says so
- **Qualitative learning:** References notes from won/lost deals to inform current suggestions

Implementation: Claude API with a system prompt that includes pipeline context, prospect details, note history, and Jeff's cadence rules. Card presentations can be pre-generated during morning brief prep (next 5-10 cards prepared in batch) to reduce latency during the processing loop. Routine card presentations use the most cost-effective model; strategy conversations and email drafting use the most capable model.

### 5.2 Voice Parser (`ai/parser.py`)

Underneath Anne. Turns conversation into structured database operations.

Understands:
- Sales vocabulary: "LV" = left voicemail, "callback" = they want a call back
- Relative dates: "in a few days" = 2-3 business days, "next week" = Monday
- Monthly buckets: "in March" = parked month 2026-03
- Population transitions: interest -> engaged, hard no -> DNC, "not yet" + timeframe -> parked
- Intel extraction: "she does fix and flip in Houston" -> loan types + market captured
- Data quality signals: "wrong number" -> flag phone suspect
- Navigation: skip, next, show me more, undo
- Actions: "send intro email", "schedule demo", "pull up John Smith", "dial him"

### 5.3 Disposition Engine (`ai/disposition.py`)

Every prospect interaction ends with one of three outcomes:
- **WON:** Deal closed. Capture value, date, notes. Celebrate.
- **OUT:** Dead/DNC (permanent), Lost (may revisit), or Parked (specific month).
- **ALIVE:** Still in play. Must have a follow-up date. No orphans. Anne enforces this.

### 5.4 AI Copilot (`ai/copilot.py`)

Deeper conversational mode. "Anne, what's our pipeline looking like?" or "What's the story with ABC Lending?" or "I've got a demo tomorrow, what should I know?" Scoped to Nexys sales, full pipeline access.

### 5.5 Rescue Engine (`ai/rescue.py`)

Zero-capacity mode. Anne generates the absolute minimum: "Just do these 3 things. Everything else can wait." Simplified interface, lowest friction.

### 5.6 Style Learner (`ai/style_learner.py`)

Jeff provides a curated set of his best sent emails (10-15 examples). These are stored locally and included in Anne's prompt when drafting emails. Simple, reliable, and Jeff's voice from day one. No automated scraping needed.

### 5.7 Card Story (`ai/card_story.py`)

Narrative context per prospect, generated from notes. "You first called John in November. He was interested but said Q1 was too early. You parked him for March. March is here. Last time, he mentioned evaluating three vendors."

### 5.8 Contact Analyzer (`ai/contact_analyzer.py`)

Engagement pattern analysis across companies. Identifies which contacts are advancing, which are stalling.

### 5.9 Prospect Insights (`ai/insights.py`)

Per-prospect strategic suggestions: best approach, likely objections, competitive vulnerabilities.

### 5.10 Proactive Interrogation

Anne reviews cards during the morning brief generation (not real-time, not expensive):
- Cards with no follow-up date
- Engaged leads that haven't moved in 2+ weeks
- High-score prospects with low data confidence
- Follow-up dates that already passed

Findings surface in the morning brief and when the card comes up in the queue.

---

## LAYER 6: THE HEARTBEAT

*The system breathes while Jeff sleeps.*

### 6.1 Nightly Cycle (`autonomous/nightly.py`)

Runs 2:00 AM - 7:00 AM via Windows Task Scheduler:

1. Take database backup (local + cloud sync)
2. Pull new prospects from ActiveCampaign
3. Run dedup against master database (with DNC protection)
4. Assess new records -> Broken or Unengaged
5. Run autonomous research on Broken prospects (free sources, 90% rule)
6. Run Groundskeeper: flag stale data for manual review
7. Re-score all active prospects
8. Check monthly buckets -> prepare activations if first business day
9. Draft nurture email sequences (queued for Jeff's batch approval, not auto-sent)
10. Pre-generate morning brief + card presentations for first 10 cards
11. Extract intel nuggets from recent notes for call-mode cheat sheets

**Missed cycle recovery:** If the laptop was powered off or the nightly cycle was interrupted, the system detects this on app launch (checks a last_nightly_run timestamp). If the cycle didn't complete, the system runs a condensed version: backup, monthly bucket activation check, morning brief generation. Research, nurture, and scoring run in background after launch. The morning brief notes: "Nightly cycle missed â€” running catch-up now." Jeff is never left without a brief because his laptop was off at 2 AM.

### 6.2 Orchestrator (`autonomous/orchestrator.py`)

The conductor. Coordinates all background tasks.

Registered tasks:
- Reply scanning: every 30 minutes (Outlook polling)
- Nurture emails: every 4 hours (daily caps)
- Demo prep: hourly (for upcoming demos)
- Calendar sync: hourly (Outlook -- â€” IronLung)

**The orchestrator starts automatically when the GUI launches AND can run headless via Task Scheduler.** This is non-negotiable.

### 6.3 Background Scheduler (`autonomous/scheduler.py`)

Windows Task Scheduler integration. Starts orchestrator on boot. Runs nightly cycle. Graceful shutdown.

### 6.4 Reply Monitor (`autonomous/reply_monitor.py`)

Inbox polled every 30 minutes. Replies classified: interested, not_interested, ooo, referral, unknown. Matched to prospect. Stored with full email content for inline display. No auto-promotion â€” interested replies are flagged and surfaced in the morning brief for Jeff to review. Jeff decides whether to promote to Engaged. This prevents misclassification from creating bad sales interactions (e.g., a brush-off classified as interest leads to an unwanted callback).

### 6.5 Email Sync (`autonomous/email_sync.py`)

Synchronizes email history between Outlook and the database. Sent and received emails stored in activity history for inline display on cards.

### 6.6 Activity Capture (`autonomous/activity_capture.py`)

Automatic detection and logging of email activity.

### 6.7 Auto-Replenish

When unengaged pool runs low, auto-pull from ActiveCampaign. Anne mentions it in the morning brief.

---

## LAYER 7: THE SOUL

*The ADHD-specific UX that makes this a cognitive prosthetic.*

### 7.1 Dopamine Engine (`gui/adhd/dopamine.py`)

Every micro-win gets a hit. Streaks tracked. Celebrations at 5, 10, 20. Achievements: First Call, First Demo, First Close, Power Hour (20+ calls in 60 min), Queue Cleared, Perfect Day.

### 7.2 Session Manager (`gui/adhd/session.py`)

- Time tracking with warnings (time blindness protection)
- Energy level: HIGH before 2 PM, MEDIUM 2-4 PM, LOW after 4 PM
- Auto low-energy mode after 2 PM (reduced cognitive load)
- Undo history (last 5 actions)
- Session recovery after crashes

### 7.3 Focus Mode (`gui/adhd/focus.py`)

Distraction-free processing. Current card fills the screen. Queue hidden. Only: card, dictation bar, action buttons. Tunnel vision.

### 7.4 Audio Feedback (`gui/adhd/audio.py`)

Sounds for every action. Confirmation tones. Different sounds for different outcomes.

### 7.5 Command Palette (`gui/adhd/command_palette.py`)

Ctrl+K. Fuzzy search across all tabs, prospects, and actions.

### 7.6 Glanceable Dashboard (`gui/adhd/dashboard.py`)

One-second read of today's progress. Small widget.

### 7.7 Compassionate Messages (`gui/adhd/compassion.py`)

No guilt trips. "Welcome back. Here are the 3 most important things."

---

## OFFLINE DEGRADATION

The system has three tiers based on connectivity:

**Full connectivity:** Everything works. Anne is live. Emails send. Bria dials. Outlook syncs.

**No internet:** Anne goes silent. Dictation Bar switches to manual mode â†’ Jeff types notes directly, they log without AI parsing. Cards browsable (SQLite is local). Manual dropdown selectors replace voice-driven disposition. Phone numbers display but click-to-call copies to clipboard instead.

**Reconnection:** System syncs. Notes added offline get timestamped and logged. Status changes take effect. Anne wakes up: "I see you worked 6 cards while I was offline. Want me to review your notes?"

Design principle: **SQLite is always available.** The GUI never crashes because an API call failed. Every API-dependent feature has a graceful fallback.

---

## BUILD ORDER: SEVEN PHASES

Each phase produces a usable tool. You can stop at any phase and have something that works.

### PHASE 1: THE SLAB + DATA IN
*"I have a database with my contacts in it."*

Build:
- SQLite database + full schema including intel_nuggets and research_queue (Layer 1)
- Data models, enumerations, timezone lookup tables (Layer 1)
- Config, logging, exceptions (Layer 1)
- Backup system (Layer 1)
- CSV importer with column mapping, dedup, and DNC protection (Layer 2)
- Basic GUI shell â†’ Import tab and Pipeline tab with multi-select and bulk actions (Layer 4)

Milestone: Jeff imports his CSV files. All contacts live in SQLite with correct populations assigned. Bulk operations work. Backup runs. DNC records are protected.

### PHASE 2: THE DAILY GRIND
*"I sit down and the system tells me who to call."*

Build:
- Today tab with morning brief dialog (Layer 4)
- Morning brief -> queue transition ("Ready? Let's go.") (Layer 4)
- Prospect card: glance view, deep dive, company context panel (Layer 4)
- Processing loop â†’ keyboard input first (Layer 4)
- Population logic and all transitions (Layer 3)
- Both cadence systems with attempt tracking (Layer 3)
- Scoring algorithm with manual weights (Layer 3)
- Queue prioritization: engaged first, timezone-ordered, unengaged by score (Layer 3)
- Calendar tab: day view, week view (Layer 4)
- Broken Prospects tab: three sections (confirm, in progress, manual research) (Layer 4)
- End-of-day summary (Layer 4)
- Settings tab (Layer 4)
- Keyboard shortcuts (Layer 4)
- Quick lookup for inbound calls (Layer 4)

Milestone: Jeff opens the app, reads the brief, hits "let's go," processes cards with correct cadence logic, sees the calendar, reviews broken records. The system breathes manually.

### PHASE 3: THE COMMUNICATOR
*"The system sends my emails and dials my phone."*

Build:
- Outlook integration â†’ send, receive, calendar sync (Layer 2)
- Bria integration â†’ click-to-call (Layer 2)
- Email template system including demo invite template (Layer 3)
- AI email generator (Layer 3)
- Demos tab with invite creator, prep docs, post-demo tracking (Layer 4)
- One-off email from cards (Layer 4)
- Inline email history on cards (Layer 4)
- Demo prep generator (Layer 3)
- Call Mode view on cards (cheat sheet during calls) (Layer 4)
- Email recall (Layer 4)
- Data export: CSV from Pipeline tab + monthly summary report (Layer 3)
- Closed Won flow: deal value, close date, notes, commission calc (Layer 4)

**DRY_RUN=false.** Emails send. Bria dials. No simulation.

Milestone: Jeff sends emails, clicks to call through Bria, creates demo invites, sees email history on cards, has a cheat sheet during calls, exports data, and tracks closed deals.

### PHASE 4: ANNE
*"I'm talking to my assistant and she handles everything."*

Build:
- Anne core conversational engine (Layer 5)
- Dictation Bar â†’ persistent on every tab (Layer 4)
- Voice parser underneath Anne (Layer 5)
- Disposition engine (WON / OUT / ALIVE) (Layer 5)
- Obsessive note-taking + intel nugget extraction (Layer 5)
- Skip, defer, undo mechanics (Layer 4)
- Confirmation step before execution (Layer 4)
- Parser failure modes (Layer 5)
- Card story generator (Layer 5)
- Style learner with curated email examples (Layer 5)
- Pre-generation of card presentations for latency reduction (Layer 5)
- Offline fallback: manual mode when Anne is unavailable (Layer 4)

Milestone: Jeff processes his entire daily queue by conversation. Anne presents cards with opinions, they discuss, Jeff decides, Anne executes and takes obsessive notes. The cognitive prosthetic is operational.

### PHASE 5: THE AUTONOMY
*"It works while I sleep."*

Build:
- Nightly cycle with all 11 steps (Layer 6)
- Orchestrator â†’ **actually starts** (Layer 6)
- Autonomous research for broken prospects (free sources, 90% rule, honest expectations) (Layer 3)
- Groundskeeper â†’ flag stale data (Layer 3)
- Nurture engine wired to Outlook (Layer 3 + Layer 2)
- Reply monitoring via polling (Layer 6)
- Email sync (Layer 6)
- Activity capture (Layer 6)
- Monthly bucket auto-activation (Layer 3)
- Auto-replenish pipeline (Layer 6)
- Windows Task Scheduler deployment (Layer 6)
- Pre-generation of morning brief + first 10 card presentations overnight (Layer 6)

Milestone: Jeff goes to bed. System backs up, researches broken records, flags stale data, sends nurture emails, monitors replies, scores prospects, activates monthly buckets, and generates tomorrow's brief with card presentations ready. The Iron Lung breathes on its own.

### PHASE 6: THE SOUL
*"It understands my brain."*

Build:
- Dopamine engine (Layer 7)
- Session manager with energy tracking (Layer 7)
- Focus mode (Layer 7)
- Audio feedback (Layer 7)
- Command palette (Layer 7)
- Glanceable dashboard (Layer 7)
- Compassionate messages (Layer 7)
- Rescue engine + rescue session UI (Layer 5)
- Troubled Cards tab (Layer 4)
- Intel Gaps tab (Layer 4)
- Bug/suggestion capture (Layer 4)
- Setup wizard

Milestone: Low-energy mode at 3 PM. Streaks celebrated. No guilt trips. Crisis mode available.

### PHASE 7: THE WEAPONS
*"It makes me dangerous."*

Build:
- AI copilot with full pipeline strategy (Layer 5)
- Anne can manipulate records directly via conversation (Layer 5)
- Contact analyzer (Layer 5)
- Prospect insights (Layer 5)
- Learning engine reading notes for qualitative patterns (Layer 3)
- Intervention engine (Layer 3)
- Proactive card interrogation during brief generation (Layer 5)
- Analytics tab with revenue/commission tracking (Layer 4)
- Dead lead resurrection audit (12+ months) (Layer 3)
- Partnership promotion workflow (Layer 4)
- Nexys contract generator integration (Layer 5)
- Cost tracking refinement (Layer 1)

Milestone: Anne learns from every deal's notes, interrogates every card during brief prep, generates strategic insights, and references qualitative patterns. The system makes Jeff lethal.

---

## FILE STRUCTURE

```
ironlung3/
|-- ironlung3.py # Single entry point
|-- requirements.txt
|-- install.bat
|-- README.md
|-- config/
| |-- .env # API keys, credentials
| +-- settings.py # Feature flags, cadence rules, commission rate
|-- data/
| |-- backups/ # Nightly backups
| +-- style_examples/ # Jeff's curated email examples for style learner
|-- templates/
| +-- emails/ # Jinja2 templates (intro, follow-up, demo invite, nurture, breakup)
|-- src/
| |-- core/
| | |-- config.py # Configuration management
| | |-- exceptions.py # Custom exception hierarchy
| | |-- logging.py # Structured logging
| | +-- tasks.py # Thread/task management
| |-- db/
| | |-- database.py # SQLite connection + CRUD + timezone lookup
| | |-- models.py # Dataclasses + enums (incl. AttemptType, IntelNugget)
| | |-- backup.py # Backup system
| | +-- intake.py # Dedup + DNC protection + import logic
| |-- integrations/
| | |-- base.py # Base integration class
| | |-- outlook.py # Microsoft Graph (email + calendar, polling)
| | |-- bria.py # Bria softphone dialer (tel:/sip: URI)
| | |-- activecampaign.py # AC API client
| | |-- google_search.py # Google Custom Search (free tier)
| | |-- csv_importer.py # File import with mapping + presets
| | +-- email_importer.py # Email CSV import for card enrichment
| |-- engine/
| | |-- populations.py # Population definitions + transition rules
| | |-- cadence.py # Dual cadence: system-paced + prospect-paced
| | |-- scoring.py # 0-100 scoring (manual weights)
| | |-- research.py # Autonomous research (90% rule, free sources only)
| | |-- groundskeeper.py # Data maintenance (flag, don't auto-verify)
| | |-- nurture.py # Email sequence logic
| | |-- learning.py # Note-driven qualitative pattern detection
| | |-- intervention.py # Decay detection + alerts
| | |-- templates.py # Jinja2 email templates (incl. demo invite)
| | |-- email_gen.py # AI email drafting (Jeff's voice)
| | |-- demo_prep.py # Demo preparation docs
| | +-- export.py # CSV export + monthly summary report
| |-- ai/
| | |-- anne.py # Anne: conversational engine (THE product)
| | |-- parser.py # Structured action extraction
| | |-- disposition.py # WON / OUT / ALIVE engine
| | |-- copilot.py # Strategic conversation mode
| | |-- rescue.py # Crisis-mode engine
| | |-- style_learner.py # Curated email examples -> Jeff's voice
| | |-- card_story.py # Narrative context per prospect
| | |-- insights.py # Per-prospect strategic suggestions
| | +-- contact_analyzer.py # Engagement pattern analysis
| |-- autonomous/
| | |-- nightly.py # Nightly cycle (11 steps)
| | |-- orchestrator.py # Background task coordinator (STARTS AUTOMATICALLY)
| | |-- scheduler.py # Windows Task Scheduler setup
| | |-- reply_monitor.py # Inbox polling + classification
| | |-- email_sync.py # Email history synchronization
| | +-- activity_capture.py # Auto activity detection
| |-- gui/
| | |-- app.py # Main application window (ONE gui)
| | |-- theme.py # Visual theme
| | |-- dictation_bar.py # Persistent input (Anne's interface + offline fallback)
| | |-- cards.py # Prospect card: glance, call mode, deep dive
| | |-- shortcuts.py # Keyboard shortcut bindings
| | |-- tabs/
| | | |-- today.py # Primary work surface (Anne-led processing)
| | | |-- broken.py # Three-section workbench (confirm/in-progress/manual)
| | | |-- pipeline.py # Full DB: filter, search, multi-select, bulk ops, export
| | | |-- calendar.py # Day + week views, Outlook-integrated
| | | |-- demos.py # Invite creator + tracking
| | | |-- partnerships.py # Non-prospect contacts
| | | |-- import_tab.py # Upload + mapping + DNC protection preview
| | | |-- settings.py # Config + backup + cadence rules + commission
| | | |-- troubled.py # Problem cards queue
| | | |-- intel_gaps.py # Missing info audit
| | | +-- analytics.py # Numbers + revenue + commission + export
| | |-- dialogs/
| | | |-- morning_brief.py # Brief dialog with "Ready? Let's go." transition
| | | |-- edit_prospect.py
| | | |-- import_preview.py # Shows DNC blocks in red
| | | |-- quick_action.py
| | | |-- closed_won.py # Deal value + close date + notes
| | | +-- email_recall.py
| | +-- adhd/
| | |-- dopamine.py # Streaks + achievements
| | |-- session.py # Timing + energy + recovery
| | |-- focus.py # Distraction-free mode
| | |-- audio.py # Sound feedback
| | |-- command_palette.py # Ctrl+K
| | |-- dashboard.py # Glanceable status
| | +-- compassion.py # Compassionate messaging
| +-- content/
| |-- morning_brief.py # Brief generation (Anne's morning memo)
| |-- daily_cockpit.py # Real-time dashboard data
| +-- eod_summary.py # End-of-day stats
+-- tests/
 |-- test_db.py
 |-- test_engine.py
 |-- test_integrations.py
 |-- test_ai.py
 |-- test_gui.py
 +-- test_autonomous.py

```

---

## TECHNICAL DECISIONS

### What Stays
- Python + tkinter (Windows desktop, proven)
- SQLite (local, zero infrastructure)
- Claude API for Anne and all AI features
- Microsoft Graph API for Outlook
- Jinja2 email templates
- Structured JSON logging
- Custom exception hierarchy
- Environment variable configuration

### What's Honest
- **Autonomous research finds 20-30% of missing data.** Not 50-60%. The rest needs Jeff.
- **Confidence scoring is simple rules, not percentages.** "Found on company website with name" = auto-fill. Everything else = suggest.
- **Learning engine reads notes, not statistics.** Works from day one. No data threshold needed.
- **Style learner uses curated examples.** Not automated scraping. Jeff picks his best 10-15 emails.
- **No SMTP verification.** Most providers block it now. Jeff handles email validation via his CSV workflow.
- **Polling, not webhooks.** Desktop apps can't receive push notifications. Every 30 minutes is fine.
- **Anne's latency managed via pre-generation.** Card presentations prepared in batch during nightly cycle and between cards. Not truly real-time, but fast enough.
- **Scoring weights are manual.** Auto-tuning needs 12+ months of data.

### What's Gone
- Trello â†’ anything. Not even a migration source.
- LinkedIn integration â†’ impossible to automate reliably
- SMTP email verification â†’ providers block it
- Persistent AI memory bank / RAG â†’ notes are the memory
- Statistical learning engine â†’ notes-based qualitative learning instead
- Twilio â†’ Bria is simpler
- Paid enrichment APIs (Hunter.io, Apollo, Clay, ZoomInfo)
- Outlook webhooks â†’ polling instead
- DRY_RUN mode as default
- Dual implementations of anything
- Multiple entry points

---

## THE DESTINATION

Jeff sits down. Anne says good morning and tells him what matters in 60 seconds. He says "let's go." Anne presents the first card. They talk. They decide. Anne executes and writes meticulous notes. Next card. Twenty seconds each. Thirty-five prospects before lunch.

When the phone rings, Anne pulls up the caller in two seconds and puts a cheat sheet on screen. When a demo needs scheduling, one sentence and the invite sends. When an email needs writing, Jeff dictates the gist and Anne writes it in his voice.

When Jeff goes to bed, the system backs up, researches broken records, flags stale data, sends nurture emails, monitors replies, scores prospects, and writes tomorrow's brief with the first ten card presentations ready to go. When a parked prospect's month arrives, they reappear in the queue. When a reply comes in at midnight, it's classified and waiting in the morning brief.

When Jeff is having a bad day, Anne doesn't guilt-trip him. She says "here are the 3 things that matter" and makes them as easy as possible. When Jeff is on fire, Anne feeds him unlimited prospects and celebrates every streak.

When the internet goes down, the system keeps working â†’ just quieter.

The Iron Lung breathes.

---

**Version:** 3.2
**Date:** February 5, 2026
**Author:** Claude (Anthropic)
**For:** Jeff Soderstrom, Nexys LLC
**Status:** Definitive architectural blueprint. Stripped of impossibles. Honest about limitations. Ready to build.

**v3.1 changes (root fixes before construction):**
- Activities schema: added stage_before/stage_after for independent tracking of engagement stage transitions
- Population transitions: separated into population transitions and engagement stage transitions; added Unengaged -> Broken (data degraded)
- Normalization: strip list reduced to pure legal suffixes only; identity terms (Holdings, Capital, Group, Partners, Financial, Services) preserved
- Notes architecture: clarified prospect.notes (static context) vs activity.notes (running log â†’ the enduring memory)
- Exception hierarchy: added DatabaseError, ActiveCampaignError, ImportError_, DNCViolationError
- Closed Won transition: accessible from any engaged stage, not just Warming Tray

**v3.2 changes (red team findings + feature walkthrough):**
- Tags: added prospect_tags table for user-defined labels on top of populations; filterable, visible on cards, bulk-applicable, no transition rules
- Reply monitor: removed auto-promotion to Engaged; interested replies flagged and surfaced in morning brief for Jeff to decide
- DNC 24-hour grace period: DNC transitions reversible within 24 hours (logged with reason), permanent after
- Missed nightly cycle recovery: app launch detects missed cycle, runs condensed catch-up (backup, bucket activation, brief generation)
- Dictation bar: renamed from "voice bar" throughout; it's a text input that receives dictation, not a voice interface
- Email CSV importer: new integration (2.7) for importing sent/inbox email exports to enrich prospect cards before Graph API is built
- Nurture engine: changed from auto-send to draft-and-queue; emails queued for Jeff's batch approval before sending
- Overdue rollover rule: explicit guarantee that missed follow-ups carry forward (query uses <= today), overdue items surface first with days-overdue flag
- Nightly cycle step 9: updated to reflect draft-and-queue instead of auto-send
