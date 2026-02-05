# Layer 3: The Engine

**Business Logic**

Version: 1.0  
Date: February 5, 2026  
Parent: Blueprint v3.2

---

## Overview

Layer 3 contains all business logic - how prospects move through the pipeline, how scoring works, how cadence is managed. Pure logic, no GUI code.

**Components:**
- Population Manager (`engine/populations.py`)
- Cadence Engine (`engine/cadence.py`)
- Scoring Algorithm (`engine/scoring.py`)
- Intake Funnel (`db/intake.py`) - lives in db/ but logic is engine
- Autonomous Research (`engine/research.py`)
- Groundskeeper (`engine/groundskeeper.py`)
- Nurture Logic (`engine/nurture.py`)
- Learning Engine (`engine/learning.py`)
- Intervention Engine (`engine/intervention.py`)
- Email Templates (`engine/templates.py`)
- Email Generator (`engine/email_gen.py`)
- Demo Prep (`engine/demo_prep.py`)
- Data Export (`engine/export.py`)

---

## Population Manager (`engine/populations.py`)

### Valid Transitions

```
BROKEN → UNENGAGED (when fixed)
UNENGAGED → BROKEN (data degraded)
UNENGAGED → ENGAGED (showed interest)
UNENGAGED → PARKED ("call me in June")
UNENGAGED → DNC ("don't ever call me")
UNENGAGED → LOST (chose competitor before engagement)
ENGAGED → PARKED ("not right now")
ENGAGED → DNC
ENGAGED → LOST
ENGAGED → CLOSED_WON (from any stage)
PARKED → UNENGAGED (month arrived)
LOST → UNENGAGED (resurrection, 12+ months, Jeff's decision)
PARTNERSHIP → UNENGAGED or ENGAGED (promotion)
```

### Invalid Transitions

```
DNC → anything (EVER)
CLOSED_WON → anything (it's done)
```

### Engagement Stage Transitions

Within ENGAGED population only:
```
pre_demo → demo_scheduled
demo_scheduled → post_demo
post_demo → closing
```

### Functions

```python
def can_transition(from_pop: Population, to_pop: Population) -> bool:
    """Check if transition is valid."""

def transition_prospect(
    prospect_id: int,
    to_population: Population,
    reason: str = None,
    to_stage: EngagementStage = None
) -> bool:
    """Execute transition with activity logging."""

def transition_stage(
    prospect_id: int,
    to_stage: EngagementStage,
    reason: str = None
) -> bool:
    """Change engagement stage within ENGAGED."""
```

---

## Cadence Engine (`engine/cadence.py`)

### Two Cadence Systems

**Unengaged (System-Paced):**
| Attempt | Channel | Wait Before Next |
|---------|---------|------------------|
| 1 | Call | 3-5 business days |
| 2 | Call | 5-7 business days |
| 3 | Email | 7-10 business days |
| 4 | Combo | 10-14 business days |
| 5+ | Evaluate |

**Engaged (Prospect-Paced):**
- Date is what prospect said
- No algorithm - exact date stored
- No orphans allowed (must have follow-up date)

### Functions

```python
def calculate_next_contact(
    prospect_id: int,
    last_attempt_date: date,
    attempt_number: int
) -> date:
    """Calculate next contact date for unengaged prospect."""

def set_follow_up(
    prospect_id: int,
    follow_up_date: datetime,
    reason: str = None
) -> bool:
    """Set follow-up date (engaged cadence)."""

def get_orphaned_engaged() -> list[int]:
    """Return IDs of engaged prospects with no follow-up date."""

def get_overdue() -> list[Prospect]:
    """Return prospects with follow_up_date < today."""
```

### Attempt Tracking

- `personal` - Jeff's direct outreach
- `automated` - System-sent nurture

Anne knows the difference: "This is attempt 4, but two were automated."

---

## Scoring Algorithm (`engine/scoring.py`)

### Score Components (0-100)

| Category | Weight | Factors |
|----------|--------|---------|
| Company Fit | 25% | Loan types, size, geography |
| Contact Quality | 20% | Title seniority, data completeness, verification |
| Engagement Signals | 25% | Responses, demo interest |
| Timing Signals | 15% | Budget cycle, recent contact |
| Source Quality | 15% | Where they came from |

### Functions

```python
def calculate_score(prospect: Prospect, company: Company) -> int:
    """Calculate prospect score 0-100."""

def calculate_confidence(prospect: Prospect, methods: list[ContactMethod]) -> int:
    """Calculate data confidence 0-100."""
```

### Manual Weights

Weights are tuned based on Jeff's sales intuition. No auto-tuning until 12+ months of data.

---

## Autonomous Research (`engine/research.py`)

### The 90% Rule

- **Auto-fill (90%+ confidence):** Found on company website with name match
- **Suggest (below 90%):** Shows Jeff what was found, he confirms

### Free Sources

1. Company website scraping (/about, /team, /contact)
2. Email pattern detection (firstname@domain, first.last@domain)
3. Google Custom Search (100/day free)
4. NMLS Lookup (free, for licensed lenders)

### Honest Expectations

Fixes 20-30% of broken records automatically. Not 50-60%.

### Functions

```python
def research_prospect(prospect_id: int) -> ResearchResult:
    """Run research on broken prospect."""

def scrape_company_site(domain: str) -> ScrapeResult:
    """Scrape company website for contact info."""

def detect_email_pattern(domain: str, first_name: str, last_name: str) -> list[str]:
    """Generate likely email patterns."""
```

---

## Groundskeeper (`engine/groundskeeper.py`)

### Stale Data Thresholds

| Field | Flag After | Method |
|-------|------------|--------|
| Email | 90 days | Flag for manual check |
| Phone | 180 days | Flag for manual check |
| Title | 120 days | Website re-scrape |
| Company | 180 days | Domain check |

### Functions

```python
def flag_stale_records() -> list[int]:
    """Flag records with stale data. Returns prospect IDs."""

def get_stale_by_priority() -> list[Prospect]:
    """Return stale records ordered by age × score."""
```

---

## Nurture Logic (`engine/nurture.py`)

### Sequences

| Sequence | Emails | Spacing | Purpose |
|----------|--------|---------|---------|
| Warm Touch | 3 | 7 days | Initial engagement |
| Re-engagement | 2 | 14 days | Went quiet after interest |
| Breakup | 1 | N/A | Final email |

### Draft-and-Queue Model

Emails are drafted and queued for Jeff's batch approval, NOT auto-sent.

### Functions

```python
def generate_nurture_batch(limit: int = 30) -> list[NurtureEmail]:
    """Generate nurture emails for batch approval."""

def approve_email(email_id: int) -> bool:
    """Approve email for sending."""

def send_approved_emails() -> int:
    """Send all approved emails. Returns count sent."""
```

---

## Learning Engine (`engine/learning.py`)

### Note-Driven Intelligence

Reads notes on won and lost deals for qualitative patterns:
- "Lost to LoanPro because of price"
- "Closed because they loved the borrower portal"

### Functions

```python
def analyze_outcomes() -> LearningInsights:
    """Analyze won/lost notes for patterns."""

def get_suggestions_for_prospect(prospect_id: int) -> list[str]:
    """Get suggestions based on historical patterns."""
```

Works from day one with even a handful of closed deals.

---

## Intervention Engine (`engine/intervention.py`)

### Decay Detection

- Overdue follow-ups
- Stale engaged leads (no movement in 2+ weeks)
- Unworked cards
- High-score prospects with low data confidence

### Functions

```python
def detect_decay() -> DecayReport:
    """Run decay detection. Returns issues by category."""
```

---

## Email Templates (`engine/templates.py`)

### Template Types

- intro - First contact
- follow_up - General follow-up
- demo_confirmation - Demo scheduled confirmation
- demo_invite - Demo invitation with Teams link
- nurture_1, nurture_2, nurture_3 - Warm Touch sequence
- breakup - Final attempt

### Functions

```python
def render_template(
    template_name: str,
    prospect: Prospect,
    company: Company,
    **kwargs
) -> str:
    """Render email template with prospect data."""
```

---

## Email Generator (`engine/email_gen.py`)

AI-powered ad-hoc email drafting using Claude API.

### Functions

```python
def generate_email(
    prospect: Prospect,
    instruction: str,
    style_examples: list[str]
) -> str:
    """Generate email draft based on Jeff's instruction and style."""
```

---

## Demo Prep (`engine/demo_prep.py`)

### Generated Content

- Loan types
- Company size
- State/region
- Pain points from notes
- Competitive landscape from intel nuggets

### Functions

```python
def generate_prep(prospect_id: int) -> DemoPrep:
    """Generate demo preparation document."""
```

---

## Data Export (`engine/export.py`)

### Quick Export

Whatever Jeff is filtering in Pipeline tab → CSV

### Monthly Summary

- Demos booked
- Deals closed
- Deal values
- Commission earned
- Pipeline movement
- Calls made
- Emails sent

### Functions

```python
def export_prospects(prospects: list[Prospect], path: Path) -> bool:
    """Export prospects to CSV."""

def generate_monthly_summary(month: str) -> MonthlySummary:
    """Generate summary for YYYY-MM."""
```

---

## Build Phases

- **Phase 2**: Populations, Cadence, Scoring (Steps 2.1-2.4)
- **Phase 3**: Templates, Email Gen, Demo Prep, Export (Steps 3.4-3.10)
- **Phase 5**: Research, Groundskeeper, Nurture, Learning, Intervention (Steps 5.1-5.6)

---

**See also:**
- `LAYER-1-SLAB.md` - Database operations
- `../build/PHASE-2-GRIND.md` - Population/cadence build steps
- `../patterns/ERROR-HANDLING.md` - DNC violation handling
