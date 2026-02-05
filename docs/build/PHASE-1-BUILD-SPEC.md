# Phase 1 Build Spec (Foundation)

## Scope

Phase 1 establishes the local data foundation:

- SQLite schema initialization
- core data models
- import path scaffolding
- backup scaffolding
- baseline GUI scaffolding

## Stage Gate

Phase 1 foundation readiness is validated with:

```bash
pytest -m phase1_ready -q
```

## Additional Checks

```bash
black --check src tests ironlung3.py
isort --check-only src tests ironlung3.py
mypy src
pytest -q
```

## Handoff Requirements

Use `docs/PHASE1-CHECKLIST.md` as the sign-off checklist.
