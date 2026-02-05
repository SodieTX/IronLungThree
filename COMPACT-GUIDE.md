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

- Stage: Pre-coding / early Phase 1 foundation
- Goal: Establish a stable, verifiable baseline before broader feature implementation

## Key Documents

- `docs/BLUEPRINT.md`
- `docs/BUILD-SEQUENCE.md`
- `docs/PHASE1-CHECKLIST.md`
- `docs/REPO-GRADE.md`
- `docs/build/PHASE-1-BUILD-SPEC.md`
