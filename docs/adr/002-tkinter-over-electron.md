# ADR 002: tkinter Over Electron

## Status

Accepted

## Date

February 5, 2026

## Context

IronLung 3 needs a GUI for a Windows desktop application. The user (Jeff) processes prospects through a tabbed interface with cards, dialogs, and a persistent dictation bar.

Options considered:
1. **tkinter** - Python's built-in GUI toolkit
2. **Electron** - Web technologies (HTML/CSS/JS) in desktop wrapper
3. **Qt (PyQt/PySide)** - Cross-platform native GUI
4. **Dear PyGui** - Modern Python GUI library
5. **Web app (Flask/Django)** - Browser-based

## Decision

We will use **tkinter** for the GUI.

## Rationale

### Why tkinter

1. **Already proven**: IronLung 1 and 2 used tkinter. We know it works for this use case.

2. **Ships with Python**: No additional dependencies to install or manage.

3. **Simple deployment**: No bundling web runtime (Electron = ~150MB overhead).

4. **Fast startup**: Native widgets load instantly. No browser initialization.

5. **Low memory**: tkinter apps use 50-100MB. Electron apps use 200-500MB+.

6. **Stable**: tkinter has been stable for decades. No breaking API changes.

7. **Adequate for the job**: The UI needs tabs, forms, tables, dialogs. tkinter handles all of these.

### Why Not Electron

- 150MB+ runtime overhead for a simple app
- Slower startup (browser initialization)
- Higher memory usage
- JavaScript ecosystem complexity
- Would require rewriting all Python business logic

### Why Not Qt

- More complex than needed
- Licensing considerations (GPL vs commercial)
- Larger learning curve
- Additional dependency management

### Why Not Web App

- Requires running a server
- Browser adds friction (opening app = opening browser + navigating)
- Offline behavior more complex
- Not what Jeff asked for

## Consequences

### Positive

- Zero additional dependencies for GUI
- Fast startup (< 3 seconds)
- Low memory footprint
- Familiar codebase from IronLung 1/2
- Same language (Python) for business logic and UI

### Negative

- Dated visual appearance (can be improved with ttk themes)
- Limited animation capabilities (not needed)
- No built-in rich text editing (not needed)
- Platform look-and-feel tied to OS

### Risks

- **UI looks dated**: Mitigated with ttk themes and consistent styling via `theme.py`
- **Complex layouts difficult**: Mitigated by keeping UI simple and card-focused

## Related

- ADR 001: SQLite Over PostgreSQL (same "simple is better" philosophy)
- `../layers/LAYER-4-FACE.md` - GUI specifications
