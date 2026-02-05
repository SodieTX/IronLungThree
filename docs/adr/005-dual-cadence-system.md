# ADR 005: Dual Cadence System

## Status

Accepted

## Date

February 5, 2026

## Context

IronLung 3 needs to manage follow-up timing for prospects. The fundamental question: who controls when Jeff calls?

Some prospects have never talked to Jeff - he's chasing them. Other prospects have expressed interest and said "call me Thursday."

These are fundamentally different situations requiring different timing logic.

## Decision

We will implement **two completely separate cadence systems**:

1. **System-Paced (Unengaged)**: The system decides when to contact
2. **Prospect-Paced (Engaged)**: The prospect said when to call, we honor it exactly

## Rationale

### Why Two Systems

1. **Different control**: For unengaged prospects, Jeff decides cadence. For engaged prospects, the prospect already told us when.

2. **Different goals**: 
   - Unengaged: Stay on radar without being a stalker
   - Engaged: Honor commitments exactly (build trust)

3. **Different math**:
   - Unengaged: Configurable intervals based on attempt number
   - Engaged: Exact date prospect specified

4. **Different violations**:
   - Unengaged: Calling too soon is annoying
   - Engaged: Calling too late or early breaks trust

### System-Paced (Unengaged)

| Attempt | Channel | Wait Before Next |
|---------|---------|------------------|
| 1 | Call | 3-5 business days |
| 2 | Call | 5-7 business days |
| 3 | Email | 7-10 business days |
| 4 | Combo | 10-14 business days |
| 5+ | Evaluate |

Jeff never has to think "when did I last call this person?" The system knows.

### Prospect-Paced (Engaged)

- Prospect says "call me Wednesday" → follow-up IS Wednesday
- Prospect says "I need two weeks" → follow-up is 14 days out
- Prospect says "after our board meeting" → parked to that month

It's never intrusive because the prospect **invited** the call.

### Why Not One System

A single cadence system would either:
- Force arbitrary timing on engaged prospects (breaking trust)
- Or require manual override for every unengaged prospect (defeating automation)

The dual system lets automation handle the boring math while respecting explicit commitments.

## Consequences

### Positive

- Clear mental model: "Are they engaged? Then they control timing."
- Automation for the tedious part (unengaged cadence math)
- Trust-building for the important part (honoring commitments)
- No orphan engaged leads (system enforces follow-up date)

### Negative

- Two code paths to maintain
- Population transition affects cadence logic
- Must distinguish personal vs automated attempts

### Risks

- **Orphan engaged leads**: Mitigated by Anne flagging any engaged prospect without follow-up date
- **Cadence interval disputes**: Mitigated by making intervals configurable

## Implementation

### Attempt Tracking

Each attempt logged with:
- `attempt_type`: personal or automated
- System-sent nurture emails count as automated

Anne knows the difference: "This is attempt 4, but two were automated nurture emails."

### Follow-Up Date Field

`prospects.follow_up_date` is DATETIME (not DATE) to support:
- "Call him at 2 PM his time"
- Timezone-aware scheduling

### No Orphans Rule

If `population = 'engaged'` and `follow_up_date IS NULL`:
- Anne flags immediately
- Morning brief highlights
- Cannot save without setting date

## Related

- ADR 004: Notes as Memory (related prospect state)
- `../layers/LAYER-3-ENGINE.md` - Cadence engine specification
- `../SCHEMA-SPEC.md` - follow_up_date field definition
