# ADR 003: Polling Over Webhooks

## Status

Accepted

## Date

February 5, 2026

## Context

IronLung 3 needs to receive email replies from Outlook and potentially other external notifications. There are two approaches:

1. **Webhooks**: Server pushes notifications to client
2. **Polling**: Client periodically checks for new data

## Decision

We will use **polling** for all external data sources (Outlook inbox, ActiveCampaign, etc.).

## Rationale

### Why Polling

1. **Desktop apps can't receive webhooks**: Webhooks require a publicly accessible URL. A desktop app running on Jeff's laptop doesn't have one.

2. **No server infrastructure**: Webhooks would require running a server (AWS Lambda, Azure Function, or VPS) to receive notifications and forward them to the app. This adds complexity, cost, and another point of failure.

3. **Reliable and simple**: Polling is straightforward - call the API, check for new items, process them. No complex setup.

4. **30-minute intervals are fine**: For a sales pipeline, knowing about a reply within 30 minutes is perfectly adequate. This isn't real-time chat.

5. **Works offline**: When Jeff's laptop wakes up after being asleep, polling automatically catches up. Webhooks would have been lost during the sleep period.

### Why Not Webhooks

- Requires publicly accessible endpoint (not possible for desktop app)
- Would require cloud infrastructure to proxy notifications
- More complex error handling (retries, delivery guarantees)
- Missed webhooks during laptop sleep would be lost

### Polling Strategy

| Data Source | Poll Interval | Purpose |
|-------------|---------------|---------|
| Outlook Inbox | 30 minutes | Detect replies |
| Outlook Calendar | 60 minutes | Sync events |
| ActiveCampaign | Nightly only | New prospects |

## Consequences

### Positive

- Zero infrastructure required
- Works reliably without complex setup
- Automatically catches up after laptop sleep
- Simple error handling (just retry on next poll)

### Negative

- Not real-time (30-minute delay acceptable)
- Consumes API calls (within free/paid tier limits)
- Slight increase in network traffic

### Risks

- **API rate limits**: Mitigated by reasonable poll intervals (30-60 minutes)
- **Missed data during laptop off**: Mitigated by polling on app launch

## Related

- `../layers/LAYER-2-PIPES.md` - Outlook integration details
- `../layers/LAYER-6-HEARTBEAT.md` - Reply monitor specifications
