# Layer 6: The Heartbeat

**Autonomous Operations**

Version: 1.0
Date: February 5, 2026
Parent: Blueprint v3.2

---

## Overview

The system breathes while Jeff sleeps.

**Components:**
- Nightly Cycle (`autonomous/nightly.py`)
- Orchestrator (`autonomous/orchestrator.py`)
- Background Scheduler (`autonomous/scheduler.py`)
- Reply Monitor (`autonomous/reply_monitor.py`)
- Email Sync (`autonomous/email_sync.py`)
- Activity Capture (`autonomous/activity_capture.py`)

---

## Nightly Cycle (`autonomous/nightly.py`)

### Schedule

Runs 2:00 AM - 7:00 AM via Windows Task Scheduler

### 11 Steps

| Step | Operation | Duration Target |
|------|-----------|-----------------|
| 1 | Take database backup (local + cloud) | < 30s |
| 2 | Pull new prospects from ActiveCampaign | < 2m |
| 3 | Run dedup against master database | < 1m |
| 4 | Assess new records → Broken or Unengaged | < 30s |
| 5 | Run autonomous research on Broken | < 30m |
| 6 | Run Groundskeeper: flag stale data | < 5m |
| 7 | Re-score all active prospects | < 5m |
| 8 | Check monthly buckets → prepare activations | < 30s |
| 9 | Draft nurture email sequences (queued) | < 10m |
| 10 | Pre-generate morning brief + first 10 cards | < 5m |
| 11 | Extract intel nuggets from recent notes | < 5m |

### Functions

```python
def run_nightly_cycle() -> NightlyCycleResult:
    """Execute full nightly cycle. Returns summary."""

def run_condensed_cycle() -> NightlyCycleResult:
    """Run catch-up after missed cycle: backup, buckets, brief."""
```

### Missed Cycle Recovery

If laptop was off at 2 AM:
- App launch detects missed cycle (checks `last_nightly_run` timestamp)
- Runs condensed version: backup, bucket activation, brief generation
- Research, nurture, scoring run in background after launch
- Morning brief notes: "Nightly cycle missed — running catch-up now."

---

## Orchestrator (`autonomous/orchestrator.py`)

The conductor. Coordinates all background tasks.

### Registered Tasks

| Task | Frequency | Purpose |
|------|-----------|---------|
| Reply scanning | Every 30 min | Outlook inbox poll |
| Nurture emails | Every 4 hours | Send approved nurture (daily caps) |
| Demo prep | Hourly | Generate prep for upcoming demos |
| Calendar sync | Hourly | Outlook ↔ IronLung |

### Critical Requirement

**Starts automatically when GUI launches AND runs headless via Task Scheduler.**

This is non-negotiable.

### Functions

```python
def start() -> None:
    """Start orchestrator. Called on GUI launch."""

def stop() -> None:
    """Stop orchestrator gracefully."""

def register_task(name: str, func: Callable, interval: timedelta) -> None:
    """Register a recurring task."""

def run_headless() -> None:
    """Run without GUI for Task Scheduler."""
```

---

## Background Scheduler (`autonomous/scheduler.py`)

Windows Task Scheduler integration.

### Tasks

| Task | Schedule | Command |
|------|----------|---------|
| Nightly Cycle | 2:00 AM daily | `ironlung3.py --nightly` |
| Orchestrator Boot | System startup | `ironlung3.py --orchestrator` |

### Functions

```python
def install_tasks() -> bool:
    """Install Windows Task Scheduler tasks."""

def uninstall_tasks() -> bool:
    """Remove scheduled tasks."""

def check_tasks() -> dict[str, TaskStatus]:
    """Check status of scheduled tasks."""
```

---

## Reply Monitor (`autonomous/reply_monitor.py`)

### Operation

- Poll inbox every 30 minutes
- Match replies to prospects by email address
- Classify: interested, not_interested, ooo, referral, unknown
- Store with full email content for inline display

### No Auto-Promotion

Interested replies are:
- Flagged for Jeff's review
- Surfaced in morning brief
- Jeff decides whether to promote to Engaged

This prevents misclassification from creating bad sales interactions.

### Functions

```python
def poll_inbox() -> list[MatchedReply]:
    """Poll inbox, match to prospects, classify."""

def get_pending_reviews() -> list[MatchedReply]:
    """Get replies awaiting Jeff's review."""
```

---

## Email Sync (`autonomous/email_sync.py`)

### Operation

Synchronize email history between Outlook and database:
- Sent emails stored in activity history
- Received emails stored in activity history
- Available for inline display on cards

### Functions

```python
def sync_sent(since: datetime = None) -> int:
    """Sync sent emails. Returns count synced."""

def sync_received(since: datetime = None) -> int:
    """Sync received emails. Returns count synced."""
```

---

## Activity Capture (`autonomous/activity_capture.py`)

### Operation

Automatic detection and logging of email activity:
- Email sent → activity logged
- Email received → activity logged
- Calendar event created → activity logged

### Functions

```python
def capture_email_activity(message_id: str) -> Optional[int]:
    """Capture email as activity. Returns activity ID."""
```

---

## Auto-Replenish

When unengaged pool runs low:
- Threshold: configurable (default 50)
- Auto-pull from ActiveCampaign
- Anne mentions it in morning brief

### Functions

```python
def check_replenish_needed() -> bool:
    """Check if unengaged pool needs replenishment."""

def replenish_from_activecampaign(limit: int = 100) -> int:
    """Pull new prospects from AC. Returns count imported."""
```

---

## Monthly Bucket Auto-Activation

### Operation

On first business day of month:
- Query parked prospects for that month
- Transition to Unengaged
- Log activity
- Surface in morning brief

### Functions

```python
def activate_monthly_bucket(month: str) -> list[int]:
    """Activate parked prospects for YYYY-MM. Returns prospect IDs."""
```

---

## Build Phases

- **Phase 5**: All autonomous operations (Steps 5.1-5.9)

---

## Performance Targets

| Operation | Target |
|-----------|--------|
| Nightly cycle total | < 1 hour |
| Reply poll | < 2 minutes |
| Monthly activation | < 30 seconds |

---

## Error Recovery

### Cycle Interruption

If nightly cycle interrupted mid-run:
- Picks up where it left off on next run
- No data corruption
- Logs progress markers for each step

### Orchestrator Crash

- Restarts on next scheduled run
- Graceful shutdown on app close
- Logs crash with stack trace

---

**See also:**
- `LAYER-2-PIPES.md` - Outlook integration
- `LAYER-3-ENGINE.md` - Nurture logic, research
- `../patterns/ERROR-HANDLING.md` - Recovery strategies
