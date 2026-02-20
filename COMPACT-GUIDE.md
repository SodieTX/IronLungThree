# IronLung 3 Compact Guide

## Daily Developer Commands

```bash
# Full quality pass (same shape as CI)
black --check src tests ironlung3.py
isort --check-only src tests ironlung3.py
mypy src
pytest -q

# Phase 1 stage gate
pytest -m phase1_ready -q
```

## Current Stage

- Stage: Phase 6 complete (The Soul — ADHD UX), scaffolding through Phase 7
- Goal: Continue implementation through Build Sequence phases

## Key Documents

- `docs/BLUEPRINT.md`
- `docs/BUILD-SEQUENCE.md`
- `docs/ARCHITECTURE-OVERVIEW.md`
- `docs/build/PHASE-1-BUILD-SPEC.md`
