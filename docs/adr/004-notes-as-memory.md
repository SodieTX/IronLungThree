# ADR 004: Notes as Memory

## Status

Accepted

## Date

February 5, 2026

## Context

IronLung 3 needs Anne (the AI assistant) to remember context about prospects across conversations. When a prospect's card comes up 3 months later, Anne should recall the full history.

Options considered:
1. **RAG (Retrieval-Augmented Generation)**: Vector database + semantic search
2. **Persistent memory bank**: AI-managed memory store
3. **Notes as memory**: Human-readable notes in the database
4. **Full conversation logs**: Store all AI conversations

## Decision

We will use **notes as the enduring memory**. Every interaction's notes are stored in the `activities.notes` field. When presenting a card, Anne reads the relevant notes to reconstruct context.

## Rationale

### Why Notes as Memory

1. **Human-readable**: Jeff can read and edit the notes directly. No black box.

2. **Already exists**: The activity log with notes is part of any CRM. No new infrastructure.

3. **Simple retrieval**: `SELECT notes FROM activities WHERE prospect_id = ? ORDER BY created_at` - no vector database needed.

4. **Portable**: If Jeff switches systems, the notes export as plain text. No proprietary memory format.

5. **Debuggable**: When Anne says something wrong, Jeff can look at the notes and see why.

6. **Obsessive note-taking works**: Anne logs detailed notes after every interaction. "He mentioned evaluating three vendors. Pain point is manual borrower intake. Wife's name is Sarah - ask about the new baby next time."

### Why Not RAG

- Requires vector database infrastructure (Pinecone, Weaviate, or local FAISS)
- Semantic search adds latency and complexity
- Overkill for 300-400 prospects
- Black box - can't easily see/edit what AI "remembers"

### Why Not Persistent Memory Bank

- Proprietary format
- Can't be edited by Jeff
- Unclear what gets stored
- Adds another data store to maintain

### Why Not Full Conversation Logs

- Too verbose - Jeff doesn't need to see every AI response
- Notes are the distilled, relevant information
- Conversation logs would require summarization anyway

## Consequences

### Positive

- Simple architecture - just database fields
- Human-readable and editable
- No additional infrastructure
- Portable and exportable
- Jeff controls what's remembered

### Negative

- Notes must be well-written (Anne is instructed to be obsessive)
- Long note histories may need summarization for prompt length
- No semantic search (exact text matching only)

### Risks

- **Prompt length limits**: Mitigated by including only recent notes + intel nuggets
- **Note quality varies**: Mitigated by Anne's obsessive note-taking behavior

## Implementation

### Where Notes Live

- `prospects.notes` - Static context ("CEO, hates cold calls")
- `activities.notes` - Running log per interaction
- `intel_nuggets` - Extracted key facts for cheat sheets

### Anne's Note-Taking Rules

1. Log every substantive detail from conversations
2. Extract actionable intel (pain points, competitors, timelines)
3. Note personal details (family, hobbies) for relationship building
4. Record Jeff's impressions ("seems skeptical about pricing")

## Related

- ADR 005: Dual Cadence System (also about prospect state)
- `../layers/LAYER-5-BRAIN.md` - Anne's note-taking capabilities
