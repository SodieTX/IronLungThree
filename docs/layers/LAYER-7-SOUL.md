# Layer 7: The Soul

**ADHD-Specific UX**

Version: 1.0
Date: February 5, 2026
Parent: Blueprint v3.2

---

## Overview

The ADHD brain goes dead in a silent room clicking buttons. It comes alive when there's another intelligence in the room. Layer 7 makes this a cognitive prosthetic.

**Components:**
- Dopamine Engine (`gui/adhd/dopamine.py`)
- Session Manager (`gui/adhd/session.py`)
- Focus Mode (`gui/adhd/focus.py`)
- Audio Feedback (`gui/adhd/audio.py`)
- Command Palette (`gui/adhd/command_palette.py`)
- Glanceable Dashboard (`gui/adhd/dashboard.py`)
- Compassionate Messages (`gui/adhd/compassion.py`)

---

## Dopamine Engine (`gui/adhd/dopamine.py`)

### Micro-Wins

Every small victory gets a hit:
- Card processed
- Email sent
- Call completed
- Demo scheduled
- Follow-up set

### Streaks

Track consecutive productive actions. Celebrations at:
- 5 cards
- 10 cards
- 20 cards
- 50 cards

### Achievements

| Achievement | Trigger |
|-------------|---------|
| First Call | Complete first call |
| First Demo | Schedule first demo |
| First Close | Close first deal |
| Power Hour | 20+ calls in 60 minutes |
| Queue Cleared | Process entire daily queue |
| Perfect Day | All engaged follow-ups completed |
| Streak Master | 50 cards without skip |

### Functions

```python
def record_win(win_type: WinType) -> None:
    """Record a micro-win. Triggers celebration if threshold met."""

def get_streak() -> int:
    """Get current streak count."""

def get_achievements() -> list[Achievement]:
    """Get earned achievements."""

def check_achievement(achievement: str) -> bool:
    """Check and award achievement if earned."""
```

---

## Session Manager (`gui/adhd/session.py`)

### Time Tracking

- Session start time
- Active working time
- Warnings at configured intervals (time blindness protection)

### Energy Levels

| Period | Level | Behavior |
|--------|-------|----------|
| Before 2 PM | HIGH | Full cognitive load |
| 2 PM - 4 PM | MEDIUM | Standard processing |
| After 4 PM | LOW | Reduced load, auto low-energy mode |

### Low-Energy Mode

- Simplified card view
- Fewer options per screen
- Bigger buttons
- More confirmations
- Anne takes more initiative

### Undo History

Last 5 actions stored for quick undo.

### Session Recovery

If app crashes or closes unexpectedly:
- Restore to last known state
- Show what was in progress
- Offer to continue or start fresh

### Functions

```python
def start_session() -> None:
    """Start tracking session."""

def get_energy_level() -> EnergyLevel:
    """Get current energy level based on time."""

def warn_time_elapsed(threshold_minutes: int) -> bool:
    """Check if warning should fire. Returns True if triggered."""

def push_undo(action: UndoableAction) -> None:
    """Push action to undo stack."""

def pop_undo() -> Optional[UndoableAction]:
    """Pop and reverse last action."""

def save_session_state() -> None:
    """Save state for crash recovery."""
```

---

## Focus Mode (`gui/adhd/focus.py`)

### Appearance

- Current card fills the screen
- Queue hidden
- Only visible: card, dictation bar, action buttons
- Tunnel vision by design

### Activation

- Manual: Ctrl+Shift+F or "focus mode"
- Auto: When streak reaches 5 (optional)

### Exit

- Escape key
- "Exit focus" command
- After queue empty

### Functions

```python
def enter_focus_mode() -> None:
    """Enter distraction-free focus mode."""

def exit_focus_mode() -> None:
    """Exit focus mode."""

def is_focus_mode() -> bool:
    """Check if focus mode active."""
```

---

## Audio Feedback (`gui/adhd/audio.py`)

### Sounds

| Action | Sound |
|--------|-------|
| Card processed | Soft ding |
| Email sent | Whoosh |
| Demo scheduled | Chime |
| Deal closed | Celebration |
| Error | Gentle buzz |
| Streak milestone | Level-up |

### Settings

- Master volume
- Individual sound toggles
- Mute all option

### Functions

```python
def play_sound(sound: Sound) -> None:
    """Play sound effect."""

def set_muted(muted: bool) -> None:
    """Set mute state."""
```

---

## Command Palette (`gui/adhd/command_palette.py`)

### Activation

Ctrl+K

### Features

- Fuzzy search across:
  - All tabs
  - All prospects (name, company)
  - All actions ("send email", "schedule demo")
  - Settings
- Recent commands at top
- Keyboard navigation

### Functions

```python
def show_palette() -> None:
    """Show command palette."""

def search(query: str) -> list[PaletteResult]:
    """Search all searchable items."""

def execute(result: PaletteResult) -> None:
    """Execute selected command."""
```

---

## Glanceable Dashboard (`gui/adhd/dashboard.py`)

### Content

One-second read of today's progress:
- Cards processed / total
- Calls made
- Emails sent
- Demos scheduled
- Current streak

### Location

Small widget, always visible (status bar or corner overlay).

### Functions

```python
def get_dashboard_data() -> DashboardData:
    """Get current dashboard stats."""

def refresh_dashboard() -> None:
    """Refresh dashboard display."""
```

---

## Compassionate Messages (`gui/adhd/compassion.py`)

### Core Principle

No guilt trips. Ever.

### Message Types

| Situation | Message Style |
|-----------|---------------|
| Returning after gap | "Welcome back. Here are the 3 most important things." |
| Missed follow-ups | "A few things slipped. Let's catch up." |
| Low productivity day | "Some days are harder. Here's what matters most." |
| Queue empty | "You crushed it. Take a break." |
| Long session | "You've been at it a while. Consider a break." |

### Functions

```python
def get_welcome_message() -> str:
    """Get appropriate welcome message based on context."""

def get_encouragement() -> str:
    """Get contextual encouragement."""

def get_break_suggestion() -> Optional[str]:
    """Suggest break if warranted."""
```

---

## Integration with Anne

Anne embodies the soul:
- Uses compassionate language
- Adjusts verbosity based on energy level
- Celebrates wins
- Never guilts

In low-energy mode, Anne:
- Shorter presentations
- Fewer questions
- More direct suggestions
- "Just do X" instead of "What would you like to do?"

---

## Build Phases

- **Phase 6**: All soul components (Steps 6.1-6.10)

---

## Performance Targets

| Operation | Target |
|-----------|--------|
| Sound playback | < 100ms |
| Command palette search | < 50ms |
| Dashboard refresh | < 50ms |
| Mode switch | < 100ms |

---

## Configuration

All soul features configurable in Settings:
- Dopamine celebrations on/off
- Sound on/off
- Auto low-energy on/off
- Time warning intervals
- Focus mode auto-trigger

---

**See also:**
- `LAYER-4-FACE.md` - GUI integration
- `LAYER-5-BRAIN.md` - Anne's soul integration
- `../build/PHASE-6-SOUL.md` - Build steps
