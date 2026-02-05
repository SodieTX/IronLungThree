# Layer 5: The Brain (Anne)

**Conversational AI**

Version: 1.0  
Date: February 5, 2026  
Parent: Blueprint v3.2

---

## Overview

Anne is the product. Everything else is plumbing.

Anne is the Anne Hathaway to Jeff's Anna Wintour. She's done her homework on every card before Jeff sees it. She presents prospects one at a time with context and a preliminary read. They have a 15-30 second conversation about each. Anne can suggest, push back, even disagree. Then whatever they decide, Anne executes.

**Components:**
- Anne Core (`ai/anne.py`)
- Voice Parser (`ai/parser.py`)
- Disposition Engine (`ai/disposition.py`)
- AI Copilot (`ai/copilot.py`)
- Rescue Engine (`ai/rescue.py`)
- Style Learner (`ai/style_learner.py`)
- Card Story (`ai/card_story.py`)
- Prospect Insights (`ai/insights.py`)
- Contact Analyzer (`ai/contact_analyzer.py`)

---

## Anne Core (`ai/anne.py`)

### Capabilities

| Capability | Description |
|------------|-------------|
| Pipeline awareness | Sees all prospects, statuses, history |
| Card presentation | Name, company, context, history, recommendation |
| Conversation | Discuss, answer questions, offer opinions, push back |
| Obsessive note-taking | Every detail logged. Notes ARE the memory. |
| Intel extraction | Pull key facts for during-call cheat sheets |
| Email drafting | Write emails in Jeff's voice |
| Calendar management | Place follow-ups based on conversation |
| Disagreement | Challenge bad decisions when warranted |
| Qualitative learning | Reference won/lost notes for suggestions |

### Card Presentation Format

```
"John Smith, ABC Lending. Bridge and fix-and-flip out of Houston. 
This is attempt three — you left voicemails Monday and the Thursday 
before. No callback.

His company's doing volume — they closed 40 loans last quarter 
according to their site. He's worth pursuing. But three voicemails 
with no callback isn't working.

Want to switch to email? Or park him and try fresh in a month?"
```

### Anne's Rules

1. Always present the card first (name, company, context, history, suggestion)
2. Never execute without Jeff's confirmation
3. Allowed to disagree ("Are you sure? He's showing buying signals.")
4. Draft emails in Jeff's voice, not robot voice
5. Dial the phone when Jeff says dial
6. Handle all filing, calendaring, note-taking after disposition

### Implementation

- Claude API with system prompt
- Pipeline context, prospect details, note history, cadence rules
- Pre-generated presentations for latency reduction
- Cost-effective model for routine, capable model for strategy

### Functions

```python
def present_card(prospect_id: int) -> str:
    """Generate card presentation with context and recommendation."""

def respond(user_input: str, context: ConversationContext) -> AnneResponse:
    """Process user input, return response and suggested actions."""

def execute_actions(actions: list[Action]) -> ExecutionResult:
    """Execute confirmed actions (log, update, email, etc.)."""

def pre_generate_cards(prospect_ids: list[int]) -> dict[int, str]:
    """Batch-generate card presentations for queue."""
```

---

## Voice Parser (`ai/parser.py`)

Turns conversation into structured database operations.

### Understanding

| Category | Examples |
|----------|----------|
| Sales vocab | "LV" = left voicemail, "callback" = they want a call back |
| Relative dates | "in a few days" = 2-3 business days, "next week" = Monday |
| Monthly buckets | "in March" = parked month 2026-03 |
| Population transitions | interest → engaged, hard no → DNC |
| Intel extraction | "she does fix and flip in Houston" → loan types + market |
| Data quality | "wrong number" → flag phone suspect |
| Navigation | skip, next, show me more, undo |
| Actions | "send intro email", "schedule demo", "dial him" |

### Functions

```python
def parse(input: str, context: ParserContext) -> ParseResult:
    """Parse input into structured actions."""

def extract_intel(input: str, prospect_id: int) -> list[IntelNugget]:
    """Extract intel nuggets from conversation."""
```

---

## Disposition Engine (`ai/disposition.py`)

### Three Outcomes

Every prospect interaction ends with one of:

| Outcome | Description | Requirements |
|---------|-------------|--------------|
| **WON** | Deal closed | Capture value, date, notes |
| **OUT** | Dead/DNC, Lost, or Parked | Reason required |
| **ALIVE** | Still in play | MUST have follow-up date |

### No Orphans

Anne enforces: engaged prospects MUST have a follow-up date.

"He's engaged but you didn't set a follow-up date. That's an orphan. When should we call?"

### Functions

```python
def determine_disposition(conversation: Conversation) -> Disposition:
    """Determine disposition from conversation."""

def validate_disposition(disposition: Disposition) -> list[str]:
    """Validate disposition. Returns issues (empty = valid)."""
```

---

## AI Copilot (`ai/copilot.py`)

Deeper conversational mode for strategy questions.

### Example Queries

- "Anne, what's our pipeline looking like?"
- "What's the story with ABC Lending?"
- "I've got a demo tomorrow, what should I know?"

### Scope

- Nexys sales context
- Full pipeline access
- Historical patterns

### Functions

```python
def ask(question: str) -> str:
    """Answer strategic question about pipeline."""
```

---

## Rescue Engine (`ai/rescue.py`)

Zero-capacity mode for bad days.

### Behavior

- Generates absolute minimum: "Just do these 3 things"
- Simplified interface
- Lowest friction
- No guilt trips

### Functions

```python
def generate_rescue_list() -> list[RescueItem]:
    """Generate minimal must-do list for low-capacity day."""
```

---

## Style Learner (`ai/style_learner.py`)

### Curated Examples

Jeff provides 10-15 of his best sent emails. These are:
- Stored locally in `data/style_examples/`
- Included in Anne's prompt when drafting
- Used to match Jeff's voice from day one

No automated scraping. Simple and reliable.

### Functions

```python
def load_examples() -> list[str]:
    """Load Jeff's email examples."""

def get_style_prompt() -> str:
    """Generate style guidance for email drafting."""
```

---

## Card Story (`ai/card_story.py`)

Narrative context per prospect, generated from notes.

### Example Output

```
"You first called John in November. He was interested but said Q1 
was too early. You parked him for March. March is here. Last time, 
he mentioned evaluating three vendors."
```

### Functions

```python
def generate_story(prospect_id: int) -> str:
    """Generate narrative from prospect history."""
```

---

## Prospect Insights (`ai/insights.py`)

Per-prospect strategic suggestions.

### Content

- Best approach based on history
- Likely objections
- Competitive vulnerabilities
- Timing recommendations

### Functions

```python
def generate_insights(prospect_id: int) -> ProspectInsights:
    """Generate strategic insights for prospect."""
```

---

## Contact Analyzer (`ai/contact_analyzer.py`)

Engagement pattern analysis across companies.

### Analysis

- Which contacts are advancing
- Which are stalling
- Multi-contact coordination

### Functions

```python
def analyze_company(company_id: int) -> CompanyAnalysis:
    """Analyze engagement patterns at company."""
```

---

## Proactive Interrogation

Anne reviews cards during morning brief generation:

- Cards with no follow-up date
- Engaged leads with no movement in 2+ weeks
- High-score prospects with low data confidence
- Follow-up dates that already passed

Findings surface in morning brief and when card comes up.

---

## Build Phases

- **Phase 4**: Anne core, parser, disposition, style learner (Steps 4.1-4.10)
- **Phase 7**: Copilot, insights, contact analyzer, learning (Steps 7.1-7.7)

---

## Performance Targets

| Operation | Target |
|-----------|--------|
| Card presentation (pre-generated) | < 500ms |
| Card presentation (live) | < 3 seconds |
| Response to input | < 2 seconds |
| Email draft | < 5 seconds |

---

## Offline Behavior

When Claude API unavailable:
- Anne goes silent
- Dictation Bar switches to manual mode
- Notes log directly without AI parsing
- Manual dropdowns for status changes
- System reconnects when API returns

---

**See also:**
- `LAYER-4-FACE.md` - Dictation Bar integration
- `LAYER-6-HEARTBEAT.md` - Pre-generation during nightly cycle
- `../patterns/ERROR-HANDLING.md` - API failure handling
