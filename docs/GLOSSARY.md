# IronLung 3 Glossary

## Core Concepts

### Anne
The conversational AI assistant. Acts as a "body double" - presents context, takes instructions, handles the boring parts. Named Anne because she's helpful.

### Body Double
ADHD concept: having another person present helps maintain focus. Anne fills this role digitally.

### Card
A single prospect presented for processing. Contains glance view (summary), call view (during call), and deep dive (full history). Jeff processes cards one at a time.

### Cadence
Follow-up timing system. Two types:
- **System-paced:** Automatic intervals for Unengaged (7→14→21→30 days)
- **Prospect-paced:** Explicit dates set by Jeff for Engaged

### Cognitive Prosthetic
The system acts as an extension of Jeff's memory and executive function, handling what ADHD makes difficult.

### DNC (Do Not Contact)
Permanent, absolute, sacrosanct status. Records marked DNC can never be contacted again. The system protects against all violations.

### Dictation Bar
Persistent input widget at the bottom of every screen. Jeff speaks or types; Anne interprets and executes.

### Disposition
The outcome of processing a card: WON (became customer), OUT (dead/DNC), or ALIVE (continue following up).

### Dopamine Engine
ADHD-aware feedback system. Micro-wins, streaks, and celebrations provide the dopamine hits that keep Jeff engaged.

### Focus Mode
Distraction-free card processing. Hides everything except the current card and essential controls.

### Intake Funnel
Import processing pipeline. Performs deduplication, DNC matching, and data validation before records enter the database.

### Layer
One of seven architectural components, each with specific responsibilities. Layers depend only on layers below them.

### Morning Brief
AI-generated summary shown at session start. Includes pipeline stats, today's priorities, overnight changes, and any warnings.

### Nightly Cycle
11-step autonomous process running 2-7 AM: backup, sync, dedup, assess, research, score, bucket, nurture, and prep.

### Phase
One of seven build increments. Each phase produces a deployable tool and adds new capabilities.

### Pipeline
The full set of prospects being worked. Metaphor: prospects flow through stages toward becoming customers (or exiting).

### Population
Current status bucket for a prospect. One of: Broken, DNC, Dead, Unengaged, Engaged, Customer, Lost, Parked.

### Prospect
A potential customer being tracked. Has associated company, contact methods, activities, and notes.

### Queue
Ordered list of cards to process. Prioritized by score, engagement status, and time sensitivity.

### Rescue Mode
"Zero capacity" mode for when Jeff is overwhelmed. Shows only the single most important action with pre-written scripts.

## Populations

### Broken
Missing phone and email. Cannot be contacted until data is found. Autonomous research attempts to fix.

### Customer
Closed won. The goal state. Deal value and close date recorded.

### Dead
Company closed, person left, or otherwise unreachable. Different from DNC (voluntary vs. impossible).

### DNC (Population)
Requested no contact. Permanent. Protected by system safeguards.

### Engaged
Active conversation underway. In one of: Discovery, Demo Scheduled, Demo Completed, Proposal, Negotiation.

### Lost
Competitive loss. Reason and competitor recorded for learning.

### Parked
Deferred to specific month. "Call me in June" = Parked to June 2026.

### Unengaged
Has contact data, not yet engaged. System-paced follow-up.

## Engagement Stages

Only for Engaged population:

### Discovery
Initial conversations. Learning about needs, qualifying fit.

### Demo Scheduled
Demo meeting is on the calendar. Not yet occurred.

### Demo Completed
Demo happened. Evaluating next steps.

### Proposal
Formal proposal sent. Awaiting response.

### Negotiation
Active deal negotiation. Terms being finalized.

## Activity Types

### call_outbound
Jeff called the prospect.

### call_inbound
Prospect called Jeff.

### email_sent
Email sent to prospect.

### email_received
Email received from prospect.

### email_auto
System-generated email (nurture sequence).

### meeting
Video/in-person meeting.

### demo
Product demonstration.

### voicemail
Voicemail left or received.

### linkedin
LinkedIn message or activity.

### note
Internal note (no prospect-visible action).

### research
Research activity (finding contact data).

## Technical Terms

### ADR
Architecture Decision Record. Documents why a technical choice was made.

### CRUD
Create, Read, Update, Delete. Basic database operations.

### DDL
Data Definition Language. SQL for creating tables.

### Fixture
pytest concept: reusable test setup/data.

### JSON
JavaScript Object Notation. Data format used for logs and config.

### MSAL
Microsoft Authentication Library. Used for Outlook OAuth.

### OAuth
Authorization protocol. How IronLung authenticates to Outlook.

### Stub
Placeholder implementation that raises NotImplementedError.

### URI Scheme
Protocol for launching applications (e.g., `tel:` for phone calls, `bria:` for Bria).

## ADHD-Specific

### Compassionate Messages
System never guilt-trips. "You've been away" becomes "Welcome back, let's pick up where we left off."

### Energy Level
Time-based capacity indicator. HIGH (morning), MEDIUM (afternoon), LOW (evening).

### Micro-win
Small accomplishment that triggers dopamine. Processing a card, sending an email.

### Streak
Consecutive days of activity. Maintained for motivation.

### Time Blindness
ADHD symptom: difficulty perceiving time passage. System warns when sessions run long.

### Undo Stack
Quick reversal for impulsive actions. "That was wrong, undo."
